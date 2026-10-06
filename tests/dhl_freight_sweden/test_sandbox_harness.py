"""Offline tests for the live sandbox harness and the payloads its segments send."""

import datetime
import pathlib
import unittest

import karrio.lib as lib
from sandbox_tests.dhl_freight_sweden import (
    booking,
    harness,
    rejection,
    test_booking_declarations as declarations,
    test_booking_export as export,
)

from .fixture import gateway, serialize_request, shipment_request

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
        self.assertEqual(config.max_bookings, 30)
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

    def test_booking_skip_reason(self):
        narrowed = harness.load_config(
            {
                **LIVE,
                "DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS": "109,112",
                "DHL_FREIGHT_SWEDEN_SANDBOX_COUNTRIES": "ro, no",
            },
            NOW,
        )
        cases = (
            (narrowed, "109", "RO", None),
            (narrowed, "112", "NO", None),
            (narrowed, "601", "NO", "product 601 is not in DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS"),
            (narrowed, "109", "HU", "country HU is not in DHL_FREIGHT_SWEDEN_SANDBOX_COUNTRIES"),
            (harness.load_config(LIVE, NOW), "601", "DK", None),
        )
        for config, product, country, reason in cases:
            with self.subTest(product=product, country=country):
                self.assertEqual(
                    harness.booking_skip_reason(config, product, country), reason
                )


class TestSandboxHarnessBudget(unittest.TestCase):
    def test_reserve_until_exhausted(self):
        budget = harness.BookingBudget(2)

        self.assertEqual([budget.reserve() for _ in range(3)], [True, True, False])
        self.assertEqual(budget.attempts, 2)

    def test_zero_budget_reserves_nothing(self):
        self.assertFalse(harness.BookingBudget(0).reserve())


class TestSandboxHarnessRedaction(unittest.TestCase):
    def test_captures_mask_the_client_key_and_keep_the_account_number(self):
        config = harness.load_config(LIVE, NOW)
        record = {
            "request_headers": {"client-key": "secret-key"},
            "data": {"parties": [{"id": "7654321", "type": "Consignor"}], "note": "via secret-key"},
        }

        self.assertEqual(harness.capture_secrets(config), ("secret-key",))
        self.assertEqual(
            harness.redact(record, harness.capture_secrets(config)),
            {
                "request_headers": {"client-key": "<redacted>"},
                "data": {
                    "parties": [{"id": "7654321", "type": "Consignor"}],
                    "note": "via <redacted>",
                },
            },
        )

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

    def test_decoded_body_keeps_empty_json_values(self):
        self.assertEqual(harness.decoded_body("[]"), [])
        self.assertEqual(harness.decoded_body("{}"), {})
        self.assertEqual(harness.decoded_body('{"a": 1}'), {"a": 1})
        self.assertEqual(harness.decoded_body("not json"), "not json")
        self.assertEqual(harness.decoded_body({"a": 1}), {"a": 1})


SERVICE_POINT = {
    "service_point_id": "PL-1234",
    "name": "Sklep Testowy",
    "type": "servicepoint",
    "address": {
        "street": "ul. Floriańska 1",
        "city": "Kraków",
        "postal_code": "31-019",
        "country_code": "PL",
    },
}

SE_SERVICE_POINT = {
    "service_point_id": "SE-982000",
    "name": "Testbutik",
    "type": "servicepoint",
    "address": {
        "street": "Drottninggatan 12",
        "city": "Stockholm",
        "postal_code": "11151",
        "country_code": "SE",
    },
}


def _serialize(request: lib.Serializable) -> dict:
    return serialize_request(request)


def _pl_request(product: str, options: dict) -> lib.Serializable:
    return gateway.mapper.create_shipment_request(
        shipment_request(
            service=product,
            shipper=booking.SHIPPER,
            recipient=booking.RECIPIENTS["PL"],
            parcels=[booking.PARCEL],
            options={**booking.SENT_FREE, **options},
        )
    )


