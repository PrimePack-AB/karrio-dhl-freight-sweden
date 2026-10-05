"""Sandbox segment ``booking-pudo``: service point lookup chained into a booking.

Each test finds the service points nearest the recipient, picks the first
candidate with an id, a complete address, and a sub type the connector accepts
for the destination, and books it as the AccessPoint party: 103 within SE,
109 from SE to PL (payer code 022, SENT free).
"""

import unittest

import karrio.lib as lib
from . import booking, harness


class TestSandboxBookingPudo(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment("booking-pudo")
        cls.gateway = cls.session.gateway()

    def setUp(self):
        self.maxDiff = None

    def nearest_point(self, label: str, product: str, recipient: dict) -> dict:
        point, messages = booking.nearest_service_point(
            self.session, self.gateway, label, product, recipient
        )

        self.assertEqual(lib.to_dict(messages), [])
        if point is None:
            self.fail(f"no service point candidate for {product} near {recipient['city']}")
        return point

    def test_book_103_service_point_se(self):
        booking.require_booking(self, self.session, "103", "SE")
        point = self.nearest_point("service-points-103-se", "103", booking.RECIPIENTS["SE"])

        booking.book(
            self,
            self.session,
            self.gateway,
            "103",
            dict(
                service="103",
                shipper=booking.SHIPPER,
                recipient=booking.RECIPIENTS["SE"],
                parcels=[booking.PARCEL],
                options=booking.service_point_options(point),
            ),
        )

    def test_book_109_service_point_pl(self):
        booking.require_booking(self, self.session, "109", "PL")
        point = self.nearest_point("service-points-109-pl", "109", booking.RECIPIENTS["PL"])

        booking.book(
            self,
            self.session,
            self.gateway,
            "109",
            dict(
                service="109",
                shipper=booking.SHIPPER,
                recipient=booking.RECIPIENTS["PL"],
                parcels=[booking.PARCEL],
                options=dict(
                    **booking.service_point_options(point),
                    **booking.SENT_FREE,
                    dhl_freight_sweden_payer_code="022",
                ),
            ),
        )
