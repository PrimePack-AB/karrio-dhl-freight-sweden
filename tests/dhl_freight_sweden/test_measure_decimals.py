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

    def test_positive_weight_below_the_step_goes_out_as_the_step(self):
        light = {**_PARCEL, "weight": 0.04}
        body = _booking("dhl_freight_sweden_paket", _recipient_se, [light, light])

        self.assertEqual([piece["weight"] for piece in body["pieces"]], [0.1, 0.1])
        self.assertEqual(body["totalWeight"], 0.2)
        self.assertEqual(
            _pickup("dhl_freight_sweden_paket", [light])["totalWeight"], 0.1
        )

    def test_tables_state_dimension_decimals(self):
        decimals = provider_units.PRODUCT_MEASURE_DECIMALS

        self.assertEqual(
            sorted(code for code, row in decimals.items() if row.dimensions == 1),
            ["102", "103", "104", "109", "112", "118"],
        )
        self.assertTrue(
            all(row.dimensions in (0, 1) for row in decimals.values())
        )

    def test_dimensions_round_to_the_table_decimals(self):
        parcel = {**_PARCEL, "length": 30.46, "width": 20.04, "height": 10.55}
        for service, sides, volume in (
            ("dhl_freight_sweden_paket", (30.5, 20.0, 10.6), 0.006),
            ("dhl_freight_sweden_stycke", (30.0, 20.0, 11.0), 0.007),
        ):
            with self.subTest(service=service):
                for body in (
                    _booking(service, _recipient_se, [parcel]),
                    _pickup(service, [parcel]),
                ):
                    piece = body["pieces"][0]

                    self.assertEqual(
                        (piece["length"], piece["width"], piece["height"]), sides
                    )
                    self.assertEqual(piece["volume"], volume)

    def test_positive_dimension_below_the_step_goes_out_as_the_step(self):
        package = _package(height=0.4)

        self.assertEqual(provider_utils.dimensions_cm(package, "211"), (30.0, 20.0, 1.0))
        self.assertEqual(provider_utils.dimensions_cm(package, "102"), (30.0, 20.0, 0.4))

    def test_107_keeps_unrounded_dimensions(self):
        package = _package(length=30.46)

        self.assertEqual(provider_utils.dimensions_cm(package, "107"), (30.46, 20.0, 10.0))
