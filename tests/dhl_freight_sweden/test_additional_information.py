"""DHL Freight (SE API Farm) pass-through additionalInformation tests."""

import unittest

import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import (
    AdditionalInformationError,
)

from .fixture import detail_keys, gateway, serialize_request
from .test_shipment import _payload, _recipient_pl, _recipient_se


class TestDHLFreightAdditionalInformation(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _serialize(self, payload: dict) -> dict:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        return serialize_request(request)

    def _error(self, payload: dict) -> AdditionalInformationError:
        with self.assertRaises(AdditionalInformationError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def test_entries_are_appended_after_sent_entries(self):
        serialized = self._serialize(
            _parcel_connect(
                _recipient_pl,
                {
                    "dhl_freight_sweden_sent_free": True,
                    "dhl_freight_sweden_additional_information": [
                        {"code": "CUSTOM_CODE", "stringValue": "value"}
                    ],
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
                        {"code": "CUSTOM_CODE", "stringValue": "value"},
                        {"code": "DATED", "dateValue": "2026-10-05T00:00:00"},
                        {"code": "COUNTED", "numericValue": 2.5},
                    ]
                },
            )
        )

        self.assertEqual(
            serialized["additionalInformation"],
            [
                {"code": "CUSTOM_CODE", "stringValue": "value"},
                {"code": "DATED", "dateValue": "2026-10-05T00:00:00"},
                {"code": "COUNTED", "numericValue": 2.5},
            ],
        )

    def test_entry_duplicating_a_sent_code_fails(self):
        error = self._error(
            _parcel_connect(
                _recipient_pl,
                {
                    "dhl_freight_sweden_sent_free": True,
                    "dhl_freight_sweden_additional_information": [
                        {"code": "SENT_FREE", "stringValue": "false"}
                    ],
                },
            )
        )

        self.assertEqual(
            detail_keys(error), {"dhl_freight_sweden_additional_information"}
        )
        self.assertIn("SENT_FREE", str(error))

    def test_entry_with_a_declaration_code_on_its_lane_fails(self):
        cases = [
            (_recipient_pl, "SENT_FREE"),
            (_recipient_hu, "EKAER_FREE"),
            (_recipient_hu, "EKAER_NUMBER"),
            (_recipient_ro, "UIT_FREE"),
            (_recipient_ro, "UIT_NUMBER"),
        ]

        for recipient, code in cases:
            with self.subTest(code=code):
                error = self._error(
                    _parcel_connect(
                        recipient,
                        {
                            "dhl_freight_sweden_sent_free": True,
                            "dhl_freight_sweden_additional_information": [
                                {"code": code, "stringValue": "true"}
                            ],
                        },
                    )
                )

                self.assertEqual(
                    detail_keys(error), {"dhl_freight_sweden_additional_information"}
                )
                self.assertIn(code, str(error))

    def test_declaration_code_off_its_lane_is_passed_through(self):
        serialized = self._serialize(
            _parcel_connect(
                _recipient_se,
                {
                    "dhl_freight_sweden_additional_information": [
                        {"code": "EKAER_FREE", "stringValue": "true"}
                    ]
                },
            )
        )

        self.assertEqual(
            serialized["additionalInformation"],
            [{"code": "EKAER_FREE", "stringValue": "true"}],
        )

    def test_entry_without_code_fails(self):
        error = self._error(
            _parcel_connect(
                _recipient_hu,
                {"dhl_freight_sweden_additional_information": [{"stringValue": "x"}]},
            )
        )

        self.assertEqual(
            detail_keys(error), {"dhl_freight_sweden_additional_information"}
        )


def _parcel_connect(recipient: dict, options: dict) -> dict:
    return _payload("dhl_freight_sweden_parcel_connect_b2c", recipient, options)


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


if __name__ == "__main__":
    unittest.main()
