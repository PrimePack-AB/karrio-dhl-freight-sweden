"""Sandbox segment ``booking-declarations``: EKAER and UIT declarations on 601.

Each test books 601 (payer code DAP) from SE with a declaration that is not
free: to HU with an EKAER number, which sends ``EKAER_FREE`` "false" and
``EKAER_NUMBER``, and to RO with ``dhl_freight_sweden_uit_free`` false and
no number, which sends ``UIT_FREE`` "false" alone. Before spending a booking
it checks for free that product matches offer 601 for the lane, and skips
otherwise.
"""

import unittest

from . import booking, harness

PRODUCT = "601"
# Sandbox-only placeholder within the EKAER number format (AN..20); it is
# not issued by the Hungarian tax authority.
EKAER_NUMBER = "E0000SANDBOX0001"
DECLARATIONS = {
    "HU": {"dhl_freight_sweden_ekaer_number": EKAER_NUMBER},
    "RO": {"dhl_freight_sweden_uit_free": False},
}


class TestSandboxBookingDeclarations(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment("booking-declarations")
        cls.gateway = cls.session.gateway()

    def setUp(self):
        self.maxDiff = None

    def declare(self, country: str):
        booking.require_booking(self, self.session, PRODUCT, country)
        recipient = booking.RECIPIENTS[country]

        codes, messages = booking.offered_products(
            self.session,
            self.gateway,
            f"product-matches-{PRODUCT}-{country.lower()}",
            recipient,
        )
        if messages:
            self.skipTest(
                f"product matches pre-check for SE to {country} failed: "
                f"{[message.message for message in messages]}"
            )
        if PRODUCT not in codes:
            self.skipTest(f"product matches do not offer {PRODUCT} from SE to {country}")

        booking.book(
            self,
            self.session,
            self.gateway,
            PRODUCT,
            dict(
                service=PRODUCT,
                shipper=booking.SHIPPER,
                recipient=recipient,
                parcels=[booking.PARCEL],
                options={
                    "dhl_freight_sweden_payer_code": "DAP",
                    **DECLARATIONS[country],
                },
            ),
        )

    def test_book_601_hu_with_ekaer_number(self):
        self.declare("HU")

    def test_book_601_ro_not_uit_free_without_number(self):
        self.declare("RO")
