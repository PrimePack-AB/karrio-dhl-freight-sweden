"""DHL Freight (SE API Farm) consignor customer number per booking system.

DHL Freight Sweden books products in two systems that number customers
separately (IFTMIN shipment instruction v3.7 p10): 202, 205, 233, SPI, and
601 take the international customer number as the consignor id, whose
"DHL account number format" rows in product manual v5.26 allow up to 35
alphanumeric characters, and every other product takes the 6-digit
domestic customer number. The Transport Instruction API caps Party.id at
15 characters.
"""

import typing
import unittest

import karrio.core.models as models
import karrio.sdk as karrio
from karrio.providers.dhl_freight_sweden import units
from karrio.providers.dhl_freight_sweden.shipment.create import (
    InternationalAccountNumberError,
)

from .fixture import as_dict, detail_keys, gateway, members, serialize_request
from .test_shipment import _payload, _recipient_dk, _recipient_se

INTERNATIONAL = {"202", "205", "233", "SPI", "601"}

INTERNATIONAL_SERVICES = {
    "202": "dhl_freight_sweden_road_freight_standard",
    "205": "dhl_freight_sweden_road_freight_direct",
    "233": "dhl_freight_sweden_road_freight_priority",
    "SPI": "dhl_freight_sweden_standard_pallet_international",
    "601": "dhl_freight_sweden_home_delivery_international_b2c",
}


def _gateway(**settings: typing.Any):
    return karrio.gateway["dhl_freight_sweden"].create(
        dict(
            test_mode=True,
            carrier_id="dhl_freight_sweden",
            client_key="TEST_CLIENT_KEY",
            account_number="1234567",
            **settings,
        )
    )


def _international(service: str) -> dict:
    return _payload(service, _recipient_dk, {"dhl_freight_sweden_payer_code": "DAP"})


def _consignor_id(gateway, payload: dict) -> typing.Optional[str]:
    request = gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
    body = serialize_request(request)
    consignor = next(
        party for party in body["parties"] if as_dict(party)["type"] == "Consignor"
    )
    return as_dict(consignor).get("id")


class TestDHLFreightBookingSystems(unittest.TestCase):
    def test_every_product_has_a_booking_system(self):
        self.assertEqual(
            {member.value for member in members(units.ShippingService)},
            set(units.PRODUCT_BOOKING_SYSTEMS),
        )

    def test_international_products(self):
        self.assertEqual(
            {
                code
                for code, system in units.PRODUCT_BOOKING_SYSTEMS.items()
                if system == units.BookingSystem.international
            },
            INTERNATIONAL,
        )


class TestDHLFreightConsignorAccountNumber(unittest.TestCase):
    def test_domestic_products_send_the_account_number(self):
        cases = [
            ("102", _payload("dhl_freight_sweden_paket", _recipient_se)),
            ("109", _payload("dhl_freight_sweden_parcel_connect_b2c", _recipient_dk)),
            ("112", _payload("dhl_freight_sweden_parcel_connect_plus", _recipient_dk)),
        ]

        for code, payload in cases:
            with self.subTest(product=code):
                self.assertEqual(_consignor_id(gateway, payload), "1234567")

    def test_domestic_products_book_without_an_international_account_number(self):
        self.assertEqual(
            _consignor_id(
                _gateway(), _payload("dhl_freight_sweden_paket", _recipient_se)
            ),
            "1234567",
        )

    def test_international_products_send_the_international_account_number(self):
        for code, service in INTERNATIONAL_SERVICES.items():
            with self.subTest(product=code):
                self.assertEqual(
                    _consignor_id(gateway, _international(service)), "INT1234567"
                )

    def test_international_account_number_is_stripped(self):
        self.assertEqual(
            _consignor_id(
                _gateway(international_account_number=" INT1234567 "),
                _international(INTERNATIONAL_SERVICES["202"]),
            ),
            "INT1234567",
        )

    def test_international_products_refuse_without_an_international_account_number(self):
        for settings in ({}, {"international_account_number": "  "}):
            for code, service in INTERNATIONAL_SERVICES.items():
                with self.subTest(product=code, settings=settings):
                    with self.assertRaises(InternationalAccountNumberError) as context:
                        _consignor_id(_gateway(**settings), _international(service))

                    self.assertEqual(
                        detail_keys(context.exception), {"international_account_number"}
                    )
                    self.assertIn(code, str(context.exception))

    def test_international_account_number_at_most_15_characters(self):
        payload = _international(INTERNATIONAL_SERVICES["233"])

        self.assertEqual(
            _consignor_id(_gateway(international_account_number="A" * 15), payload),
            "A" * 15,
        )
        with self.assertRaises(InternationalAccountNumberError) as context:
            _consignor_id(_gateway(international_account_number="A" * 16), payload)

        self.assertIn("16 characters", str(context.exception))
        self.assertEqual(
            (context.exception.details or {})["international_account_number"]["code"],
            "invalid",
        )

    def test_domestic_products_ignore_an_overlong_international_account_number(self):
        self.assertEqual(
            _consignor_id(
                _gateway(international_account_number="A" * 16),
                _payload("dhl_freight_sweden_paket", _recipient_se),
            ),
            "1234567",
        )

    def test_rates_list_international_products_without_an_international_account_number(self):
        shipment = _payload("dhl_freight_sweden_paket", _recipient_dk)
        request = models.RateRequest(
            **{
                key: shipment[key] for key in ("shipper", "recipient", "parcels")
            },
            services=list(INTERNATIONAL_SERVICES.values()),
        )

        rates, _ = karrio.Rating.fetch(request).from_(_gateway()).parse()

        self.assertEqual(
            {rate.meta["carrier_service_code"] for rate in rates if rate.meta},
            INTERNATIONAL,
        )
