"""Offline tests for the live sandbox harness's configuration, budget, and redaction."""

import datetime
import pathlib
import unittest

from sandbox_tests.dhl_freight_sweden import harness

NOW = datetime.datetime(2026, 10, 5, 12, 0, 0)
LIVE = {
    "DHL_FREIGHT_SWEDEN_SANDBOX": "1",
    "KARRIO_DHL_FREIGHT_SWEDEN_CLIENT_KEY": "secret-key",
    "KARRIO_DHL_FREIGHT_SWEDEN_ACCOUNT_NUMBER": "7654321",
    "HOME": "/home/tester",
}


class TestSandboxHarnessConfig(unittest.TestCase):
    def test_defaults(self):
        config = harness.load_config({"HOME": "/home/tester"}, NOW)

        self.assertFalse(config.enabled)
        self.assertEqual(config.segments, {"lookups"})
        self.assertIsNone(config.products)
        self.assertEqual(config.max_bookings, 3)
        self.assertEqual(
            config.capture_dir,
            pathlib.Path(
                "/home/tester/.local/state/karrio-dhl-freight-sweden/sandbox/20261005-120000"
            ),
        )

    def test_selection_and_capture_dir(self):
        config = harness.load_config(
            {
                **LIVE,
                "XDG_STATE_HOME": "/state",
                "DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS": " booking-pudo, lookups ,",
                "DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS": "109,103",
                "DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS": "1",
            },
            NOW,
        )

        self.assertTrue(config.enabled)
        self.assertEqual(config.segments, {"booking-pudo", "lookups"})
        self.assertEqual(config.products, {"103", "109"})
        self.assertEqual(config.max_bookings, 1)
        self.assertEqual(
            config.capture_dir,
            pathlib.Path("/state/karrio-dhl-freight-sweden/sandbox/20261005-120000"),
        )
        self.assertEqual(
            harness.load_config(
                {**LIVE, "DHL_FREIGHT_SWEDEN_SANDBOX_CAPTURE_DIR": "/tmp/run"}, NOW
            ).capture_dir,
            pathlib.Path("/tmp/run"),
        )

    def test_malformed_or_unsafe_values_raise(self):
        for key, value in (
            ("DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS", "lookups,customs"),
            ("DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS", "three"),
            ("DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS", "-1"),
        ):
            with self.subTest(key=key, value=value):
                with self.assertRaises(harness.SandboxConfigError):
                    harness.load_config({**LIVE, key: value}, NOW)


    def test_only_the_sandbox_host_is_allowed(self):
        self.assertEqual(
            harness.check_host("https://TEST-API.freight-logistics.dhl.com/x"),
            "test-api.freight-logistics.dhl.com",
        )
        for url in (
            "https://api.freight-logistics.dhl.com/x",
            "https://example.com/x",
            "",
        ):
            with self.subTest(url=url):
                with self.assertRaises(harness.SandboxConfigError):
                    harness.check_host(url)

    def test_skip_reasons(self):
        booking = {**LIVE, "DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS": "booking-approved"}
        cases = (
            ({**LIVE, "DHL_FREIGHT_SWEDEN_SANDBOX": "true"}, "lookups", "DHL_FREIGHT_SWEDEN_SANDBOX is not 1"),
            ({**LIVE, "KARRIO_DHL_FREIGHT_SWEDEN_CLIENT_KEY": ""}, "lookups", "KARRIO_DHL_FREIGHT_SWEDEN_CLIENT_KEY is not set"),
            (LIVE, "lookups", None),
            (LIVE, "booking-approved", "segment booking-approved is not in DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS"),
            (booking, "booking-approved", None),
            ({**booking, "KARRIO_DHL_FREIGHT_SWEDEN_ACCOUNT_NUMBER": ""}, "booking-approved", "KARRIO_DHL_FREIGHT_SWEDEN_ACCOUNT_NUMBER is not set"),
        )
        for environ, segment, reason in cases:
            with self.subTest(segment=segment, reason=reason):
                self.assertEqual(
                    harness.skip_reason(harness.load_config(environ, NOW), segment),
                    reason,
                )

    def test_product_skip_reason(self):
        narrowed = harness.load_config(
            {**LIVE, "DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS": "102"}, NOW
        )

        self.assertIsNone(harness.product_skip_reason(narrowed, "102"))
        self.assertIsNotNone(harness.product_skip_reason(narrowed, "601"))
        self.assertIsNone(
            harness.product_skip_reason(harness.load_config(LIVE, NOW), "601")
        )


class TestSandboxHarnessBudget(unittest.TestCase):
    def test_reserve_until_exhausted(self):
        budget = harness.BookingBudget(2)

        self.assertEqual([budget.reserve() for _ in range(3)], [True, True, False])
        self.assertEqual(budget.attempts, 2)

    def test_zero_budget_reserves_nothing(self):
        self.assertFalse(harness.BookingBudget(0).reserve())


class TestSandboxHarnessRedaction(unittest.TestCase):
    def test_redacts_secret_headers_and_values(self):
        record = {
            "url": "https://test-api.freight-logistics.dhl.com/x",
            "request_headers": {"Client-Key": "secret-key", "Content-Type": "application/json"},
            "data": {
                "parties": [{"id": "7654321", "type": "Consignor"}],
                "note": "account 7654321 via secret-key",
                "weight": 1.0,
            },
        }

        self.assertEqual(
            harness.redact(record, ("secret-key", "7654321", None)),
            {
                "url": "https://test-api.freight-logistics.dhl.com/x",
                "request_headers": {"Client-Key": "<redacted>", "Content-Type": "application/json"},
                "data": {
                    "parties": [{"id": "<redacted>", "type": "Consignor"}],
                    "note": "account <redacted> via <redacted>",
                    "weight": 1.0,
                },
            },
        )