class TestSandboxRejectionPayloads(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_mutated_request_leaves_the_original_request_intact(self):
        request = _pl_request("112", {})
        original = _serialize(request)

        mutated = _serialize(
            harness.mutated_request(request, rejection.with_payer_code("1"))
        )

        self.assertEqual(mutated["payerCode"], {"code": "1"})
        self.assertEqual(_serialize(request), original)
        self.assertEqual(
            {**mutated, "payerCode": original["payerCode"]}, original
        )

    def test_without_sent_removes_only_the_sent_entries(self):
        request = _pl_request(
            "109",
            {
                **booking.service_point_options(SERVICE_POINT),
                "dhl_freight_sweden_payer_code": "022",
            },
        )
        original = _serialize(request)

        mutated = _serialize(harness.mutated_request(request, rejection.without_sent))

        self.assertEqual(
            original["additionalInformation"],
            [{"code": "SENT_FREE", "stringValue": "true"}],
        )
        self.assertNotIn("additionalInformation", mutated)
        self.assertEqual(
            {key: value for key, value in original.items() if key != "additionalInformation"},
            mutated,
        )

    def test_with_party_appends_the_connector_access_point_shape(self):
        request = _pl_request(
            "109",
            {
                **booking.service_point_options(SERVICE_POINT),
                "dhl_freight_sweden_payer_code": "022",
            },
        )
        connector_access_point = _serialize(request)["parties"][-1]
        plain = _serialize(_pl_request("112", {}))

        mutated = _serialize(
            harness.mutated_request(
                _pl_request("112", {}),
                rejection.with_party(rejection.access_point_party(SERVICE_POINT)),
            )
        )

        self.assertEqual(
            rejection.access_point_party(SERVICE_POINT), connector_access_point
        )
        self.assertEqual(mutated["parties"], [*plain["parties"], connector_access_point])


    def test_access_point_id_only_drops_name_and_address(self):
        request = gateway.mapper.create_shipment_request(
            shipment_request(
                service="103",
                shipper=booking.SHIPPER,
                recipient=booking.RECIPIENTS["SE"],
                parcels=[booking.PARCEL],
                options=booking.service_point_options(SE_SERVICE_POINT),
            )
        )
        original = _serialize(request)

        mutated = _serialize(
            harness.mutated_request(request, rejection.access_point_id_only)
        )

        self.assertEqual(
            mutated["parties"],
            [
                *original["parties"][:-1],
                {"id": "SE-982000", "type": "AccessPoint", "subType": "ParcelShop"},
            ],
        )
        self.assertEqual({**mutated, "parties": original["parties"]}, original)


class TestSandboxDeclarationPayloads(unittest.TestCase):
    def test_601_declarations_serialize_as_not_free(self):
        cases = {
            "HU": [
                {"code": "EKAER_FREE", "stringValue": "false"},
                {"code": "EKAER_NUMBER", "stringValue": declarations.EKAER_NUMBER},
            ],
            "RO": [{"code": "UIT_FREE", "stringValue": "false"}],
        }

        for country, expected in cases.items():
            with self.subTest(country=country):
                serialized = _serialize(
                    gateway.mapper.create_shipment_request(
                        shipment_request(
                            service=declarations.PRODUCT,
                            shipper=booking.SHIPPER,
                            recipient=booking.RECIPIENTS[country],
                            parcels=[booking.PARCEL],
                            options={
                                "dhl_freight_sweden_payer_code": "DAP",
                                **declarations.DECLARATIONS[country],
                            },
                        )
                    )
                )

                self.assertEqual(serialized["additionalInformation"], expected)


class TestSandboxExportPayloads(unittest.TestCase):
    def test_aland_customs_without_service_carries_customs_information(self):
        serialized = _serialize(
            gateway.mapper.create_shipment_request(
                shipment_request(
                    **export.export_payload(
                        "109", booking.ALAND, export.ALAND_PARCEL_SHOP, customs_service=False
                    )
                )
            )
        )

        self.assertEqual(
            serialized["customsInformation"]["customsDocuments"][0]["type"], "CommercialInvoice"
        )
        self.assertEqual(len(serialized["customsInformation"]["customsCommodities"]), 1)
        self.assertFalse(
            {"customsHandlingStandard", "customsHandlingFullService"}
            & set(serialized.get("additionalServices") or {})
        )
