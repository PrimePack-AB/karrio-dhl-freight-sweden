"""DHL Freight (SE API Farm) payer code tests.

Payer codes are validated per product against the "Payer codes" tables of
DHL Freight Sweden product manual v5.23. The expected PL bookings mirror the
transport instructions the live sandbox accepted on 2026-10-05 (bookings
2906761073 and 2906761081), with the piece volume at karrio's two-decimal
cubic-metre precision.
"""

import typing
import unittest

import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import PayerCodeError

from .fixture import detail_keys, gateway, serialize_request
from .test_shipment import (
    Customs,
    _payload,
    _recipient_de,
    _recipient_no,
    _recipient_se,
    _shipper,
)


class TestDHLFreightPayerCodes(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _serialize(self, payload: dict) -> dict:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        return serialize_request(request)

    def _payer_code(self, payload: dict) -> str:
        return self._serialize(payload)["payerCode"]["code"]

    def _error(self, payload: dict) -> PayerCodeError:
        with self.assertRaises(PayerCodeError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def test_parcel_connect_to_pl_parcel_shop_defaults_to_022(self):
        self.assertEqual(
            self._serialize(ShipmentPayload109ParcelShopPL), ShipmentRequest109PL
        )

    def test_parcel_connect_plus_to_pl_defaults_to_023(self):
        self.assertEqual(self._serialize(ShipmentPayload112PL), ShipmentRequest112PL)

    def test_explicit_invalid_payer_code_names_valid_codes(self):
        error = self._error(
            _with_options(ShipmentPayload112PL, {"dhl_freight_sweden_payer_code": "1"})
        )

        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_payer_code"})
        self.assertIn("valid codes: 022, 023", str(error))

    def test_explicit_022_on_parcel_connect_plus_is_sent(self):
        payload = _with_options(
            ShipmentPayload112PL, {"dhl_freight_sweden_payer_code": "022"}
        )

        self.assertEqual(self._payer_code(payload), "022")

    def test_explicit_valid_payer_code_is_sent(self):
        payload = _payload(
            "dhl_freight_sweden_paket",
            _recipient_se,
            {"dhl_freight_sweden_payer_code": "3"},
        )

        self.assertEqual(self._payer_code(payload), "3")

    def test_incoterm_dap_on_parcel_connect_translates_to_022(self):
        self.assertEqual(self._payer_code(_with_incoterm(_parcel_connect, "DAP")), "022")

    def test_incoterm_ddp_on_parcel_connect_plus_translates_to_023(self):
        self.assertEqual(
            self._payer_code(_with_incoterm(_parcel_connect_plus, "DDP")), "023"
        )

    def test_incoterms_on_parcel_connect_plus_translate_to_022(self):
        for incoterm in ["DAP", "CPT", "CIP", "DPU"]:
            with self.subTest(incoterm=incoterm):
                self.assertEqual(
                    self._payer_code(_with_incoterm(_parcel_connect_plus, incoterm)),
                    "022",
                )

    def test_untranslatable_incoterm_on_parcel_connect_plus_fails(self):
        error = self._error(_with_incoterm(_parcel_connect_plus, "EXW"))

        self.assertEqual(detail_keys(error), {"customs.incoterm"})
        self.assertIn("valid codes: 022, 023", str(error))

    def test_incoterm_ddp_on_parcel_connect_requires_joint_declaration(self):
        error = self._error(_with_incoterm(_parcel_connect, "DDP"))

        self.assertEqual(
            detail_keys(error), {"dhl_freight_sweden_customs_joint_declaration"}
        )

    def test_explicit_023_on_parcel_connect_requires_joint_declaration(self):
        error = self._error(
            _with_options(
                _parcel_connect, {"dhl_freight_sweden_payer_code": "023"}
            )
        )

        self.assertEqual(
            detail_keys(error), {"dhl_freight_sweden_customs_joint_declaration"}
        )

    def test_incoterm_ddp_on_parcel_connect_with_joint_declaration_is_023(self):
        payload = _with_options(
            _with_incoterm(_parcel_connect, "DDP"),
            {
                "dhl_freight_sweden_customs_joint_declaration": True,
                "dhl_freight_sweden_customs_joint_declaration_id": "SFID-0001",
            },
        )

        self.assertEqual(self._payer_code(payload), "023")

    def test_incoterm_outside_domestic_product_list_keeps_default(self):
        payload = {**_payload("dhl_freight_sweden_paket", _recipient_se), "customs": Customs}

        self.assertEqual(self._payer_code(payload), "1")

    def test_product_without_default_requires_explicit_payer_code(self):
        error = self._error(
            _payload("dhl_freight_sweden_euroconnect_plus", _recipient_de)
        )

        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_payer_code"})
        self.assertIn("DAP, DDP", str(error))

    def test_home_delivery_return_requires_explicit_payer_code(self):
        error = self._error(_payload("dhl_freight_sweden_home_delivery_c2b", _recipient_se))

        self.assertIn("3, 4", str(error))

    def test_products_with_derived_defaults(self):
        cases = [
            ("dhl_freight_sweden_service_point_c2b", "3"),
            ("dhl_freight_sweden_parcel_return_connect_c2b", "001"),
            ("dhl_freight_sweden_hemleverans_paket_b2c", "1"),
        ]

        for service, payer_code in cases:
            with self.subTest(service=service):
                self.assertEqual(
                    self._payer_code(_payload(service, _recipient_se)), payer_code
                )

    def test_road_freight_direct_import_accepts_import_terms_only(self):
        payload = {
            **_payload(
                "dhl_freight_sweden_road_freight_direct",
                _recipient_se,
                {"dhl_freight_sweden_payer_code": "DAP"},
            ),
            "shipper": _shipper_de,
        }

        error = self._error(payload)
        self.assertIn("valid codes: EXW, FCA", str(error))
        self.assertEqual(
            self._payer_code(
                _with_options(payload, {"dhl_freight_sweden_payer_code": "EXW"})
            ),
            "EXW",
        )

    def test_road_freight_direct_export_rejects_exw(self):
        error = self._error(
            _payload(
                "dhl_freight_sweden_road_freight_direct",
                _recipient_no,
                {"dhl_freight_sweden_payer_code": "EXW"},
            )
        )

        self.assertIn("valid codes: CPT, CIP, DAP, DPU, DDP", str(error))


def _with_options(payload: dict, options: dict) -> dict:
    return {**payload, "options": {**payload.get("options", {}), **options}}


def _with_incoterm(payload: dict, incoterm: str) -> dict:
    return {**payload, "customs": {"commodities": [], "incoterm": incoterm}}


_shipper_de = {**_shipper, "city": "Berlin", "postal_code": "10115", "country_code": "DE"}

_recipient_krakow = {
    "person_name": "Jan Kowalski",
    "address_line1": "ul. Królewska 10",
    "city": "Kraków",
    "postal_code": "30-079",
    "country_code": "PL",
    "phone_number": "+48 600 000 000",
    "email": "jan.kowalski@example.pl",
}

_parcel_pl = {
    "weight": 1.0,
    "width": 20.0,
    "height": 10.0,
    "length": 30.0,
    "weight_unit": "KG",
    "dimension_unit": "CM",
    "reference_number": "REF-TEST-1",
}

_parcel_shop_krakow = {
    "dhl_freight_sweden_service_point": "8005-PL-4507446",
    "dhl_freight_sweden_service_point_type": "ParcelShop",
    "dhl_freight_sweden_service_point_name": "DHL Parcelshop",
    "dhl_freight_sweden_service_point_street": "Al. Kijowska 57/LU5",
    "dhl_freight_sweden_service_point_city": "KRAKÓW",
    "dhl_freight_sweden_service_point_postal_code": "30-079",
    "dhl_freight_sweden_service_point_country_code": "PL",
}


def _pl_payload(service: str, options: typing.Optional[dict] = None) -> dict:
    return {
        "service": service,
        "shipper": _shipper,
        "recipient": _recipient_krakow,
        "parcels": [_parcel_pl],
        "options": {"dhl_freight_sweden_sent_free": True, **(options or {})},
    }


ShipmentPayload109ParcelShopPL = _pl_payload(
    "dhl_freight_sweden_parcel_connect_b2c", _parcel_shop_krakow
)
ShipmentPayload112PL = _pl_payload("dhl_freight_sweden_parcel_connect_plus")
_parcel_connect = _pl_payload("dhl_freight_sweden_parcel_connect_b2c")
_parcel_connect_plus = ShipmentPayload112PL

ShipmentRequest112PL = {
    "additionalServices": {},
    "parties": [
        {
            "address": {
                "cityName": "Stockholm",
                "countryCode": "SE",
                "postalCode": "11143",
                "street": "Kungsgatan 1",
            },
            "contactName": "Sven Svensson",
            "email": "shipper@example.se",
            "id": "1234567",
            "name": "Test Shipper AB",
            "phone": "+46 8 123 456",
            "type": "Consignor",
        },
        {
            "address": {
                "cityName": "Kraków",
                "countryCode": "PL",
                "postalCode": "30-079",
                "street": "ul. Królewska 10",
            },
            "contactName": "Jan Kowalski",
            "email": "jan.kowalski@example.pl",
            "name": "Jan Kowalski",
            "phone": "+48 600 000 000",
            "type": "Consignee",
        },
    ],
    "payerCode": {"code": "023"},
    "pieces": [
        {
            "height": 10.0,
            "length": 30.0,
            "marksAndNumbers": "REF-TEST-1",
            "numberOfPieces": 1,
            "volume": 0.01,
            "weight": 1.0,
            "width": 20.0,
        }
    ],
    "productCode": "112",
    "totalNumberOfPieces": 1,
    "totalWeight": 1.0,
    "additionalInformation": [{"code": "SENT_FREE", "stringValue": "true"}],
}

ShipmentRequest109PL = {
    **ShipmentRequest112PL,
    "parties": [
        *ShipmentRequest112PL["parties"],
        {
            "id": "8005-PL-4507446",
            "type": "AccessPoint",
            "subType": "ParcelShop",
            "name": "DHL Parcelshop",
            "address": {
                "street": "Al. Kijowska 57/LU5",
                "cityName": "KRAKÓW",
                "postalCode": "30-079",
                "countryCode": "PL",
            },
        },
    ],
    "payerCode": {"code": "022"},
    "productCode": "109",
}


if __name__ == "__main__":
    unittest.main()
