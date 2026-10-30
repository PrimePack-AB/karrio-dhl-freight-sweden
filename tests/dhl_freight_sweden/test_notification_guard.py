"""Booking guard for the notification additional service.

A live 118 booking with the notification flag set was rejected with 24000
"notification is not available for this product" before this guard existed;
docs/notes/integration/notification-guard.md records the decisions. The
capability is read from the same product matches answer the product guard
uses, so the guard functions are tested here against plain product dicts
before the proxy wiring is tested below.
"""

import json
import pathlib
import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
from karrio.providers.dhl_freight_sweden.product_matches import (
    NotificationNotOfferedError,
    ProductNotOfferedError,
    check_booking_notification,
)

from .fixture import _gateway, as_dict, http_error, proxy_of, settings_of
from .test_product_match_guard import _answers, _book
from .test_shipment import _payload, _recipient_se

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

UNLISTED_118 = (
    "Notification support was not verified (product 118 is not listed in the "
    "product matches answer from SE 11143 to SE 41103); the booking proceeded "
    "without the check"
)

MATCHES_PATH = "/productapi/v1/productmatches"
TI_PATH = "/transportinstruction/sendtransportinstruction"
FIXTURE_NAME = "lookup-product-matches-se-se-additional-services.json"
PAYLOAD_118 = _payload(
    "dhl_freight_sweden_hemleverans_paket_b2c",
    _recipient_se,
    {"email_notification": True},
)
PAYLOAD_118_SMS = _payload(
    "dhl_freight_sweden_hemleverans_paket_b2c",
    _recipient_se,
    {"sms_notification": True},
)
PAYLOAD_102 = _payload(
    "dhl_freight_sweden_paket",
    _recipient_se,
    {"email_notification": True},
)
PAYLOAD_118_FALSE = _payload(
    "dhl_freight_sweden_hemleverans_paket_b2c",
    _recipient_se,
    {"email_notification": False},
)


def _matches_answer() -> str:
    evidence = json.loads((FIXTURES / FIXTURE_NAME).read_text())
    return lib.to_json(evidence["exchanges"][0]["response"])


def _booking_answers() -> list:
    evidence = json.loads(
        (FIXTURES / "booking-2906761222-102-se-se.json").read_text()
    )
    return [
        lib.to_json(exchange["response"])
        for exchange in evidence["exchanges"]
    ]


