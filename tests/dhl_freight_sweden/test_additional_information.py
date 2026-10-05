"""DHL Freight (SE API Farm) pass-through additionalInformation tests."""

import unittest

import karrio.lib as lib
import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import (
    AdditionalInformationError,
)

from .fixture import gateway
from .test_shipment import _payload, _recipient_pl, _recipient_se


class TestDHLFreightAdditionalInformation(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _serialize(self, payload: dict) -> dict:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        return lib.to_dict(request.serialize())

    def _error(self, payload: dict) -> AdditionalInformationError:
        with self.assertRaises(AdditionalInformationError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def test_entries_are_appended_after_sent_entries(self):
        serialized = self._serialize(
            _parcel_connect(
                _recipient_pl,
                {
                    "dhl_freight_sweden_additional_information": [
                        {"code": "CUSTOM_CODE", "stringValue": "value"}
                    ]
                },
            )
        )

        self.assertEqual(
            serialized["additionalInformation"],
            [
                {"code": "SENT_FREE", "stringValue": "true"},
                {"code": "CUSTOM_CODE", "stringValue": "value"},
            ],
        )

    def test_entries_are_sent_on_lanes_without_sent(self):
        serialized = self._serialize(
            _parcel_connect(
                _recipient_hu,
                {
                    "dhl_freight_sweden_additional_information": [
                        {"code": "EKAER_FREE", "stringValue": "true"},
                        {"code": "DATED", "dateValue": "2026-10-05T00:00:00"},
                        {"code": "COUNTED", "numericValue": 2.5},
                    ]
                },
            )
        )

        self.assertEqual(
            serialized["additionalInformation"],
            [
                {"code": "EKAER_FREE", "stringValue": "true"},
                {"code": "DATED", "dateValue": "2026-10-05T00:00:00"},
                {"code": "COUNTED", "numericValue": 2.5},
            ],
        )

    def test_entry_duplicating_a_sent_code_fails(self):
        error = self._error(
            _parcel_connect(
                _recipient_pl,
                {
                    "dhl_freight_sweden_additional_information": [
                        {"code": "SENT_FREE", "stringValue": "false"}
                    ]
                },
            )
        )

        self.assertEqual(
            set(error.details), {"dhl_freight_sweden_additional_information"}
        )
        self.assertIn("SENT_FREE", str(error))

    def test_entry_without_code_fails(self):
        error = self._error(
            _parcel_connect(
                _recipient_hu,
                {"dhl_freight_sweden_additional_information": [{"stringValue": "x"}]},
            )
        )

        self.assertEqual(
            set(error.details), {"dhl_freight_sweden_additional_information"}
        )


def _parcel_connect(recipient: dict, options: dict) -> dict:
    return _payload("dhl_freight_sweden_parcel_connect_b2c", recipient, options)


_recipient_hu = {
    **_recipient_se,
    "city": "Budapest",
    "postal_code": "1051",
    "country_code": "HU",
}


if __name__ == "__main__":
    unittest.main()
