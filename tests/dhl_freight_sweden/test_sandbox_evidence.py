"""Offline checks on the committed sandbox evidence files.

The evidence files back the sandbox findings note and the README's sandbox
citations, so these tests keep them free of secrets and label payloads and
show that their response bodies still parse with the connector's parsers.
"""

import json
import logging
import os
import pathlib
import re
import typing
import unittest
import unittest.mock

import karrio.lib as lib
from karrio.providers.dhl_freight_sweden import (
    address,
    error,
    product_matches,
    service_points,
)
from karrio.providers.dhl_freight_sweden.shipment import create

from .fixture import gateway, settings_of

EVIDENCE_DIR = pathlib.Path(__file__).parent / "fixtures" / "sandbox"
EVIDENCE_FILES = sorted(EVIDENCE_DIR.glob("*.json"))
HOST = "test-api.freight-logistics.dhl.com"
ACCOUNT_NUMBER = "116768"
KINDS = ("booking", "rejection", "lookup", "label")
METADATA_KEYS = (
    "kind",
    "summary",
    "captured_at",
    "environment",
    "endpoint",
    "product",
    "route",
    "booking_id",
    "error_code",
    "http_status",
    "captured_by",
    "redaction",
    "account_number_restored",
    "exchanges",
)
EXCHANGE_KEYS = (
    "endpoint",
    "http_status",
    "date",
    "date_basis",
    "request_source",
    "response_source",
    "request",
    "response",
)
OPTIONAL_EXCHANGE_KEYS = {"response_reduced", "label"}
LABEL_KEYS = ("pdf_source", "page_size_pt", "text_extraction", "text_source", "text")
TI_PATH = "/transportinstructionapi/v1/transportinstruction/sendtransportinstruction"
PRINT_PATH = "/printapi/v1/print/printdocumentsbyid"
CAPTURED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TOKEN = re.compile(r"^[A-Za-z0-9_\-+/=]{30,}$")
OMITTED = re.compile(r"^<base64 omitted: \d+ characters>$")


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())


