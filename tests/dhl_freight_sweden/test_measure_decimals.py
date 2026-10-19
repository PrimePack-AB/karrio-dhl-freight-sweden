"""Piece weight and volume precision from the product tables' "Number of decimals" rows.

Every product section of product manual v5.26 except 107 (§5.15 p65-p67)
states the decimals of weight and volume: weight to 1 decimal throughout,
volume to 3 decimals, and no volume ("-") for 210 (§5.6 p30) and 109
(§5.14 p62). Bookings and pickups send pieces at those decimals.
"""

import copy
import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.dhl_freight_sweden.units as provider_units
import karrio.providers.dhl_freight_sweden.utils as provider_utils

from .fixture import gateway, members, serialize_request
from .test_pickup import _options, _pickup_request
from .test_shipment import (
    _payload,
    _recipient_de,
    _recipient_se,
)

_PARCEL = {
    "weight": 1.26,
    "weight_unit": "KG",
    "length": 30.0,
    "width": 20.0,
    "height": 10.0,
    "dimension_unit": "CM",
    "reference_number": "REF-001",
}


def _booking(service: str, recipient: dict, parcels: typing.List[dict]) -> dict:
    payload = {**copy.deepcopy(_payload(service, recipient)), "parcels": parcels}
    return serialize_request(
        gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
    )


def _pickup(service: str, parcels: typing.List[dict], payer_code: str = "1") -> dict:
    options = _options(
        dhl_freight_sweden_service=service, dhl_freight_sweden_payer_code=payer_code
    )
    return serialize_request(
        gateway.mapper.create_pickup_request(
            _pickup_request(parcels=parcels, options=options)
        )
    )


def _package(**changes: typing.Any) -> lib.units.Package:
    return lib.to_packages(
        [typing.cast(models.Parcel, lib.to_object(models.Parcel, {**_PARCEL, **changes}))]
    ).single


class TestMeasureDecimals(unittest.TestCase):
    def test_every_booked_product_but_107_has_its_table(self):
        products = {member.value for member in members(provider_units.ShippingService)}

        self.assertEqual(
            products - set(provider_units.PRODUCT_MEASURE_DECIMALS), {"107"}
        )

    def test_booking_rounds_piece_and_total_weight_to_one_decimal(self):
        body = _booking("dhl_freight_sweden_paket", _recipient_se, [_PARCEL, _PARCEL])

        self.assertEqual([piece["weight"] for piece in body["pieces"]], [1.3, 1.3])
        self.assertEqual([piece["volume"] for piece in body["pieces"]], [0.006, 0.006])
        self.assertEqual(body["totalWeight"], 2.6)

    def test_booking_sends_no_volume_for_products_without_volume_decimals(self):
        for service, recipient in (
            ("dhl_freight_sweden_parcel_connect_b2c", _recipient_de),
            ("dhl_freight_sweden_pall", _recipient_se),
        ):
            with self.subTest(service=service):
                body = _booking(service, recipient, [_PARCEL])

                self.assertNotIn("volume", body["pieces"][0])
                self.assertEqual(body["pieces"][0]["weight"], 1.3)

    def test_pickup_rounds_weight_and_keeps_three_volume_decimals(self):
        body = _pickup("dhl_freight_sweden_paket", [_PARCEL, _PARCEL])

        self.assertEqual([piece["weight"] for piece in body["pieces"]], [1.3, 1.3])
        self.assertEqual(body["totalWeight"], 2.6)
        self.assertEqual(body["totalVolume"], 0.012)

    def test_pickup_sends_no_volume_for_products_without_volume_decimals(self):
        for service, payer_code in (
            ("dhl_freight_sweden_parcel_connect_b2c", "022"),
            ("dhl_freight_sweden_pall", "1"),
        ):
            with self.subTest(service=service):
                body = _pickup(service, [_PARCEL], payer_code)

                self.assertNotIn("volume", body["pieces"][0])
                self.assertNotIn("totalVolume", body)

    def test_weight_rounds_half_up(self):
        self.assertEqual(provider_utils.weight_kg(_package(weight=1.25), "102"), 1.3)
        self.assertEqual(provider_utils.weight_kg(_package(weight=1.24), "102"), 1.2)

    def test_107_keeps_the_unrounded_weight_and_three_volume_decimals(self):
        package = _package(weight=1.26)

        self.assertEqual(provider_utils.weight_kg(package, "107"), 1.26)
        self.assertEqual(provider_utils.volume_m3(package, "107"), 0.006)
