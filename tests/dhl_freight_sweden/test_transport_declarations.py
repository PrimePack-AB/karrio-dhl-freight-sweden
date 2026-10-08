"""DHL Freight (SE API Farm) EKAER and UIT additionalInformation tests.

The "Related fields" tables of product manual v5.26 for products 202, 205,
233, SPI, and 601 list EKAER_FREE with EKAER_NUMBER (AN..20) for HU and
UIT_FREE with UIT_NUMBER (AN..19) for RO; the UIT number is conditional even
when the shipment is not UIT free ("Code should be provided if possible",
e.g. §5.4 p23).

Without a declaration or number, these products declare the shipment EKAER
or UIT free below 500 kg total gross weight and are refused at or above it.
"""

import typing
import unittest

import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import (
    TransportDeclarationError,
)

from .fixture import detail_keys, gateway, serialize_request
from .test_shipment import _payload, _recipient_de, _recipient_se


class TestDHLFreightTransportDeclarations(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _serialize(self, payload: dict) -> dict:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        return serialize_request(request)

    def _error(self, payload: dict) -> TransportDeclarationError:
        with self.assertRaises(TransportDeclarationError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def test_declaration_products_without_declaration_send_free(self):
        for service in DeclarationServices:
            for recipient, code in [(_recipient_hu, "EKAER_FREE"), (_recipient_ro, "UIT_FREE")]:
                with self.subTest(service=service, country=recipient["country_code"]):
                    serialized = self._serialize(_declaration_payload(service, recipient))

                    self.assertEqual(
                        serialized["additionalInformation"],
                        [{"code": code, "stringValue": "true"}],
                    )

    def test_without_declaration_below_500_kg_sends_free(self):
        for recipient, code in Declarations:
            for parcels in [
                [{"weight": 499.99, "weight_unit": "KG"}],
                [{"weight": 1102, "weight_unit": "LB"}],
                [{"weight": 249.9, "weight_unit": "KG"}] * 2,
            ]:
                with self.subTest(code=code, parcels=parcels):
                    serialized = self._serialize(
                        _with_parcels(_road_freight(recipient), parcels)
                    )

                    self.assertEqual(
                        serialized["additionalInformation"],
                        [{"code": code, "stringValue": "true"}],
                    )

    def test_without_declaration_at_or_above_500_kg_fails(self):
        for recipient, name in [(_recipient_hu, "ekaer"), (_recipient_ro, "uit")]:
            for parcels in [
                [{"weight": 500, "weight_unit": "KG"}],
                [{"weight": 500.01, "weight_unit": "KG"}],
                [{"weight": 1102.5, "weight_unit": "LB"}],
                [{"weight": 1103, "weight_unit": "LB"}],
                [{"weight": 200, "weight_unit": "KG"}] * 3,
            ]:
                with self.subTest(name=name, parcels=parcels):
                    error = self._error(_with_parcels(_road_freight(recipient), parcels))

                    options = {
                        f"dhl_freight_sweden_{name}_free",
                        f"dhl_freight_sweden_{name}_number",
                    }
                    self.assertEqual(detail_keys(error), options)
                    self.assertIn("500 kg", str(error))
                    for option in options:
                        self.assertIn(option, str(error))

    def test_from_hu_and_ro_without_declaration_at_500_kg_fails(self):
        for shipper, option in [
            (_shipper_hu, "dhl_freight_sweden_ekaer_free"),
            (_shipper_ro, "dhl_freight_sweden_uit_free"),
        ]:
            with self.subTest(country=shipper["country_code"]):
                error = self._error(
                    _with_parcels(
                        _import_payload("dhl_freight_sweden_road_freight_standard", shipper),
                        [{"weight": 500, "weight_unit": "KG"}],
                    )
                )

                self.assertIn(option, detail_keys(error))
                self.assertIn("to or from", str(error))

    def test_explicit_free_at_or_above_500_kg_is_sent(self):
        for recipient, code in Declarations:
            option = f"dhl_freight_sweden_{code.split('_')[0].lower()}_free"
            for weight in [500, 2000]:
                with self.subTest(code=code, weight=weight):
                    serialized = self._serialize(
                        _with_parcels(
                            _road_freight(recipient, {option: True}),
                            [{"weight": weight, "weight_unit": "KG"}],
                        )
                    )

                    self.assertEqual(
                        serialized["additionalInformation"],
                        [{"code": code, "stringValue": "true"}],
                    )

    def test_number_at_or_above_500_kg_is_sent(self):
        cases = [
            (_recipient_hu, "dhl_freight_sweden_ekaer_number", "EKAER", "E2026100500001"),
            (_recipient_ro, "dhl_freight_sweden_uit_number", "UIT", "1234-5678-9012-3456"),
        ]

        for recipient, option, name, number in cases:
            with self.subTest(name=name):
                serialized = self._serialize(
                    _with_parcels(
                        _road_freight(recipient, {option: number}),
                        [{"weight": 800, "weight_unit": "KG"}],
                    )
                )

                self.assertEqual(
                    serialized["additionalInformation"],
                    [
                        {"code": f"{name}_FREE", "stringValue": "false"},
                        {"code": f"{name}_NUMBER", "stringValue": number},
                    ],
                )

    def test_other_products_at_or_above_500_kg_send_nothing_by_default(self):
        for recipient in [_recipient_hu, _recipient_ro]:
            with self.subTest(country=recipient["country_code"]):
                serialized = self._serialize(
                    _with_parcels(
                        _parcel_connect(recipient), [{"weight": 600, "weight_unit": "KG"}]
                    )
                )

                self.assertNotIn("additionalInformation", serialized)

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

        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_ekaer_number"})

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
            detail_keys(error),
            {"dhl_freight_sweden_ekaer_free", "dhl_freight_sweden_ekaer_number"},
        )

    def test_ekaer_number_over_twenty_characters_fails(self):
        error = self._error(
            _road_freight(_recipient_hu, {"dhl_freight_sweden_ekaer_number": "E" * 21})
        )

        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_ekaer_number"})

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
            detail_keys(error),
            {"dhl_freight_sweden_uit_free", "dhl_freight_sweden_uit_number"},
        )

    def test_uit_number_over_nineteen_characters_fails(self):
        error = self._error(
            _road_freight(
                _recipient_ro, {"dhl_freight_sweden_uit_number": "1234-5678-9012-34567"}
            )
        )

        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_uit_number"})

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

    def test_declaration_products_from_hu_and_ro_without_declaration_send_free(self):
        for service in DeclarationServices:
            for shipper, code in [(_shipper_hu, "EKAER_FREE"), (_shipper_ro, "UIT_FREE")]:
                with self.subTest(service=service, country=shipper["country_code"]):
                    serialized = self._serialize(_import_payload(service, shipper))

                    self.assertEqual(
                        serialized["additionalInformation"],
                        [{"code": code, "stringValue": "true"}],
                    )

    def test_lanes_from_hu_and_ro_send_explicit_declarations(self):
        cases = [
            (
                _shipper_hu,
                {"dhl_freight_sweden_ekaer_number": "E1234567890123456789"},
                [
                    {"code": "EKAER_FREE", "stringValue": "false"},
                    {"code": "EKAER_NUMBER", "stringValue": "E1234567890123456789"},
                ],
            ),
            (
                _shipper_ro,
                {"dhl_freight_sweden_uit_free": True},
                [{"code": "UIT_FREE", "stringValue": "true"}],
            ),
        ]

        for shipper, options, expected in cases:
            with self.subTest(country=shipper["country_code"]):
                serialized = self._serialize(
                    _import_payload(
                        "dhl_freight_sweden_road_freight_standard", shipper, options
                    )
                )

                self.assertEqual(serialized["additionalInformation"], expected)

    def test_other_products_from_hu_do_not_require_a_declaration(self):
        serialized = self._serialize(
            {
                **_payload("dhl_freight_sweden_parcel_return_connect_c2b", _recipient_se),
                "shipper": _shipper_hu,
            }
        )

        self.assertNotIn("additionalInformation", serialized)


