"""DHL Freight (SE API Farm) SENT additionalInformation tests.

Lanes to or from PL carry SENT entries under the shipment's
additionalInformation: SENT_REF with SENT_CARKEY (product manual v5.23
§5.4 p19), otherwise SENT_FREE "true", which the live API requires when
neither identifier is sent (validation error 22001, sandbox 2026-10-05).
"""

import unittest

import karrio.lib as lib
import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import SentInformationError

from .fixture import gateway
from .test_shipment import _payload, _recipient_dk, _recipient_pl, _recipient_se


class TestDHLFreightSent(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _serialize(self, payload: dict) -> dict:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        return lib.to_dict(request.serialize())

    def _error(self, payload: dict) -> SentInformationError:
        with self.assertRaises(SentInformationError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def test_pl_lane_defaults_to_sent_free(self):
        serialized = self._serialize(_parcel_connect(_recipient_pl))

        self.assertEqual(serialized["additionalInformation"], [SentFree])

    def test_lane_from_pl_defaults_to_sent_free(self):
        serialized = self._serialize(
            {**_parcel_connect(_recipient_se), "shipper": _shipper_pl}
        )

        self.assertEqual(serialized["additionalInformation"], [SentFree])

    def test_explicit_sent_free_is_sent(self):
        serialized = self._serialize(
            _parcel_connect(_recipient_pl, {"dhl_freight_sweden_sent_free": True})
        )

        self.assertEqual(serialized["additionalInformation"], [SentFree])

    def test_sent_reference_and_carrier_key(self):
        serialized = self._serialize(
            _parcel_connect(
                _recipient_pl,
                {
                    "dhl_freight_sweden_sent_ref": "123456789A",
                    "dhl_freight_sweden_sent_carkey": "82727166666",
                },
            )
        )

        self.assertEqual(
            serialized["additionalInformation"],
            [
                {"code": "SENT_REF", "stringValue": "123456789A"},
                {"code": "SENT_CARKEY", "stringValue": "82727166666"},
            ],
        )

    def test_sent_reference_without_carrier_key_fails(self):
        error = self._error(
            _parcel_connect(_recipient_pl, {"dhl_freight_sweden_sent_ref": "123456789A"})
        )

        self.assertEqual(set(error.details), {"dhl_freight_sweden_sent_carkey"})
        self.assertIn("dhl_freight_sweden_sent_carkey", str(error))

    def test_sent_free_false_without_identifiers_fails(self):
        error = self._error(
            _parcel_connect(_recipient_pl, {"dhl_freight_sweden_sent_free": False})
        )

        self.assertEqual(
            set(error.details),
            {"dhl_freight_sweden_sent_ref", "dhl_freight_sweden_sent_carkey"},
        )

    def test_sent_value_over_twenty_characters_fails(self):
        error = self._error(
            _parcel_connect(
                _recipient_pl,
                {
                    "dhl_freight_sweden_sent_ref": "X" * 21,
                    "dhl_freight_sweden_sent_carkey": "82727166666",
                },
            )
        )

        self.assertEqual(set(error.details), {"dhl_freight_sweden_sent_ref"})

    def test_dangerous_good_without_sent_choice_fails(self):
        error = self._error(_parcel_connect(_recipient_pl, {"dangerous_good": True}))

        self.assertEqual(set(error.details), {"dhl_freight_sweden_sent_free"})

    def test_dangerous_good_with_explicit_sent_free_is_sent(self):
        serialized = self._serialize(
            _parcel_connect(
                _recipient_pl,
                {"dangerous_good": True, "dhl_freight_sweden_sent_free": True},
            )
        )

        self.assertEqual(serialized["additionalInformation"], [SentFree])

    def test_non_pl_lane_sends_no_sent_entries(self):
        serialized = self._serialize(
            _parcel_connect(
                _recipient_dk,
                {
                    "dhl_freight_sweden_sent_free": True,
                    "dhl_freight_sweden_sent_ref": "123456789A",
                },
            )
        )

        self.assertNotIn("additionalInformation", serialized)


def _parcel_connect(recipient: dict, options: dict = None) -> dict:
    return _payload("dhl_freight_sweden_parcel_connect_b2c", recipient, options)


_shipper_pl = {
    "company_name": "Test Shipper Sp. z o.o.",
    "person_name": "Jan Kowalski",
    "address_line1": "ul. Królewska 10",
    "city": "Kraków",
    "postal_code": "30-079",
    "country_code": "PL",
    "phone_number": "+48 600 000 000",
    "email": "jan.kowalski@example.pl",
}

SentFree = {"code": "SENT_FREE", "stringValue": "true"}


if __name__ == "__main__":
    unittest.main()
