"""Sandbox segment ``booking-approved``: DHL-approved TransportInstruction products.

Each test books one shipment and prints its label: 102 (SE domestic),
601 (SE to DK), and 118 (SE home delivery behind the ``enforce`` postal-code
pre-flight). Bookings count against ``DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS``
and cannot be cancelled through the API.
"""

import unittest

from . import booking, harness

SE_RECIPIENT = {
    "person_name": "Anna Andersson",
    "address_line1": "Drottninggatan 10",
    "city": "Stockholm",
    "postal_code": "11151",
    "country_code": "SE",
    "phone_number": "+46 70 123 45 67",
    "email": "anna.andersson@example.se",
    "residential": True,
}
DK_RECIPIENT = {
    "person_name": "Mette Hansen",
    "address_line1": "Vesterbrogade 10",
    "city": "København V",
    "postal_code": "1620",
    "country_code": "DK",
    "phone_number": "+45 20 12 34 56",
    "email": "mette.hansen@example.dk",
    "residential": True,
}


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
                recipient=SE_RECIPIENT,
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
                recipient=DK_RECIPIENT,
                parcels=[booking.PARCEL],
                options=dict(dhl_freight_sweden_payer_code="DAP"),
            ),
        )

    def test_book_118_home_delivery_enforced(self):
        booking.require_product(self, self.session, "118")
        enforce_gateway = self.session.gateway(dict(address_validation="enforce"))

        booking.book(
            self,
            self.session,
            enforce_gateway,
            "118",
            dict(
                service="118",
                shipper=booking.SHIPPER,
                recipient=SE_RECIPIENT,
                parcels=[booking.PARCEL],
            ),
        )