def _declaration_payload(service: str, recipient: dict, options: typing.Optional[dict] = None) -> dict:
    return _payload(
        service, recipient, {"dhl_freight_sweden_payer_code": "DAP", **(options or {})}
    )


def _import_payload(service: str, shipper: dict, options: typing.Optional[dict] = None) -> dict:
    return {
        **_payload(
            service,
            _recipient_se,
            {"dhl_freight_sweden_payer_code": "EXW", **(options or {})},
        ),
        "shipper": shipper,
    }


def _road_freight(recipient: dict, options: typing.Optional[dict] = None) -> dict:
    return _declaration_payload(
        "dhl_freight_sweden_road_freight_standard", recipient, options
    )


def _with_parcels(payload: dict, parcels: typing.List[dict]) -> dict:
    return {**payload, "parcels": parcels}


def _parcel_connect(recipient: dict, options: typing.Optional[dict] = None) -> dict:
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

Declarations = [(_recipient_hu, "EKAER_FREE"), (_recipient_ro, "UIT_FREE")]

_shipper_hu = {
    **_recipient_hu,
    "company_name": "Test Shipper Kft.",
    "person_name": "Nagy Anna",
}

_shipper_ro = {
    **_recipient_ro,
    "company_name": "Test Shipper SRL",
    "person_name": "Popescu Ana",
}


if __name__ == "__main__":
    unittest.main()
