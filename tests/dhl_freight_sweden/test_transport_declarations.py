"""DHL Freight (SE API Farm) EKAER and UIT additionalInformation tests.

The "Related fields" tables of product manual v5.23 for products 202, 205,
233, SPI, and 601 list EKAER_FREE with EKAER_NUMBER (AN..20) for HU and
UIT_FREE with UIT_NUMBER (AN..19) for RO; the UIT number is optional even
when the shipment is not UIT free (release note p7).
"""

import unittest

import karrio.lib as lib
import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import (
    TransportDeclarationError,
)

from .fixture import gateway
from .test_shipment import _payload, _recipient_de, _recipient_se


class TestDHLFreightTransportDeclarations(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _serialize(self, payload: dict) -> dict:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        return lib.to_dict(request.serialize())

    def _error(self, payload: dict) -> TransportDeclarationError:
        with self.assertRaises(TransportDeclarationError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def test_declaration_products_without_declaration_fail(self):
        for service in DeclarationServices:
            for recipient, option in [
                (_recipient_hu, "dhl_freight_sweden_ekaer_free"),
                (_recipient_ro, "dhl_freight_sweden_uit_free"),
            ]:
                with self.subTest(service=service, country=recipient["country_code"]):
                    error = self._error(_declaration_payload(service, recipient))

                    self.assertEqual(set(error.details), {option})
                    self.assertIn(option, str(error))

    def test_ekaer_free_is_sent(self):
        serialized = self._serialize(
            _road_freight(_recipient_hu, {"dhl_freight_sweden_ekaer_free": True})
        )

        self.assertEqual(
            serialized["additionalInformation"],
            [{"code": "EKAER_FREE", "stringValue": "true"}],
        )

    def test_ekaer_number_is_sent_with_ekaer_free_false(self):
        for free in [{}, {"dhl_freight_sweden_ekaer_free": False}]:
            with self.subTest(free=free):
                serialized = self._serialize(
                    _road_freight(
                        _recipient_hu,
                        {**free, "dhl_freight_sweden_ekaer_number": "E2026100500001"},
                    )
                )

                self.assertEqual(
                    serialized["additionalInformation"],
                    [
                        {"code": "EKAER_FREE", "stringValue": "false"},
                        {"code": "EKAER_NUMBER", "stringValue": "E2026100500001"},
                    ],
                )

    def test_ekaer_free_false_without_number_fails(self):
        error = self._error(
            _road_freight(_recipient_hu, {"dhl_freight_sweden_ekaer_free": False})
        )

        self.assertEqual(set(error.details), {"dhl_freight_sweden_ekaer_number"})

    def test_ekaer_free_with_number_fails(self):
        error = self._error(
            _road_freight(
                _recipient_hu,
                {
                    "dhl_freight_sweden_ekaer_free": True,
                    "dhl_freight_sweden_ekaer_number": "E2026100500001",
                },
            )
        )

        self.assertEqual(
            set(error.details),
            {"dhl_freight_sweden_ekaer_free", "dhl_freight_sweden_ekaer_number"},
        )

    def test_ekaer_number_over_twenty_characters_fails(self):
        error = self._error(
            _road_freight(_recipient_hu, {"dhl_freight_sweden_ekaer_number": "E" * 21})
        )

        self.assertEqual(set(error.details), {"dhl_freight_sweden_ekaer_number"})

    def test_uit_free_is_sent(self):
        serialized = self._serialize(
            _road_freight(_recipient_ro, {"dhl_freight_sweden_uit_free": True})
        )

        self.assertEqual(
            serialized["additionalInformation"],
            [{"code": "UIT_FREE", "stringValue": "true"}],
        )

    def test_uit_number_is_sent_with_uit_free_false(self):
        for free in [{}, {"dhl_freight_sweden_uit_free": False}]:
            with self.subTest(free=free):
                serialized = self._serialize(
                    _road_freight(
                        _recipient_ro,
                        {**free, "dhl_freight_sweden_uit_number": "1234-5678-9012-3456"},
                    )
                )

                self.assertEqual(
                    serialized["additionalInformation"],
                    [
                        {"code": "UIT_FREE", "stringValue": "false"},
                        {"code": "UIT_NUMBER", "stringValue": "1234-5678-9012-3456"},
                    ],
                )

    def test_uit_free_false_without_number_is_sent(self):
        serialized = self._serialize(
            _road_freight(_recipient_ro, {"dhl_freight_sweden_uit_free": False})
        )

        self.assertEqual(
            serialized["additionalInformation"],
            [{"code": "UIT_FREE", "stringValue": "false"}],
        )

    def test_uit_free_with_number_fails(self):
        error = self._error(
            _road_freight(
                _recipient_ro,
                {
                    "dhl_freight_sweden_uit_free": True,
                    "dhl_freight_sweden_uit_number": "1234-5678-9012-3456",
                },
            )
        )

        self.assertEqual(
            set(error.details),
            {"dhl_freight_sweden_uit_free", "dhl_freight_sweden_uit_number"},
        )

    def test_uit_number_over_nineteen_characters_fails(self):
        error = self._error(
            _road_freight(
                _recipient_ro, {"dhl_freight_sweden_uit_number": "1234-5678-9012-34567"}
            )
        )

        self.assertEqual(set(error.details), {"dhl_freight_sweden_uit_number"})

    def test_other_products_to_hu_and_ro_send_nothing_by_default(self):
        for recipient in [_recipient_hu, _recipient_ro]:
            with self.subTest(country=recipient["country_code"]):
                serialized = self._serialize(_parcel_connect(recipient))

                self.assertNotIn("additionalInformation", serialized)

    def test_other_products_to_hu_and_ro_send_explicit_declarations(self):
        cases = [
            (_recipient_hu, {"dhl_freight_sweden_ekaer_free": True}, "EKAER_FREE"),
            (_recipient_ro, {"dhl_freight_sweden_uit_free": True}, "UIT_FREE"),
        ]

        for recipient, options, code in cases:
            with self.subTest(code=code):
                serialized = self._serialize(_parcel_connect(recipient, options))

                self.assertEqual(
                    serialized["additionalInformation"],
                    [{"code": code, "stringValue": "true"}],
                )

    def test_lanes_without_hu_or_ro_send_no_declarations(self):
        serialized = self._serialize(
            _road_freight(
                _recipient_de,
                {
                    "dhl_freight_sweden_ekaer_free": True,
                    "dhl_freight_sweden_uit_number": "1234-5678-9012-3456",
                },
            )
        )

        self.assertNotIn("additionalInformation", serialized)

    def test_lane_from_hu_does_not_require_a_declaration(self):
        serialized = self._serialize(
            {
                **_road_freight(_recipient_se, {"dhl_freight_sweden_payer_code": "EXW"}),
                "shipper": _shipper_hu,
            }
        )

        self.assertNotIn("additionalInformation", serialized)


def _declaration_payload(service: str, recipient: dict, options: dict = None) -> dict:
    return _payload(
        service, recipient, {"dhl_freight_sweden_payer_code": "DAP", **(options or {})}
    )


def _road_freight(recipient: dict, options: dict = None) -> dict:
    return _declaration_payload(
        "dhl_freight_sweden_road_freight_standard", recipient, options
    )


def _parcel_connect(recipient: dict, options: dict = None) -> dict:
    return _payload("dhl_freight_sweden_parcel_connect_b2c", recipient, options)


DeclarationServices = [
    "dhl_freight_sweden_road_freight_standard",
    "dhl_freight_sweden_road_freight_direct",
    "dhl_freight_sweden_road_freight_priority",
    "dhl_freight_sweden_standard_pallet_international",
    "dhl_freight_sweden_home_delivery_international_b2c",
]

_recipient_hu = {
    **_recipient_se,
    "city": "Budapest",
    "postal_code": "1051",
    "country_code": "HU",
}

_recipient_ro = {
    **_recipient_se,
    "city": "Bucuresti",
    "postal_code": "010011",
    "country_code": "RO",
}

_shipper_hu = {
    **_recipient_hu,
    "company_name": "Test Shipper Kft.",
    "person_name": "Nagy Anna",
}


if __name__ == "__main__":
    unittest.main()
