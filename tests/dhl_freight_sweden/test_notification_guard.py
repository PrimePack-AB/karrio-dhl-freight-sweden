"""Booking guard for the notification additional service.

A live 118 booking with the notification flag set was rejected with 24000
"notification is not available for this product" before this guard existed;
docs/notes/integration/notification-guard.md records the decisions. The
capability is read from the same product matches answer the product guard
uses, so the guard functions are tested here against plain product dicts
before the proxy wiring is tested below.
"""

import pathlib
import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
from karrio.providers.dhl_freight_sweden.product_matches import (
    NotificationNotOfferedError,
    check_booking_notification,
)

from .fixture import _gateway, settings_of

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "sandbox"

CRITERIA = {
    "parties": [
        {"type": "Consignor", "address": {"countryCode": "SE", "postalCode": "11143"}},
        {"type": "Consignee", "address": {"countryCode": "SE", "postalCode": "41103"}},
    ]
}

REFUSAL_118 = (
    "Product 118 (dhl_freight_sweden_hemleverans_paket_b2c) does not offer the "
    "notification service from SE 11143 to SE 41103 by DHL product matches; the "
    "notification option (email_notification, sms_notification, or "
    "dhl_freight_sweden_notification) was set explicitly. Additional services "
    "offered for this product: signature."
)


class TestCheckBookingNotification(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.settings = settings_of(_gateway({}))
        self.products = [
            {
                "code": "118",
                "name": "DHL Hemleverans Paket",
                "additional_services": ["signature"],
            },
            {
                "code": "102",
                "name": "DHL Paket",
                "additional_services": ["notification", "signature"],
            },
        ]

    def test_enforce_raises_when_the_product_lacks_notification(self):
        with self.assertRaises(NotificationNotOfferedError) as context:
            check_booking_notification(
                CRITERIA, "118", self.products, [], self.settings, "enforce"
            )

        self.assertEqual(str(context.exception), REFUSAL_118)
        self.assertEqual(context.exception.code, "SHIPPING_SDK_FIELD_ERROR")
        self.assertEqual(
            context.exception.details,
            {
                "notification": dict(
                    code="notification_not_offered",
                    message=REFUSAL_118,
                )
            },
        )

    def test_warn_warns_when_the_product_lacks_notification(self):
        messages = check_booking_notification(
            CRITERIA, "118", self.products, [], self.settings, "warn"
        )

        (warning,) = messages
        self.assertEqual(warning.code, "notification_not_offered")
        self.assertEqual(warning.level, "warning")
        self.assertEqual(warning.message, REFUSAL_118)
        self.assertEqual(warning.details, dict(product="118", additional_services=["signature"]))

    def test_offered_product_returns_no_message(self):
        self.assertEqual(
            check_booking_notification(
                CRITERIA, "102", self.products, [], self.settings, "enforce"
            ),
            [],
        )

    def test_product_missing_from_the_answer_returns_no_message(self):
        self.assertEqual(
            check_booking_notification(
                CRITERIA, "401", self.products, [], self.settings, "warn"
            ),
            [],
        )

    def test_failed_lookup_warns_unverified(self):
        failure = models.Message(
            carrier_id="dhl_freight_sweden",
            carrier_name="dhl_freight_sweden",
            code="22001",
            message="The Consignee address postal code is required",
        )

        (warning,) = check_booking_notification(
            CRITERIA, "118", [], [failure], self.settings, "enforce"
        )

        self.assertEqual(warning.code, "notification_availability_unverified")
        self.assertEqual(warning.level, "warning")
        self.assertEqual(
            warning.message,
            "Notification support was not verified (product matches lookup "
            "failed: The Consignee address postal code is required); the "
            "booking proceeded without the check",
        )

    def test_notifications_setting_defaults_to_enforce(self):
        self.assertEqual(
            str(_gateway({}).settings.connection_config.notifications.state),
            "enforce",
        )


if __name__ == "__main__":
    unittest.main()
