"""Sandbox segment ``booking-probes``: one-off mutated bookings, each answering
a single question and spending a booking only when this segment is named.

The access-point phone probe books the same 103 SE service-point payload as
``booking-pudo`` and adds a ``phone`` to the serialized AccessPoint party via
``harness.mutated_request``, to learn whether the Print API then prints it on
the label's ``Phn.`` line. Unlike ``rejections``, the probe asserts DHL
accepts and returns a label; a failure is the finding, and the outcome is
recorded once, never retried.
"""

import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.dhl_freight_sweden.units as provider_units
from . import booking, harness

# Sandbox-only placeholder within the phone format of product manual v5.26
# Appendix E §10.6 p197 (one +46 prefix, digits, and spaces); its digits
# echo terminal id 9820 for traceability, and it belongs to no real
# service point.
ACCESS_POINT_PHONE = "+46 8 982 000"


def with_access_point_phone(phone: str) -> typing.Callable[[dict], dict]:
    """A mutation adding ``phone`` to the instruction's AccessPoint parties."""

    def mutate(instruction: dict) -> dict:
        return {
            **instruction,
            "parties": [
                {**party, "phone": phone}
                if party.get("type") == provider_units.PartyType.AccessPoint.value
                else party
                for party in instruction.get("parties") or []
            ],
        }

    return mutate


def book_mutated(
    test: unittest.TestCase,
    session: harness.Session,
    gateway,
    label: str,
    product: str,
    payload: dict,
    mutate: typing.Callable[[dict], dict],
) -> models.ShipmentDetails:
    """Send ``payload`` mutated by ``mutate`` once and assert a labelled shipment.

    The attempt counts against the booking budget and is logged to
    ``bookings.jsonl`` whether or not DHL returns a shipment id, because
    sandbox bookings cannot be cancelled through the API. A rejection fails
    the test carrying DHL's messages: the probe records the outcome once.
    """
    booking.require_booking(
        test, session, product, str(payload["recipient"]["country_code"]).upper()
    )
    request = gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
    mutated = harness.mutated_request(request, mutate)
    if not session.budget.reserve():
        test.skipTest("booking budget exhausted")

    shipment: typing.Optional[models.ShipmentDetails] = None
    messages: typing.List[models.Message] = []
    try:
        shipment, messages = gateway.mapper.parse_shipment_response(
            gateway.proxy.create_shipment(mutated)
        )
    finally:
        session.log_booking(
            product, shipment.tracking_number if shipment else None, test.id()
        )
        session.capture(gateway, label)
        session.capture_parsed(
            label,
            dict(
                tracking_number=shipment.tracking_number if shipment else None,
                label_type=shipment.label_type if shipment else None,
                label_length=len(shipment.docs.label or "") if shipment else 0,
                messages=lib.to_dict(messages),
            ),
        )

    errors = [m for m in messages if m.level not in ("warning", "info")]
    test.assertEqual(lib.to_dict(errors), [])
    assert shipment is not None
    test.assertTrue(shipment.tracking_number)
    test.assertEqual(shipment.shipment_identifier, shipment.tracking_number)
    test.assertTrue(shipment.docs.label)
    return shipment


class TestSandboxBookingProbes(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment("booking-probes")
        cls.gateway = cls.session.gateway()

    def setUp(self):
        self.maxDiff = None

    def test_book_103_service_point_access_point_phone(self):
        booking.require_booking(self, self.session, "103", "SE")
        recipient = booking.RECIPIENTS["SE"]
        point, messages = booking.nearest_service_point(
            self.session,
            self.gateway,
            "service-points-103-access-point-phone",
            "103",
            recipient,
        )

        self.assertEqual(lib.to_dict(messages), [])
        if point is None:
            self.fail(f"no service point candidate for 103 near {recipient['city']}")

        book_mutated(
            self,
            self.session,
            self.gateway,
            "booking-103-access-point-phone",
            "103",
            dict(
                service="103",
                shipper=booking.SHIPPER,
                recipient=recipient,
                parcels=[booking.PARCEL],
                options=booking.service_point_options(point),
            ),
            with_access_point_phone(ACCESS_POINT_PHONE),
        )
