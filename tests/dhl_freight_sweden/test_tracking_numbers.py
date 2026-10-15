"""Per-parcel tracking numbers parsed from the booking response.

The karrio server writes ``meta.tracking_numbers[i]`` into parcel ``i``'s
``reference_number`` (karrio fork modules/core/karrio/server/core/
gateway.py), so a multi-parcel booking lists the response's piece ids, one
per parcel, positionally. Booking 2906788993 answered one
``transportInstruction.pieces[]`` row per parcel in request order, each with
a single-element id list (tests/dhl_freight_sweden/fixtures/sandbox/
booking-2906788993-102-se-se-two-parcels.json); the connector keeps the
transport instruction id whenever the flattened id count disagrees with the
parcel count, and single-parcel bookings always keep it.
"""

import copy
import json
import pathlib
import typing
import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio

from .fixture import gateway
from .test_shipment import _parcel, _payload, _recipient_se

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "sandbox"
TwoParcelBooking = json.loads(
    (FIXTURES / "booking-2906788993-102-se-se-two-parcels.json").read_text()
)
# A single-parcel 102 booking whose response also lists one piece row with
# a single-element id list, so its piece id must not reach tracking_numbers.
SingleParcelBooking = json.loads(
    (FIXTURES / "booking-2906761222-102-se-se.json").read_text()
)

TwoParcelPayload = {
    **_payload("dhl_freight_sweden_paket", _recipient_se),
    "parcels": [
        {**_parcel, "reference_number": "SANDBOX-PIECE-1"},
        {**_parcel, "reference_number": "SANDBOX-PIECE-2"},
    ],
}


def _responses(
    fixture: dict,
    mutate: typing.Optional[typing.Callable[[dict], None]] = None,
):
    """JSON bodies for mocked ``lib.request`` calls, from a booking fixture."""
    document = copy.deepcopy(fixture)
    if mutate is not None:
        mutate(document)
    return [lib.to_json(exchange["response"]) for exchange in document["exchanges"]]


def _drop_second_piece_id(document: dict) -> None:
    pieces = document["exchanges"][0]["response"]["transportInstruction"]["pieces"]
    pieces[1].pop("id")


def _extra_id_on_first_piece(document: dict) -> None:
    pieces = document["exchanges"][0]["response"]["transportInstruction"]["pieces"]
    pieces[0]["id"] = [*pieces[0]["id"], "373221512525060866"]


class TestPerParcelTrackingNumbers(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _parse(self, payload: dict, responses: typing.List[str]):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.side_effect = responses
            return (
                karrio.Shipment.create(models.ShipmentRequest(**payload))
                .from_(gateway)
                .parse()
            )

    def test_two_parcel_booking_lists_piece_ids_per_parcel(self):
        details, messages = self._parse(TwoParcelPayload, _responses(TwoParcelBooking))

        self.assertEqual(messages, [])
        assert details is not None
        self.assertEqual(details.tracking_number, "2906788993")
        self.assertEqual(details.shipment_identifier, "2906788993")
        self.assertEqual(
            details.meta["tracking_numbers"],
            ["373221512525060842", "373221512525060859"],
        )
        self.assertEqual(details.meta["shipment_identifiers"], ["2906788993"])
        self.assertEqual(
            details.docs.label,
            TwoParcelBooking["exchanges"][1]["response"]["reports"][0]["content"],
        )

    def test_piece_id_count_mismatch_keeps_transport_instruction_id(self):
        for mutate in [_drop_second_piece_id, _extra_id_on_first_piece]:
            with self.subTest(mutate=mutate.__name__):
                details, messages = self._parse(
                    TwoParcelPayload, _responses(TwoParcelBooking, mutate)
                )

                self.assertEqual(messages, [])
                assert details is not None
                self.assertEqual(details.tracking_number, "2906788993")
                self.assertEqual(
                    details.meta["tracking_numbers"], ["2906788993"]
                )

    def test_single_parcel_booking_keeps_transport_instruction_id(self):
        details, messages = self._parse(
            _payload("dhl_freight_sweden_paket", _recipient_se),
            _responses(SingleParcelBooking),
        )

        self.assertEqual(messages, [])
        assert details is not None
        self.assertEqual(details.tracking_number, "2906761222")
        self.assertEqual(details.meta["tracking_numbers"], ["2906761222"])
