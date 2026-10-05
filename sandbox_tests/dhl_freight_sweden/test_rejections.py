"""Sandbox segment ``rejections``: DHL validation errors the connector pre-empts.

Each test builds a valid SE to PL request through the connector, mutates the
serialized TransportInstruction just before sending it, and asserts the DHL
error code: 109 without its SENT entries (22001), 112 with an AccessPoint
party (22015), and 112 with payer code 1 (22020). Each attempt counts
against ``DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS``; a shipment id in a
response is reported as a finding, not a pass.
"""

import unittest

import karrio.lib as lib
from . import booking, harness, rejection


class TestSandboxRejections(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment("rejections")
        cls.gateway = cls.session.gateway()

    def setUp(self):
        self.maxDiff = None

    def nearest_point(self, label: str, product: str) -> dict:
        point, messages = booking.nearest_service_point(
            self.session, self.gateway, label, product, booking.RECIPIENTS["PL"]
        )

        self.assertEqual(lib.to_dict(messages), [])
        if point is None:
            self.skipTest(f"no service point candidate for {product} near Kraków")
        return point

    def payload(self, product: str, options: dict) -> dict:
        return dict(
            service=product,
            shipper=booking.SHIPPER,
            recipient=booking.RECIPIENTS["PL"],
            parcels=[booking.PARCEL],
            options={**booking.SENT_FREE, **options},
        )

    def test_109_pl_without_sent_is_rejected_with_22001(self):
        booking.require_booking(self, self.session, "109", "PL")
        point = self.nearest_point("service-points-rejection-109-pl", "109")

        rejection.reject(
            self,
            self.session,
            self.gateway,
            "rejection-109-pl-without-sent",
            "109",
            self.payload(
                "109",
                {
                    **booking.service_point_options(point),
                    "dhl_freight_sweden_payer_code": "022",
                },
            ),
            rejection.without_sent,
            "22001",
        )

    def test_112_pl_with_access_point_is_rejected_with_22015(self):
        booking.require_booking(self, self.session, "112", "PL")
        point = self.nearest_point("service-points-rejection-112-pl", "109")

        rejection.reject(
            self,
            self.session,
            self.gateway,
            "rejection-112-pl-access-point",
            "112",
            self.payload("112", {}),
            rejection.with_party(rejection.access_point_party(point)),
            "22015",
        )

    def test_112_pl_with_payer_code_1_is_rejected_with_22020(self):
        rejection.reject(
            self,
            self.session,
            self.gateway,
            "rejection-112-pl-payer-code-1",
            "112",
            self.payload("112", {}),
            rejection.with_payer_code("1"),
            "22020",
        )