def walk(value: typing.Any, key: str = "") -> typing.Iterator[typing.Tuple[str, typing.Any]]:
    """Yield every (key, value) pair in a JSON tree, keys of lists repeated."""
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield child_key, child
            yield from walk(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield key, child
            yield from walk(child, key)


def exchanges_to(evidence: dict, path: str) -> typing.List[dict]:
    return [item for item in evidence["exchanges"] if item["endpoint"].endswith(path)]


class TestSandboxEvidenceFiles(unittest.TestCase):
    def test_evidence_files_exist(self):
        self.assertGreater(len(EVIDENCE_FILES), 0)

    def test_metadata(self):
        for path in EVIDENCE_FILES:
            with self.subTest(path.name):
                evidence = load(path)
                self.assertEqual(tuple(evidence), METADATA_KEYS)
                self.assertIn(evidence["kind"], KINDS)
                self.assertTrue(path.name.startswith(evidence["kind"] + "-"))
                self.assertEqual(evidence["environment"], HOST)
                self.assertRegex(evidence["captured_at"], CAPTURED_AT)
                self.assertIn(
                    evidence["endpoint"], [item["endpoint"] for item in evidence["exchanges"]]
                )
                if evidence["kind"] in ("booking", "label"):
                    self.assertIsNotNone(evidence["booking_id"])
                    self.assertIn(evidence["booking_id"], path.name)
                if evidence["kind"] == "rejection":
                    self.assertIsNone(evidence["booking_id"])
                    self.assertIn(evidence["error_code"], path.name)

    def test_exchanges_cite_their_source_captures(self):
        for path in EVIDENCE_FILES:
            evidence = load(path)
            for item in evidence["exchanges"]:
                with self.subTest(path.name, endpoint=item["endpoint"]):
                    self.assertEqual(tuple(item)[: len(EXCHANGE_KEYS)], EXCHANGE_KEYS)
                    self.assertLessEqual(set(item) - set(EXCHANGE_KEYS), OPTIONAL_EXCHANGE_KEYS)
                    self.assertRegex(item["date"], CAPTURED_AT)
                    for source in (item["request_source"], item["response_source"]):
                        if source is None:
                            continue
                        self.assertFalse(pathlib.PurePath(source["path"]).is_absolute())
                        self.assertRegex(source["sha256"], SHA256)
                    self.assertIsNotNone(item["response_source"])

    def test_no_client_key_or_label_payload(self):
        client_key = os.environ.get("KARRIO_DHL_FREIGHT_SWEDEN_CLIENT_KEY")
        for path in EVIDENCE_FILES:
            with self.subTest(path.name):
                text = path.read_text()
                self.assertFalse("<KEY>" in text, "client key placeholder present")
                self.assertFalse("JVBERi0" in text, "base64 PDF present")
                if client_key:
                    self.assertFalse(client_key in text, "client key present")
                for key, value in walk(load(path)):
                    self.assertNotIn(key.lower(), ("client-key", "request_headers"))
                    if not isinstance(value, str) or key == "sha256":
                        continue
                    self.assertNotRegex(value, TOKEN, f"{key} carries a token-like value")
                    if key == "content":
                        self.assertRegex(value, OMITTED)

    def test_consignor_carries_the_account_number(self):
        for path in EVIDENCE_FILES:
            evidence = load(path)
            for item in exchanges_to(evidence, TI_PATH):
                for body in (item["request"], item["response"].get("transportInstruction")):
                    for party in (body or {}).get("parties", []):
                        if party["type"] == "Consignor":
                            with self.subTest(path.name):
                                self.assertEqual(party["id"], ACCOUNT_NUMBER)

    def test_labels_cite_their_pdf_and_text(self):
        labels = 0
        for path in EVIDENCE_FILES:
            evidence = load(path)
            for item in evidence["exchanges"]:
                if "label" not in item:
                    continue
                labels += 1
                with self.subTest(path.name):
                    label = item["label"]
                    self.assertEqual(tuple(label), LABEL_KEYS)
                    self.assertTrue(item["endpoint"].endswith(PRINT_PATH))
                    for source in (label["pdf_source"], label["text_source"]):
                        self.assertFalse(pathlib.PurePath(source["path"]).is_absolute())
                        self.assertRegex(source["sha256"], SHA256)
                    self.assertEqual(len(label["page_size_pt"]), 2)
                    self.assertIn(evidence["booking_id"], label["text"])
        self.assertGreater(labels, 0)


class TestSandboxEvidenceParses(unittest.TestCase):
    """Live bodies carry fields the vendored schemas do not declare.

    jstruct logs a warning for each such field while parsing, so the logger
    is muted to keep the run output readable.
    """

    def setUp(self):
        muted = unittest.mock.patch.object(logging.getLogger("jstruct.utils"), "disabled", True)
        muted.start()
        self.addCleanup(muted.stop)

    def test_booking_responses_parse(self):
        for path in EVIDENCE_FILES:
            evidence = load(path)
            if evidence["kind"] != "booking":
                continue
            with self.subTest(path.name):
                (booking,) = exchanges_to(evidence, TI_PATH)
                printed = next(iter(exchanges_to(evidence, PRINT_PATH)), None)
                details, messages = create.parse_shipment_response(
                    lib.Deserializable(
                        [booking["response"], printed["response"] if printed else None]
                    ),
                    settings_of(gateway),
                )

                self.assertEqual(messages, [])
                self.assertIsNotNone(details)
                self.assertEqual(details.tracking_number, evidence["booking_id"])

    def test_label_responses_parse(self):
        for path in EVIDENCE_FILES:
            evidence = load(path)
            if evidence["kind"] != "label":
                continue
            with self.subTest(path.name):
                (printed,) = exchanges_to(evidence, PRINT_PATH)
                self.assertEqual(
                    [report["contentType"] for report in printed["response"]["reports"]],
                    ["application/pdf"],
                )
                for booking in exchanges_to(evidence, TI_PATH):
                    details, messages = create.parse_shipment_response(
                        lib.Deserializable([booking["response"], printed["response"]]),
                        settings_of(gateway),
                    )

                    self.assertEqual(messages, [])
                    self.assertIsNotNone(details)
                    self.assertEqual(details.tracking_number, evidence["booking_id"])

    def test_rejection_responses_parse(self):
        for path in EVIDENCE_FILES:
            evidence = load(path)
            if evidence["kind"] != "rejection":
                continue
            with self.subTest(path.name):
                (booking,) = exchanges_to(evidence, TI_PATH)
                details, messages = create.parse_shipment_response(
                    lib.Deserializable([booking["response"], None]), settings_of(gateway)
                )

                self.assertIsNone(details)
                self.assertEqual([message.code for message in messages], [evidence["error_code"]])

    def test_lookup_responses_parse(self):
        for path in EVIDENCE_FILES:
            evidence = load(path)
            if evidence["kind"] != "lookup":
                continue
            for item in evidence["exchanges"]:
                with self.subTest(path.name, endpoint=item["endpoint"]):
                    response = lib.Deserializable(item["response"])
                    if "/productmatches" in item["endpoint"]:
                        products, messages = product_matches.parse_product_matches_response(
                            response, settings_of(gateway)
                        )
                        self.assertEqual(
                            [product["code"] for product in products],
                            [match["product"]["code"] for match in item["response"]],
                        )
                        self.assertEqual(messages, [])
                    elif "/findnearestservicepoints" in item["endpoint"]:
                        points, messages = service_points.parse_service_points_response(
                            response, settings_of(gateway)
                        )
                        if item["http_status"] == 200:
                            self.assertEqual(len(points), len(item["response"]["servicePoints"]))
                            self.assertEqual(messages, [])
                        else:
                            self.assertEqual(points, [])
                            self.assertEqual(
                                [message.message for message in messages],
                                [item["response"]["errorMessage"]],
                            )
                    elif item["endpoint"].endswith("/route"):
                        # attrs drops the leading underscore of Deserializable._ctx, so the init parameter is ctx.
                        route = lib.Deserializable(item["response"], ctx={})  # pyright: ignore[reportCallIssue]
                        details, messages = address.parse_address_validation_response(
                            route, settings_of(gateway)
                        )
                        if item["http_status"] == 200:
                            self.assertIsNotNone(details)
                            self.assertEqual(messages, [])
                        else:
                            self.assertIsNone(details)
                            self.assertEqual(
                                [message.code for message in messages], [evidence["error_code"]]
                            )
                    else:
                        self.assertEqual(
                            error.parse_error_response(item["response"], settings_of(gateway)), []
                        )


if __name__ == "__main__":
    unittest.main()