def _expected_refusal(product_code: str) -> str:
    evidence = json.loads((FIXTURES / FIXTURE_NAME).read_text())
    entry = next(
        match["product"]
        for match in evidence["exchanges"][0]["response"]
        if match["product"]["code"] == product_code
    )
    services = [service["code"] for service in entry["additionalServices"]]
    listing = ", ".join(services) if services else "none"
    return (
        f"Product {product_code} (dhl_freight_sweden_hemleverans_paket_b2c) "
        "does not offer the notification service from SE 11143 to SE 41103 "
        "by DHL product matches; the notification option (email_notification, "
        "sms_notification, or dhl_freight_sweden_notification) was set "
        f"explicitly. Additional services offered for this product: {listing}."
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

    def test_service_less_product_refuses_with_none_listing(self):
        with self.assertRaises(NotificationNotOfferedError) as context:
            check_booking_notification(
                CRITERIA,
                "118",
                [{"code": "118", "name": "DHL Hemleverans Paket"}],
                [],
                self.settings,
                "enforce",
            )

        self.assertTrue(
            str(context.exception).endswith(
                "Additional services offered for this product: none."
            )
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

    def test_product_missing_from_the_answer_warns_unverified(self):
        for mode in ("warn", "enforce"):
            with self.subTest(mode=mode):
                (warning,) = check_booking_notification(
                    CRITERIA, "401", self.products, [], self.settings, mode
                )

                self.assertEqual(warning.code, "notification_availability_unverified")
                self.assertEqual(warning.level, "warning")
                self.assertEqual(warning.message, UNLISTED_118.replace("118", "401"))

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

    def test_notification_check_setting_defaults_to_enforce(self):
        self.assertEqual(
            str(_gateway({}).settings.connection_config.notification_check.state),
            "enforce",
        )


class TestNotificationGuardBooking(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.enforce = _gateway({"product_matches_check": "enforce"})
        self.warn = _gateway({"product_matches_check": "warn", "notification_check": "warn"})

    def test_enforce_refuses_118_before_booking(self):
        for payload, name in ((PAYLOAD_118, "email"), (PAYLOAD_118_SMS, "sms")):
            with self.subTest(option=name):
                request = self.enforce.mapper.create_shipment_request(
                    models.ShipmentRequest(**payload)
                )
                with patch(
                    "karrio.mappers.dhl_freight_sweden.proxy.lib.request"
                ) as mock:
                    mock.side_effect = _answers(_matches_answer())
                    with self.assertRaises(NotificationNotOfferedError) as context:
                        proxy_of(self.enforce).create_shipment(request)

                self.assertEqual(mock.call_count, 1)
                self.assertTrue(
                    mock.call_args.kwargs["url"].endswith(MATCHES_PATH)
                )
                self.assertEqual(
                    str(context.exception), _expected_refusal("118")
                )

    def test_warn_strips_the_flag_and_warns(self):
        (details, messages), urls, mock = _book(
            self.warn, PAYLOAD_118, _matches_answer(), *_booking_answers()
        )

        self.assertIsNotNone(details)
        warning = next(
            m for m in messages if m.code == "notification_not_offered"
        )
        self.assertEqual(warning.level, "warning")
        self.assertEqual(warning.message, _expected_refusal("118"))
        booking_call = next(
            call for call in mock.call_args_list
            if call.kwargs["url"].endswith(TI_PATH)
        )
        sent = as_dict(lib.to_dict(booking_call.kwargs["data"]))
        self.assertNotIn(
            "notification",
            sent.get("additionalServices") or {},
            "warn mode drops the flag before the booking POST",
        )

    def test_offered_product_sends_the_flag_without_warning(self):
        (details, messages), urls, mock = _book(
            self.enforce, PAYLOAD_102, _matches_answer(), *_booking_answers()
        )

        self.assertIsNotNone(details)
        self.assertEqual(messages, [])
        booking_call = next(
            call for call in mock.call_args_list
            if call.kwargs["url"].endswith(TI_PATH)
        )
        sent = as_dict(lib.to_dict(booking_call.kwargs["data"]))
        self.assertIs(sent["additionalServices"]["notification"], True)

    def test_warn_mode_with_offered_product_sends_the_flag_without_warning(self):
        warn = _gateway({"product_matches_check": "enforce", "notification_check": "warn"})
        (details, messages), urls, mock = _book(
            warn, PAYLOAD_102, _matches_answer(), *_booking_answers()
        )

        self.assertIsNotNone(details)
        self.assertEqual(messages, [])
        booking_call = next(
            call for call in mock.call_args_list
            if call.kwargs["url"].endswith(TI_PATH)
        )
        sent = as_dict(lib.to_dict(booking_call.kwargs["data"]))
        self.assertIs(sent["additionalServices"]["notification"], True)

    def test_explicit_false_passes_through_verbatim(self):
        (details, messages), urls, mock = _book(
            self.enforce, PAYLOAD_118_FALSE, _matches_answer(), *_booking_answers()
        )

        self.assertIsNotNone(details)
        self.assertEqual(messages, [])
        booking_call = next(
            call for call in mock.call_args_list
            if call.kwargs["url"].endswith(TI_PATH)
        )
        sent = as_dict(lib.to_dict(booking_call.kwargs["data"]))
        self.assertIs(sent["additionalServices"]["notification"], False)

    def test_off_mode_sends_the_flag_verbatim(self):
        off = _gateway({"product_matches_check": "off", "notification_check": "off"})
        (details, messages), urls, mock = _book(
            off, PAYLOAD_118, *_booking_answers()
        )

        self.assertIsNotNone(details)
        self.assertEqual(messages, [])
        self.assertFalse(any(url.endswith(MATCHES_PATH) for url in urls))
        booking_call = next(
            call for call in mock.call_args_list
            if call.kwargs["url"].endswith(TI_PATH)
        )
        sent = as_dict(lib.to_dict(booking_call.kwargs["data"]))
        self.assertIs(sent["additionalServices"]["notification"], True)

    def test_product_check_off_lookup_failure_warns_notification_only(self):
        product_off = _gateway({"product_matches_check": "off"})
        (details, messages), urls, mock = _book(
            product_off,
            PAYLOAD_118,
            http_error(502, "<html>Bad Gateway</html>"),
            *_booking_answers(),
        )

        self.assertIsNotNone(details)
        (warning,) = messages
        self.assertEqual(warning.code, "notification_availability_unverified")
        self.assertEqual(warning.level, "warning")
        self.assertTrue(urls[0].endswith(MATCHES_PATH))
        self.assertIs(_sent(mock)["additionalServices"]["notification"], True)

    def test_failed_lookup_warns_both_guards_unverified(self):
        (details, messages), urls, _ = _book(
            self.enforce,
            PAYLOAD_118,
            http_error(502, "<html>Bad Gateway</html>"),
            *_booking_answers(),
        )

        self.assertIsNotNone(details)
        self.assertEqual(
            [m.code for m in messages],
            ["product_availability_unverified", "notification_availability_unverified"],
        )

    def test_unguarded_product_skips_the_guard(self):
        payload = _payload(
            "dhl_freight_sweden_pall",
            _recipient_se,
            {"email_notification": True},
        )
        (details, messages), urls, mock = _book(
            self.enforce, payload, *_booking_answers()
        )

        self.assertIsNotNone(details)
        self.assertEqual(messages, [])
        self.assertFalse(any(url.endswith(MATCHES_PATH) for url in urls))
        booking_call = next(
            call for call in mock.call_args_list
            if call.kwargs["url"].endswith(TI_PATH)
        )
        sent = as_dict(lib.to_dict(booking_call.kwargs["data"]))
        self.assertIs(sent["additionalServices"]["notification"], True)

    def test_matches_refusal_wins_over_the_notification_refusal(self):
        request = self.enforce.mapper.create_shipment_request(
            models.ShipmentRequest(**PAYLOAD_102)
        )
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.side_effect = _answers("[]")
            with self.assertRaises(ProductNotOfferedError):
                proxy_of(self.enforce).create_shipment(request)


def _with_check(payload: dict, **checks: str) -> dict:
    return {
        **payload,
        "options": {
            **payload["options"],
            **{f"dhl_freight_sweden_{name}": mode for name, mode in checks.items()},
        },
    }


def _sent(mock) -> dict:
    booking_call = next(
        call for call in mock.call_args_list if call.kwargs["url"].endswith(TI_PATH)
    )
    return as_dict(lib.to_dict(booking_call.kwargs["data"]))


class TestNotificationCheckOption(unittest.TestCase):
    """The per-shipment option overrides the connection setting in both directions."""

    def setUp(self):
        self.maxDiff = None
        self.enforce = _gateway({"product_matches_check": "enforce"})

    def test_option_off_sends_the_flag_on_an_enforcing_connection(self):
        (details, messages), urls, mock = _book(
            self.enforce,
            _with_check(PAYLOAD_118, notification_check="off"),
            _matches_answer(),
            *_booking_answers(),
        )

        self.assertIsNotNone(details)
        self.assertEqual(messages, [])
        self.assertTrue(urls[0].endswith(MATCHES_PATH), "the product guard still looks up")
        self.assertIs(_sent(mock)["additionalServices"]["notification"], True)

    def test_option_warn_strips_the_flag_on_an_enforcing_connection(self):
        (details, messages), urls, mock = _book(
            self.enforce,
            _with_check(PAYLOAD_118, notification_check="warn"),
            _matches_answer(),
            *_booking_answers(),
        )

        self.assertIsNotNone(details)
        (warning,) = messages
        self.assertEqual(warning.code, "notification_not_offered")
        self.assertEqual(warning.message, _expected_refusal("118"))
        self.assertNotIn("notification", _sent(mock).get("additionalServices") or {})

    def test_option_enforce_refuses_on_an_off_or_warn_connection(self):
        for setting in ("off", "warn"):
            with self.subTest(setting=setting):
                gateway_ = _gateway(
                    {"product_matches_check": "enforce", "notification_check": setting}
                )
                request = gateway_.mapper.create_shipment_request(
                    models.ShipmentRequest(
                        **_with_check(PAYLOAD_118, notification_check="enforce")
                    )
                )
                with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
                    mock.side_effect = _answers(_matches_answer())
                    with self.assertRaises(NotificationNotOfferedError) as context:
                        proxy_of(gateway_).create_shipment(request)

                self.assertEqual(mock.call_count, 1)
                self.assertEqual(str(context.exception), _expected_refusal("118"))

    def test_connection_setting_applies_without_the_option(self):
        warn = _gateway({"product_matches_check": "enforce", "notification_check": "warn"})
        (details, messages), urls, mock = _book(
            warn, PAYLOAD_118, _matches_answer(), *_booking_answers()
        )

        self.assertIsNotNone(details)
        self.assertEqual([m.code for m in messages], ["notification_not_offered"])

    def test_options_are_not_sent_to_dhl(self):
        (details, _), urls, mock = _book(
            self.enforce,
            _with_check(PAYLOAD_118, notification_check="off", product_matches_check="warn"),
            _matches_answer(),
            *_booking_answers(),
        )

        self.assertIsNotNone(details)
        for call in mock.call_args_list:
            self.assertNotIn("_check", str(call.kwargs.get("data")))


class TestNotificationLookupWithProductCheckOff(unittest.TestCase):
    """The notification guard runs its own matches lookup when the product check is off."""

    def setUp(self):
        self.maxDiff = None
        self.product_off = _gateway({"product_matches_check": "off"})

    def test_enforce_refuses_a_product_without_notification(self):
        for gateway_, payload in (
            (self.product_off, PAYLOAD_118),
            (
                _gateway({"product_matches_check": "enforce"}),
                _with_check(PAYLOAD_118, product_matches_check="off"),
            ),
        ):
            with self.subTest(options=payload["options"]):
                request = gateway_.mapper.create_shipment_request(
                    models.ShipmentRequest(**payload)
                )
                with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
                    mock.side_effect = _answers(_matches_answer())
                    with self.assertRaises(NotificationNotOfferedError) as context:
                        proxy_of(gateway_).create_shipment(request)

                self.assertEqual(mock.call_count, 1)
                self.assertTrue(mock.call_args.kwargs["url"].endswith(MATCHES_PATH))
                self.assertEqual(str(context.exception), _expected_refusal("118"))

    def test_warn_books_without_the_flag(self):
        (details, messages), urls, mock = _book(
            self.product_off,
            _with_check(PAYLOAD_118, notification_check="warn"),
            _matches_answer(),
            *_booking_answers(),
        )

        self.assertIsNotNone(details)
        self.assertEqual([m.code for m in messages], ["notification_not_offered"])
        self.assertEqual(messages[0].message, _expected_refusal("118"))
        self.assertNotIn("notification", _sent(mock).get("additionalServices") or {})

    def test_product_missing_from_the_answer_warns_unverified(self):
        (details, messages), urls, mock = _book(
            self.product_off, PAYLOAD_118, "[]", *_booking_answers()
        )

        self.assertIsNotNone(details)
        self.assertEqual(
            [(m.code, m.message) for m in messages],
            [("notification_availability_unverified", UNLISTED_118)],
        )
        self.assertTrue(urls[0].endswith(MATCHES_PATH))
        self.assertTrue(urls[1].endswith(TI_PATH))
        self.assertIs(_sent(mock)["additionalServices"]["notification"], True)

    def test_offered_product_books_with_the_flag(self):
        (details, messages), urls, mock = _book(
            self.product_off, PAYLOAD_102, _matches_answer(), *_booking_answers()
        )

        self.assertIsNotNone(details)
        self.assertEqual(messages, [])
        self.assertTrue(urls[0].endswith(MATCHES_PATH))
        self.assertIs(_sent(mock)["additionalServices"]["notification"], True)

    def test_unset_or_false_flag_makes_no_lookup(self):
        unset = _payload("dhl_freight_sweden_hemleverans_paket_b2c", _recipient_se)
        for payload in (unset, PAYLOAD_118_FALSE):
            with self.subTest(options=payload["options"]):
                (details, messages), urls, _ = _book(
                    self.product_off, payload, *_booking_answers()
                )

                self.assertIsNotNone(details)
                self.assertEqual(messages, [])
                self.assertFalse(any(url.endswith(MATCHES_PATH) for url in urls))


class TestNotificationUnlistedProduct(unittest.TestCase):
    """A product the matches answer does not list leaves notification support unverified."""

    def test_product_warn_adds_both_warnings_and_keeps_the_flag(self):
        warn = _gateway({"product_matches_check": "warn"})
        (details, messages), urls, mock = _book(
            warn, PAYLOAD_118, "[]", *_booking_answers()
        )

        self.assertIsNotNone(details)
        self.assertEqual(
            [m.code for m in messages],
            ["product_not_offered", "notification_availability_unverified"],
        )
        self.assertEqual(messages[1].message, UNLISTED_118)
        self.assertIs(_sent(mock)["additionalServices"]["notification"], True)

    def test_notification_warn_keeps_the_flag(self):
        warn = _gateway({"product_matches_check": "off", "notification_check": "warn"})
        (details, messages), urls, mock = _book(
            warn, PAYLOAD_118, "[]", *_booking_answers()
        )

        self.assertIsNotNone(details)
        self.assertEqual(
            [(m.code, m.message) for m in messages],
            [("notification_availability_unverified", UNLISTED_118)],
        )
        self.assertIs(_sent(mock)["additionalServices"]["notification"], True)

    def test_product_enforce_refuses_before_the_notification_guard(self):
        enforce = _gateway({"product_matches_check": "enforce"})
        (details, messages), urls, _ = _book(enforce, PAYLOAD_118, "[]")

        self.assertIsNone(details)
        self.assertEqual(len(urls), 1)
        self.assertEqual([m.code for m in messages], ["SHIPPING_SDK_FIELD_ERROR"])
        self.assertIn("is not offered from SE 11143 to SE 41103", messages[0].message)

    def test_notification_off_adds_no_notification_warning(self):
        warn = _gateway({"product_matches_check": "warn", "notification_check": "off"})
        (details, messages), urls, _ = _book(
            warn, PAYLOAD_118, "[]", *_booking_answers()
        )

        self.assertIsNotNone(details)
        self.assertEqual([m.code for m in messages], ["product_not_offered"])


if __name__ == "__main__":
    unittest.main()
