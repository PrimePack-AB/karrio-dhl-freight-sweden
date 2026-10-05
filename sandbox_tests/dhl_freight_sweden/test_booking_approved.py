"""Sandbox segment ``booking-approved``: DHL-approved TransportInstruction products.

Each test books one shipment and prints its label: 102 (SE domestic),
601 (SE to DK), and 118 (SE home delivery behind the ``enforce`` postal-code
pre-flight). Bookings count against ``DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS``
and cannot be cancelled through the API.
"""

import unittest

from . import booking, harness


class TestSandboxBookingApproved(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment("booking-approved")
        cls.gateway = cls.session.gateway()

    def setUp(self):
        self.maxDiff = None

    def test_book_102_domestic(self):
        booking.book(
            self,
            self.session,
            self.gateway,
            "102",
            dict(
                service="102",
                shipper=booking.SHIPPER,
                recipient=booking.RECIPIENTS["SE"],
                parcels=[booking.PARCEL],
            ),
        )

    def test_book_601_to_dk(self):
        booking.book(
            self,
            self.session,
            self.gateway,
            "601",
            dict(
                service="601",
                shipper=booking.SHIPPER,
                recipient=booking.RECIPIENTS["DK"],
                parcels=[booking.PARCEL],
                options=dict(dhl_freight_sweden_payer_code="DAP"),
            ),
        )

    def test_book_118_home_delivery_enforced(self):
        booking.require_booking(self, self.session, "118", "SE")
        enforce_gateway = self.session.gateway(dict(address_validation="enforce"))

        booking.book(
            self,
            self.session,
            enforce_gateway,
            "118",
            dict(
                service="118",
                shipper=booking.SHIPPER,
                recipient=booking.RECIPIENTS["SE"],
                parcels=[booking.PARCEL],
            ),
        )
