"""DHL Freight (SE API Farm) customs information required outside the EU VAT area.

A booking whose shipper or recipient lies outside the EU VAT area for goods
needs customs data: commodities, an invoice number, or an invoice date.
The connector refuses such a booking without customs data before it sends
any request; the check is the connector's own, not a DHL rejection.
"""

import typing
import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.sdk as karrio
from karrio.providers.dhl_freight_sweden.shipment.create import (
    AlandCustomsServiceError,
    CustomsInformationRequiredError,
    ExcludedDestinationError,
)

from .fixture import detail_keys, gateway, serialize_request
from .test_shipment import Customs, _payload, _recipient_de, _recipient_no, _recipient_se

ROAD_FREIGHT_STANDARD = "dhl_freight_sweden_road_freight_standard"
ROAD_FREIGHT_DIRECT = "dhl_freight_sweden_road_freight_direct"
PARCEL_CONNECT = "dhl_freight_sweden_parcel_connect_b2c"
PAKET = "dhl_freight_sweden_paket"
DAP = {"dhl_freight_sweden_payer_code": "DAP"}
ALAND_PARCEL_SHOP = {
    "dhl_freight_sweden_service_point": "8011-221003201",
    "dhl_freight_sweden_service_point_type": "ParcelShop",
    "dhl_freight_sweden_service_point_name": "c/o Posti",
    "dhl_freight_sweden_service_point_street": "Nygatan 6",
    "dhl_freight_sweden_service_point_city": "Mariehamn",
    "dhl_freight_sweden_service_point_postal_code": "22100",
    "dhl_freight_sweden_service_point_country_code": "FI",
}


def _recipient(country: str, postal_code: str) -> dict:
    return {**_recipient_se, "city": "City", "country_code": country, "postal_code": postal_code}


def _with_customs(payload: dict, customs: typing.Optional[dict]) -> dict:
    return {**payload, **({"customs": customs} if customs is not None else {})}


def _serialized(payload: dict) -> dict:
    return serialize_request(
        gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
    )


class TestDHLFreightCustomsInformationRequired(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _refusal(self, payload: dict) -> CustomsInformationRequiredError:
        with self.assertRaises(CustomsInformationRequiredError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def test_export_outside_eu_vat_area_without_customs_sends_no_request(self):
        payload = _payload(ROAD_FREIGHT_STANDARD, _recipient_no, DAP)

        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            details, messages = (
                karrio.Shipment.create(models.ShipmentRequest(**payload))
                .from_(gateway)
                .parse()
            )

        mock.assert_not_called()
        self.assertIsNone(details)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].code, "SHIPPING_SDK_FIELD_ERROR")
        self.assertEqual(set(messages[0].details), {"customs"})
        self.assertIn("SE 11143 to NO", messages[0].message)
        self.assertIn("the connector refuses the booking before sending it", messages[0].message)

    def test_customs_without_customs_data_is_refused(self):
        cases = {
            "incoterm and duty only": {
                "commodities": [],
                "incoterm": "DAP",
                "duty": {"paid_by": "sender", "currency": "EUR", "declared_value": 100.0},
            },
            "documents without invoice": {"commodities": [], "content_type": "documents"},
        }
        for case, customs in cases.items():
            with self.subTest(case=case):
                error = self._refusal(
                    _with_customs(_payload(ROAD_FREIGHT_STANDARD, _recipient_no, DAP), customs)
                )

                self.assertEqual(detail_keys(error), {"customs"})
                self.assertIn("customs.invoice", str(error))

    def test_documents_with_invoice_number_book_with_customs_information(self):
        serialized = _serialized(
            _with_customs(
                _payload(ROAD_FREIGHT_STANDARD, _recipient_no, DAP),
                {"commodities": [], "content_type": "documents", "invoice": "DOC-1"},
            )
        )

        document = serialized["customsInformation"]["customsDocuments"][0]
        self.assertEqual((document["id"], document["type"]), ("DOC-1", "ProformaInvoice"))

    def test_export_with_commodities_books_with_customs_information(self):
        serialized = _serialized(_with_customs(_payload(ROAD_FREIGHT_STANDARD, _recipient_no), Customs))

        self.assertEqual(len(serialized["customsInformation"]["customsCommodities"]), 1)

    def test_import_from_outside_eu_vat_area_without_customs_is_refused(self):
        payload = {
            **_payload(ROAD_FREIGHT_STANDARD, _recipient_se, {"dhl_freight_sweden_payer_code": "EXW"}),
            "shipper": {**_recipient_no, "company_name": "Shipper AS"},
        }

        self.assertIn("from NO 0154 to SE", str(self._refusal(payload)))

    def test_lanes_inside_eu_vat_area_book_without_customs(self):
        cases = {
            "domestic": _payload(PAKET, _recipient_se),
            "intra-EU": _payload(ROAD_FREIGHT_STANDARD, _recipient_de, DAP),
            "Northern Ireland": _payload(ROAD_FREIGHT_STANDARD, _recipient("GB", "BT1 1AA"), DAP),
        }
        for case, payload in cases.items():
            with self.subTest(case=case):
                serialized = _serialized(payload)

                self.assertNotIn("customsInformation", serialized)

    def test_canary_islands_require_customs(self):
        for country in ("ES", "IC"):
            with self.subTest(country=country):
                payload = _payload(ROAD_FREIGHT_DIRECT, _recipient(country, "35001"), DAP)

                self._refusal(payload)
                self.assertIn(
                    "customsInformation", _serialized(_with_customs(payload, Customs))
                )

    def test_aland_requires_customs(self):
        for country in ("FI", "AX"):
            with self.subTest(country=country):
                error = self._refusal(
                    _payload(PARCEL_CONNECT, _recipient(country, "22100"), ALAND_PARCEL_SHOP)
                )

                self.assertIn("to FI 22100", str(error))

    def test_aland_with_customs_and_no_customs_service_books(self):
        serialized = _serialized(
            _with_customs(
                _payload(PARCEL_CONNECT, _recipient("FI", "22100"), ALAND_PARCEL_SHOP),
                Customs,
            )
        )

        self.assertIn("customsInformation", serialized)
        self.assertFalse(
            {"customsHandlingStandard", "customsHandlingFullService"}
            & set(serialized.get("additionalServices") or {})
        )

    def test_destination_refusals_are_reported_first(self):
        cases = {
            ExcludedDestinationError: _payload(
                PARCEL_CONNECT, _recipient("ES", "35001"), ALAND_PARCEL_SHOP
            ),
            AlandCustomsServiceError: _payload(
                ROAD_FREIGHT_DIRECT,
                _recipient("FI", "22100"),
                {**DAP, "dhl_freight_sweden_customs_handling_full_service": True},
            ),
        }
        for error_type, payload in cases.items():
            with self.subTest(error=error_type.__name__):
                with self.assertRaises(error_type):
                    gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))


if __name__ == "__main__":
    unittest.main()
