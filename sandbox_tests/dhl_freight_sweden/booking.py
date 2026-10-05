"""Shared sandbox booking step: budget, live booking, capture, and assertions."""

import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio
from . import harness

SHIPPER = {
    "company_name": "Test Shipper AB",
    "person_name": "Sven Svensson",
    "address_line1": "Kungsgatan 1",
    "city": "Stockholm",
    "postal_code": "11143",
    "country_code": "SE",
    "phone_number": "+46 8 123 456",
    "email": "shipper@example.se",
}

PARCEL = {
    "weight": 1.0,
    "length": 30.0,
    "width": 20.0,
    "height": 10.0,
    "weight_unit": "KG",
    "dimension_unit": "CM",
    "reference_number": "SANDBOX-TEST",
}


def require_product(test: unittest.TestCase, session: harness.Session, product: str) -> None:
    """Skip unless ``product`` is selected and a booking attempt remains."""
    reason = harness.product_skip_reason(session.config, product)
    if reason:
        test.skipTest(reason)
    if session.budget.attempts >= session.budget.limit:
        test.skipTest(
            f"booking budget exhausted ({session.budget.attempts} of "
            f"DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS={session.budget.limit} used)"
        )


def book(
    test: unittest.TestCase,
    session: harness.Session,
    gateway,
    product: str,
    payload: dict,
) -> models.ShipmentDetails:
    """Book ``payload`` once within the budget and assert a labelled shipment.

    The attempt is reserved before the call and logged to ``bookings.jsonl``
    whether or not DHL returns a shipment id, because sandbox bookings
    cannot be cancelled through the API.
    """
    require_product(test, session, product)
    if not session.budget.reserve():
        test.skipTest("booking budget exhausted")

    shipment: typing.Optional[models.ShipmentDetails] = None
    messages: typing.List[models.Message] = []
    try:
        shipment, messages = (
            karrio.Shipment.create(models.ShipmentRequest(**payload))
            .from_(gateway)
            .parse()
        )
    finally:
        session.log_booking(
            product, shipment.tracking_number if shipment else None, test.id()
        )
        session.capture(gateway, f"booking-{product}")
        session.capture_parsed(
            f"booking-{product}",
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
