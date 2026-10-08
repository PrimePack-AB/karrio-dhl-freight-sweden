"""DHL Freight (SE API Farm) SENT additionalInformation tests.

Lanes to or from PL carry SENT entries under the shipment's
additionalInformation: SENT_FREE "false" with SENT_REF and SENT_CARKEY, or
SENT_FREE "true" (product manual v5.26 §5.4 p23). The sandbox rejected 109
to PL with neither identifier nor SENT_FREE "true" on 2026-10-05 (validation
error 22001, fixtures/sandbox/rejection-22001-109-se-pl-without-sent.json)
and accepted the same request on 2026-10-08
(fixtures/sandbox/booking-2906769613-109-se-pl-without-sent.json). Without
either identifier, the connector declares the shipment SENT free.
"""

import typing
import unittest

import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import SentInformationError

from .fixture import detail_keys, gateway, serialize_request
from .test_shipment import _payload, _recipient_dk, _recipient_pl, _recipient_se


class TestDHLFreightSent(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _serialize(self, payload: dict) -> dict:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        return serialize_request(request)

    def _error(self, payload: dict) -> SentInformationError:
        with self.assertRaises(SentInformationError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def test_lanes_to_and_from_pl_without_sent_declaration_send_sent_free(self):
        cases = [
            ("to PL", _parcel_connect(_recipient_pl)),
            ("from PL", {**_parcel_connect(_recipient_se), "shipper": _shipper_pl}),
            ("dangerous goods", _parcel_connect(_recipient_pl, {"dangerous_good": True})),
        ]

        for lane, payload in cases:
            with self.subTest(lane=lane):
                serialized = self._serialize(payload)

                self.assertEqual(serialized["additionalInformation"], [SentFree])

    def test_lane_to_pl_without_sent_declaration_at_500_kg_and_above_sends_sent_free(self):
        for weight in [500.0, 1200.0]:
            with self.subTest(weight=weight):
                serialized = self._serialize(
                    {
                        **_parcel_connect(_recipient_pl),
                        "parcels": [{"weight": weight, "weight_unit": "KG"}],
                    }
                )

                self.assertEqual(serialized["additionalInformation"], [SentFree])

    def test_lane_from_pl_with_explicit_sent_free_is_sent(self):
        serialized = self._serialize(
            {
                **_parcel_connect(_recipient_se, {"dhl_freight_sweden_sent_free": True}),
                "shipper": _shipper_pl,
            }
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

        self.assertEqual(serialized["additionalInformation"], SentIdentified)

    def test_sent_free_false_with_identifiers(self):
        serialized = self._serialize(
            _parcel_connect(
                _recipient_pl,
                {
                    "dhl_freight_sweden_sent_free": False,
                    "dhl_freight_sweden_sent_ref": "123456789A",
                    "dhl_freight_sweden_sent_carkey": "82727166666",
                },
            )
        )

        self.assertEqual(serialized["additionalInformation"], SentIdentified)

    def test_sent_reference_without_carrier_key_fails(self):
        error = self._error(
            _parcel_connect(_recipient_pl, {"dhl_freight_sweden_sent_ref": "123456789A"})
        )

        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_sent_carkey"})
        self.assertIn("dhl_freight_sweden_sent_carkey", str(error))

    def test_sent_free_with_identifiers_fails(self):
        cases = [
            {"dhl_freight_sweden_sent_ref": "123456789A"},
            {"dhl_freight_sweden_sent_carkey": "82727166666"},
            {
                "dhl_freight_sweden_sent_ref": "123456789A",
                "dhl_freight_sweden_sent_carkey": "82727166666",
            },
        ]

        for identifiers in cases:
            with self.subTest(identifiers=sorted(identifiers)):
                error = self._error(
                    _parcel_connect(
                        _recipient_pl,
                        {"dhl_freight_sweden_sent_free": True, **identifiers},
                    )
                )

                self.assertEqual(
                    detail_keys(error),
                    {"dhl_freight_sweden_sent_free", *identifiers},
                )

    def test_sent_free_false_without_identifiers_fails(self):
        error = self._error(
            _parcel_connect(_recipient_pl, {"dhl_freight_sweden_sent_free": False})
        )

        self.assertEqual(
            detail_keys(error),
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

        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_sent_ref"})

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


def _parcel_connect(recipient: dict, options: typing.Optional[dict] = None) -> dict:
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
SentIdentified = [
    {"code": "SENT_FREE", "stringValue": "false"},
    {"code": "SENT_REF", "stringValue": "123456789A"},
    {"code": "SENT_CARKEY", "stringValue": "82727166666"},
]


if __name__ == "__main__":
    unittest.main()
