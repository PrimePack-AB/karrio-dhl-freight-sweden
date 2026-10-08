"""Sandbox segment ``rejections``: DHL validation errors the connector pre-empts.

Each test builds a valid SE to PL request through the connector, mutates the
serialized TransportInstruction just before sending it, and asserts the DHL
error code: 112 with an AccessPoint party (22015) and 112 with payer code 1
(22020). A 103 request within SE sends its AccessPoint party with the id
only, without name and address, and expects 22001 and 22006. Each attempt
counts against ``DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS``; a shipment id in
a response is reported as a finding, not a pass.
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

    def nearest_point(self, label: str, product: str, country: str = "PL") -> dict:
        recipient = booking.RECIPIENTS[country]
        point, messages = booking.nearest_service_point(
            self.session, self.gateway, label, product, recipient
        )

        self.assertEqual(lib.to_dict(messages), [])
        if point is None:
            self.skipTest(f"no service point candidate for {product} near {recipient['city']}")
        return point

    def payload(self, product: str, options: dict) -> dict:
        return dict(
            service=product,
            shipper=booking.SHIPPER,
            recipient=booking.RECIPIENTS["PL"],
            parcels=[booking.PARCEL],
            options={**booking.SENT_FREE, **options},
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

    def test_103_se_access_point_id_only_is_rejected_with_22001_and_22006(self):
        booking.require_booking(self, self.session, "103", "SE")
        point = self.nearest_point("service-points-rejection-103-se", "103", "SE")

        messages = rejection.reject(
            self,
            self.session,
            self.gateway,
            "rejection-103-se-access-point-id-only",
            "103",
            dict(
                service="103",
                shipper=booking.SHIPPER,
                recipient=booking.RECIPIENTS["SE"],
                parcels=[booking.PARCEL],
                options=booking.service_point_options(point),
            ),
            rejection.access_point_id_only,
            "22001",
        )

        self.assertIn("22006", [str(message.code) for message in messages])
