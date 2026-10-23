---
title: "Notification guard implementation plan"
created: 2026-10-23
---

# Notification guard implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guard the `additionalServices.notification` flag per product with a tri-state `notifications` connection setting (off/warn/enforce, default enforce), reading capability from the same product-matches lookup the matches guard already uses.

**Architecture:** The mapper change is one alias (`sms_notification` joins `email_notification` on `dhl_freight_sweden_notification`) plus one `ConnectionConfig` member. The guard logic lives in `karrio/providers/dhl_freight_sweden/product_matches.py` beside `check_booking_product`; the proxy factors the matches lookup into a helper shared by both guards, consults it for the booked product's `additionalServices` codes, and strips the flag in warn mode before the booking POST. No new HTTP call is ever made: the notification guard only consults an answer the matches guard already fetched.

**Tech stack:** Python stdlib `unittest`, karrio SDK (`lib.OptionEnum`, `models.Message`, `errors.ShippingSDKDetailedError`), `pyright` for types.

**Spec:** `docs/notes/integration/notification-guard.md` (approved 2026-10-23).
**Branch:** `notification-guard` (already checked out; verify with `git branch --show-current` before starting).
**Test commands:** `cd tests && ../.venv/bin/python -m unittest dhl_freight_sweden.<module> -v` for one module, `.venv/bin/python -m unittest discover -s tests` for the suite, `pyright` from the repo root.

---

### Task 1: Reduce the capture to a committed fixture

**Files:**
- Create: `tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-se-additional-services.json`
- Modify: `docs/notes/sandbox/sandbox-findings.md` (section `## Product matches`, reference definitions near `[l-pm-se]`)
- Move: `./productmatches.se_to_se.md` to `~/.local/state/karrio-dhl-freight-sweden/productmatches.se_to_se.md`

The fixture must satisfy `tests/dhl_freight_sweden/test_sandbox_evidence.py` exactly: `tuple(evidence) == METADATA_KEYS` (key order), `environment == "test-api.freight-logistics.dhl.com"` (the operator confirmed the sandbox host), exchange keys exactly `EXCHANGE_KEYS` plus optional `response_reduced`, `captured_at` matching `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$`, and sha256 values matching 64 lowercase hex. `test_doc_links.py` then requires the fixture to be linked from a checked document, so the findings-note entry lands in this task.

Deviation recorded 2026-10-23 (controller-approved during execution): the no-secrets scan in `test_sandbox_evidence.py` flags token-like values ≥30 characters, and five genuine DHL catalog additional-service codes cross that line (`deliveryMonitoringArrivedAtDhlTerminal`, `deliveryMonitoringNotCollectedByReciever`, `deliveryMonitoringCollectedByReciever`, `deliveryMonitoringOutForDelivery`, `deliveryWithoutProofOfDelivery`). The scan's exact-value exemption was extended to members of `additionalServices` lists (structure-aware, keeping the flat-`code` non-exemption the existing unit test asserts), committed as `test(evidence): exempt DHL additional-service catalog codes in the token scan` before the fixture commit so every commit stays green.

Task 2 deviation recorded 2026-10-23 (controller-approved during execution): the plan's `"additional_services": []` insertions into `ParsedProductMatches` are unreachable — the module's `to_dict` normalization (clear-empty) drops empty lists at both the parser wrap and the test comparison, the same convention that omits `short_name` when null. The normalized key is therefore present exactly when the product offers at least one additional service; the expected dicts stay at their committed shape, and consumers read the key as `(entry or {}).get("additional_services") or []` (Task 4's guard code already does).

- [ ] **Step 1: Write the reducer and run it**

Run from the repo root:

```bash
.venv/bin/python - <<'PY'
import datetime, hashlib, json, pathlib, re

capture = pathlib.Path("productmatches.se_to_se.md").read_text()
fences = re.findall(r"```[a-z]*\n(.*?)```", capture, re.S)
request, response = json.loads(fences[0]), json.loads(fences[1])
reduced = [
    {
        "product": {
            "code": match["product"]["code"],
            "name": match["product"]["name"],
            "shortName": match["product"].get("shortName"),
            "isDomestic": match["product"].get("isDomestic"),
            "additionalServices": [
                {"code": service["code"]}
                for service in match["product"].get("additionalServices") or []
            ],
        }
    }
    for match in response
]
now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
digest = hashlib.sha256(capture.encode()).hexdigest()
source = dict(
    path="~/.local/state/karrio-dhl-freight-sweden/productmatches.se_to_se.md",
    sha256=digest,
)
evidence = {
    "kind": "lookup",
    "summary": "Product matches for a domestic SE lane, kept for the additional services each product offers.",
    "captured_at": now,
    "environment": "test-api.freight-logistics.dhl.com",
    "endpoint": "POST /productapi/v1/productmatches",
    "product": None,
    "route": "SE -> SE",
    "booking_id": None,
    "error_code": None,
    "http_status": 200,
    "captured_by": "operator lookup via the Product API, manually reduced",
    "redaction": "no redaction needed: the response body carries catalog constants and catalog ids only, and the request carries the two lane postcodes kept per fixture convention",
    "account_number_restored": None,
    "exchanges": [
        {
            "endpoint": "POST /productapi/v1/productmatches",
            "http_status": 200,
            "date": now,
            "date_basis": "operator capture time",
            "request_source": source,
            "response_source": source,
            "request": request,
            "response": reduced,
            "response_reduced": "each match keeps product code, name, shortName, isDomestic, and the additionalServices codes; the full body is identified by response_source.sha256",
        }
    ],
}
out = pathlib.Path("tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-se-additional-services.json")
out.write_text(json.dumps(evidence, indent=1) + "\n")
print(out, "products:", [m["product"]["code"] for m in reduced])
PY
```

Expected: prints the eight product codes `['502', '118', '104', '102', '402', '211', '401', '103']`.

- [ ] **Step 2: Move the original capture out of the repo**

```bash
mv productmatches.se_to_se.md ~/.local/state/karrio-dhl-freight-sweden/productmatches.se_to_se.md
```

- [ ] **Step 3: Record the lookup in the findings note**

In `docs/notes/sandbox/sandbox-findings.md`, append to the end of the `## Product matches` section (which starts around line 270):

```markdown
On 2026-10-23 an operator lookup for SE to SE kept each product's additional services ([lookup-product-matches-se-se-additional-services.json][l-pm-se-as]): `notification` (Avisering) is listed for 102 and 211 only, and the "via SMS or e-mail" wording belongs to the separate `deliveryMonitoring*` family.
```

Add the reference definition beside the existing `[l-pm-se]` definition (around line 524):

```markdown
[l-pm-se-as]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-se-additional-services.json
```

- [ ] **Step 4: Verify the evidence and link tests**

```bash
cd tests && ../.venv/bin/python -m unittest dhl_freight_sweden.test_sandbox_evidence tests.dhl_freight_sweden.test_doc_links -v
```

Expected: all pass. If `test_sandbox_evidence` reports an envelope mismatch, fix the fixture to the exact key order or value it names and rerun; do not weaken the test.

- [ ] **Step 5: Commit**

```bash
git add tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-se-additional-services.json docs/notes/sandbox/sandbox-findings.md
git commit -m "feat(evidence): reduce the SE-SE productmatches capture to a fixture"
```

---

### Task 2: Expose per-product additional services in the matches parser

**Files:**
- Modify: `karrio/providers/dhl_freight_sweden/product_matches.py` (function `_normalize_product`)
- Test: `tests/dhl_freight_sweden/test_product_matches.py`

- [ ] **Step 1: Update the existing expected shape and add a failing test**

In `tests/dhl_freight_sweden/test_product_matches.py`, add `"additional_services": []` to both product dicts in `ParsedProductMatches` (the `109` entry around line 407 and the `601` entry around line 453 — the inline response literal contains no `additionalServices`, so both normalize to the empty list). Insert the key directly after `"code"` in each dict.

Then add this test to the test class that holds `test_parse_product_matches_response` (around line 105):

```python
    def test_parse_product_matches_additional_services(self):
        response = lib.Deserializable(
            [
                {
                    "product": {
                        "code": "102",
                        "name": "DHL Paket",
                        "additionalServices": [
                            {"code": "notification", "name": "Notification"},
                            {"code": "signature", "name": "Signature"},
                        ],
                    }
                }
            ]
        )

        products, messages = product_matches.parse_product_matches_response(
            response, settings_of(gateway)
        )

        self.assertEqual(messages, [])
        self.assertEqual(products[0]["additional_services"], ["notification", "signature"])
```

The file already imports `lib`, `gateway`, and `settings_of`; if `settings_of` is not imported, add it to the existing `.fixture` import line.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd tests && ../.venv/bin/python -m unittest dhl_freight_sweden.test_product_matches -v
```

Expected: FAIL — `test_parse_product_matches_additional_services` with a `KeyError: 'additional_services'`, and `test_parse_product_matches_response` with a dict inequality naming the missing key.

- [ ] **Step 3: Implement the parser extension**

In `_normalize_product` in `karrio/providers/dhl_freight_sweden/product_matches.py`, add after the `"code"` entry in the returned dict:

```python
            "additional_services": [
                item.get("code") for item in product.get("additionalServices") or []
            ],
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd tests && ../.venv/bin/python -m unittest dhl_freight_sweden.test_product_matches -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add karrio/providers/dhl_freight_sweden/product_matches.py tests/dhl_freight_sweden/test_product_matches.py
git commit -m "feat(matches): expose per-product additional services in the matches parser"
```

---

### Task 3: Alias `sms_notification` and add the `notifications` setting

**Files:**
- Modify: `karrio/providers/dhl_freight_sweden/units.py` (class `ConnectionConfig` around line 43, unified mapping around line 962)
- Test: `tests/dhl_freight_sweden/test_option_flags.py`, `tests/dhl_freight_sweden/test_services.py`

- [ ] **Step 1: Write the failing tests**

In `tests/dhl_freight_sweden/test_option_flags.py`, add beside `test_unified_alias_is_read_strictly` (line 97):

```python
    def test_sms_notification_alias_is_read_strictly(self):
        for value, expected in [("true", True), ("false", False)]:
            with self.subTest(value=value):
                options = provider_units.shipping_options_initializer(
                    {"sms_notification": value}
                )

                self.assertIs(options.dhl_freight_sweden_notification.state, expected)

    def test_notifications_setting_defaults_to_enforce(self):
        self.assertEqual(
            str(_gateway({}).settings.connection_config.notifications.state),
            "enforce",
        )
```

Add `_gateway` to the `.fixture` import line at the top of the file.

In `tests/dhl_freight_sweden/test_services.py`, change line 30 from:

```python
        unified_aliases = {"email_notification", "insurance"}
```

to:

```python
        unified_aliases = {"email_notification", "insurance", "sms_notification"}
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd tests && ../.venv/bin/python -m unittest dhl_freight_sweden.test_option_flags tests.dhl_freight_sweden.test_services -v
```

Expected: FAIL — `sms_notification` is dropped by the initializer (state `None`, not `True`), and `connection_config.notifications` raises `AttributeError`.

- [ ] **Step 3: Implement both units.py changes**

In `karrio/providers/dhl_freight_sweden/units.py`, add to `ConnectionConfig` after the `product_matches` member (line 45):

```python
    # Booking pre-flight for the notification additional service: off sends
    # the flag verbatim, warn drops the flag and annotates the shipment when
    # the product's matches answer lists no notification service, enforce
    # refuses the booking before the transport instruction is sent.
    notifications = lib.OptionEnum(
        "notifications", ServabilityMode, default="enforce"
    )
```

In the unified mapping at the bottom of `ShippingOption` (line 962), add:

```python
    sms_notification = dhl_freight_sweden_notification
```

directly above the existing `email_notification` alias line.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd tests && ../.venv/bin/python -m unittest dhl_freight_sweden.test_option_flags tests.dhl_freight_sweden.test_services -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add karrio/providers/dhl_freight_sweden/units.py tests/dhl_freight_sweden/test_option_flags.py tests/dhl_freight_sweden/test_services.py
git commit -m "feat(options): alias sms_notification and add the notifications setting"
```

---

### Task 4: The notification guard functions

**Files:**
- Modify: `karrio/providers/dhl_freight_sweden/product_matches.py`
- Create: `tests/dhl_freight_sweden/test_notification_guard.py`
- Modify: `tests/dhl_freight_sweden/test_option_flags.py` (controller addition below)

Controller addition 2026-10-23 (from Task 3's quality review): this task also moves `test_notifications_setting_defaults_to_enforce` out of `tests/dhl_freight_sweden/test_option_flags.py` into the new `test_notification_guard.py` — the guard module owns connection-config coverage, matching the `test_default_mode_is_enforce` precedent in `test_product_match_guard.py` — removing the now-unused `_gateway` import from `test_option_flags.py` if nothing else in that file uses it, and adds `"sms_notification": 1.0` beside `email_notification` in both the input and the expected dict of `test_invalid_flags_names_each_invalid_option`.

- [ ] **Step 1: Write the failing guard-function tests**

Create `tests/dhl_freight_sweden/test_notification_guard.py`:

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd tests && ../.venv/bin/python -m unittest dhl_freight_sweden.test_notification_guard -v
```

Expected: FAIL with `ImportError: cannot import name 'NotificationNotOfferedError'`.

- [ ] **Step 3: Implement the guard functions**

In `karrio/providers/dhl_freight_sweden/product_matches.py`, add after `ProductNotOfferedError` (line 30):

```python
class NotificationNotOfferedError(errors.ShippingSDKDetailedError):
    """Raised before booking when the product offers no notification service."""

    code = "SHIPPING_SDK_FIELD_ERROR"
```

Add after `criteria_unavailable_warning` (after line 333):

```python
def notification_unverified_warning(
    reason: str, settings: provider_utils.Settings
) -> models.Message:
    """The warning for a notification flag whose support was not verified."""
    return models.Message(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        code="notification_availability_unverified",
        level="warning",
        message=(
            f"Notification support was not verified ({reason}); "
            "the booking proceeded without the check"
        ),
        details=dict(reason=reason),
    )
```

Add after `check_booking_product` (after line 377):

```python
def check_booking_notification(
    criteria: dict,
    product: str,
    products: typing.List[dict],
    messages: typing.List[models.Message],
    settings: provider_utils.Settings,
    mode: str,
) -> typing.List[models.Message]:
    """Apply the notification guard to a product matches answer.

    A lookup that produced messages leaves the flag's support unverified and
    yields a warning in warn and enforce alike. A product whose matches entry
    does not list the notification additional service raises
    ``NotificationNotOfferedError`` in ``enforce`` and yields a warning in
    ``warn``; the caller strips the flag before booking in warn. A product
    missing from the answer returns no message: the product guard has
    already reported the product itself.
    """
    if any(messages):
        return [
            notification_unverified_warning(
                "product matches lookup failed: "
                + "; ".join(str(m.message) for m in messages),
                settings,
            )
        ]

    entry = next(
        (item for item in products if str(item.get("code")) == product), None
    )
    services = (entry or {}).get("additional_services") or []
    if entry is None or "notification" in services:
        return []

    message = _notification_not_offered_message(criteria, product, services)
    if mode == provider_units.ServabilityMode.enforce:
        raise NotificationNotOfferedError(
            message,
            details={
                "notification": dict(
                    code="notification_not_offered", message=message
                )
            },
        )

    return [
        models.Message(
            carrier_name=settings.carrier_name,
            carrier_id=settings.carrier_id,
            code="notification_not_offered",
            level="warning",
            message=message,
            details=dict(product=product, additional_services=services),
        )
    ]
```

Add beside `_not_offered_message` (after line 439):

```python
def _notification_not_offered_message(
    criteria: dict,
    product: str,
    services: typing.List[str],
) -> str:
    names = {
        service.value: service.name
        for service in provider_units.ShippingService.__members__.values()
    }
    origin, destination = (
        f"{party['address']['countryCode']} {party['address']['postalCode']}"
        for party in criteria["parties"]
    )
    listing = ", ".join(services) if services else "none"

    return (
        f"Product {product} ({names.get(product, product)}) does not offer the "
        f"notification service from {origin} to {destination} by DHL product "
        "matches; the notification option (email_notification, "
        "sms_notification, or dhl_freight_sweden_notification) was set "
        f"explicitly. Additional services offered for this product: {listing}."
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd tests && ../.venv/bin/python -m unittest dhl_freight_sweden.test_notification_guard -v
```

Expected: all five guard-function tests pass.

- [ ] **Step 5: Commit**

```bash
git add karrio/providers/dhl_freight_sweden/product_matches.py tests/dhl_freight_sweden/test_notification_guard.py
git commit -m "feat(guard): refuse or warn the notification flag from the matches answer"
```

---

### Task 5: Wire the guard into the proxy

**Files:**
- Modify: `karrio/mappers/dhl_freight_sweden/proxy.py` (methods `create_shipment`, `_product_match_messages`; new methods `_match_answer`, `_notification_messages`)
- Test: `tests/dhl_freight_sweden/test_notification_guard.py`

Controller addition 2026-10-23 (from Task 4's quality review): while appending the proxy tests, also drop the unused `import typing` from `tests/dhl_freight_sweden/test_notification_guard.py` and add a guard-function test covering a product entry that exists with an absent `additional_services` key (the Task 2 clear-empty shape): it refuses in enforce with the listing sentence ending "Additional services offered for this product: none."

Task 5 deviation recorded 2026-10-23 (controller-approved during execution): the plan's original warn-mode setUp `_gateway({"product_matches": "warn"})` left `notifications` at its `enforce` default, which refuses the 118 booking instead of warning — the warn test's assertions uniquely require `notifications: "warn"` as well, so the setUp is `_gateway({"product_matches": "warn", "notifications": "warn"})`.

- [ ] **Step 1: Write the failing proxy-level tests**

Append to `tests/dhl_freight_sweden/test_notification_guard.py` (new imports at top; reuse the existing `CRITERIA`-style constants). Add to the imports:

```python
import json
from unittest.mock import patch

import karrio.core.models as models
import karrio.sdk as karrio
from karrio.mappers.dhl_freight_sweden import proxy as connector_proxy
from karrio.providers.dhl_freight_sweden.product_matches import ProductNotOfferedError

from .fixture import as_dict, http_error, proxy_of
from .test_product_match_guard import _answers
from .test_shipment import _payload, _recipient_se
```

Add module constants after `REFUSAL_118`:

```python
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


def _book(gateway_, payload: dict, *responses):
    with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
        mock.side_effect = _answers(*responses)
        result = (
            karrio.Shipment.create(models.ShipmentRequest(**payload))
            .from_(gateway_)
            .parse()
        )
    return result, [call.kwargs["url"] for call in mock.call_args_list], mock
```

Add the proxy test class:

```python
class TestNotificationGuardBooking(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.enforce = _gateway({"product_matches": "enforce"})
        self.warn = _gateway({"product_matches": "warn", "notifications": "warn"})

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

    def test_off_mode_sends_the_flag_verbatim(self):
        off = _gateway({"product_matches": "off", "notifications": "off"})
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

    def test_starved_lookup_warns_unverified_and_sends_the_flag(self):
        starved = _gateway({"product_matches": "off"})
        (details, messages), urls, _ = _book(
            starved, PAYLOAD_118, *_booking_answers()
        )

        self.assertIsNotNone(details)
        (warning,) = messages
        self.assertEqual(warning.code, "notification_availability_unverified")
        self.assertEqual(warning.level, "warning")
        self.assertEqual(
            warning.message,
            "Notification support was not verified (the product matches "
            "lookup did not run); the booking proceeded without the check",
        )
        self.assertFalse(any(url.endswith(MATCHES_PATH) for url in urls))

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
```

Note: `_expected_refusal` pins the 118 service name `dhl_freight_sweden_hemleverans_paket_b2c`; the fixture lane postcodes are the recipient `_recipient_se` uses (SE 11143 to SE 41103, the same pair `test_product_match_guard.py` asserts for its domestic payload). If the payload's consignee postal code differs, adjust the lane string in `_expected_refusal` to the actual pair — check `_recipient_se` in `tests/dhl_freight_sweden/test_shipment.py` first and keep the expected message in sync with it.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd tests && ../.venv/bin/python -m unittest dhl_freight_sweden.test_notification_guard -v
```

Expected: the five guard-function tests pass; the new booking tests FAIL — the booking succeeds with no warning (no guard wired), and `test_enforce_refuses_118_before_booking` fails because no error is raised.

- [ ] **Step 3: Implement the proxy wiring**

In `karrio/mappers/dhl_freight_sweden/proxy.py`, first replace the body of `create_shipment` between the `headers` assignment and the `booking = lib.request(...)` call:

```python
        data = provider_utils.to_dict(request.serialize())
        criteria = provider_product_matches.booking_match_criteria(data)
        match_answer = self._match_answer(criteria)

        warnings = [
            *self._product_match_messages(data, request, criteria, match_answer),
            *self._notification_messages(data, criteria, match_answer),
            *self._destination_route_messages(request),
        ]
```

and change the booking call's `data` argument from `lib.to_json(request.serialize())` to `lib.to_json(data)`. Extend the method docstring's guard sentence from "Two config-gated pre-flights run first, product matches and then address validation" to "Three config-gated pre-flights run first, product matches, the notification guard, and then address validation".

Second, replace `_product_match_messages` wholesale:

```python
    def _product_match_messages(
        self,
        data: dict,
        request: lib.Serializable,
        criteria: typing.Any,
        answer: typing.Optional[
            typing.Tuple[typing.List[dict], typing.List[models.Message]]
        ],
    ) -> typing.List[models.Message]:
        """Run the config-gated product matches booking guard.

        Off mode and ``PRODUCT_MATCH_UNGUARDED`` products skip the lookup
        silently; a booking whose consignor, or whose consignee and access
        point, lack a postal or country code skips it with a warning. A lookup
        that raises (a non-JSON HTTP error body, a network error) is turned
        into a message, so it leaves availability unverified rather than
        failing the booking.
        """
        mode = _preflight_mode(self.settings.connection_config.product_matches.state)

        if mode == "off" or criteria is None:
            return []

        if isinstance(criteria, provider_product_matches.CriteriaUnavailable):
            return [
                provider_product_matches.criteria_unavailable_warning(
                    criteria, self.settings
                )
            ]

        products, messages = answer or ([], [])
        return provider_product_matches.check_booking_product(
            criteria,
            str(data.get("productCode")),
            products,
            messages,
            self.settings,
            mode,
            (request.ctx or {}).get("separate_agreement"),
        )

    def _match_answer(
        self, criteria: typing.Any
    ) -> typing.Optional[
        typing.Tuple[typing.List[dict], typing.List[models.Message]]
    ]:
        """The parsed product matches answer for the booking guards.

        The lookup runs only for the product guard's own trigger (mode not
        off and criteria available); the notification guard consults the
        answer and never triggers a lookup of its own, so a booking's HTTP
        behavior is unchanged.
        """
        mode = _preflight_mode(self.settings.connection_config.product_matches.state)

        if (
            mode == "off"
            or criteria is None
            or isinstance(criteria, provider_product_matches.CriteriaUnavailable)
        ):
            return None

        try:
            return provider_product_matches.parse_product_matches_response(
                self.find_product_matches(
                    lib.Serializable(criteria, provider_utils.to_dict)
                ),
                self.settings,
            )
        except Exception as exception:
            return [], [
                provider_product_matches.lookup_failure(exception, self.settings)
            ]

    def _notification_messages(
        self,
        data: dict,
        criteria: typing.Any,
        answer: typing.Optional[
            typing.Tuple[typing.List[dict], typing.List[models.Message]]
        ],
    ) -> typing.List[models.Message]:
        """Run the config-gated notification booking guard.

        The guard triggers only when the serialized request carries a truthy
        ``additionalServices.notification`` (an explicit false passes through)
        and the product is one the matches guard covers. With no answer in
        hand the booking proceeds with an unverified warning in warn and
        enforce alike; in warn mode a definitive negative strips the flag
        before the booking POST.
        """
        mode = _preflight_mode(self.settings.connection_config.notifications.state)
        flag = (data.get("additionalServices") or {}).get("notification")

        if mode == "off" or not flag or criteria is None:
            return []

        if isinstance(criteria, provider_product_matches.CriteriaUnavailable):
            return [
                provider_product_matches.notification_unverified_warning(
                    f"{criteria.reason} for product matches", self.settings
                )
            ]

        if answer is None:
            return [
                provider_product_matches.notification_unverified_warning(
                    "the product matches lookup did not run", self.settings
                )
            ]

        products, messages = answer
        warnings = provider_product_matches.check_booking_notification(
            criteria,
            str(data.get("productCode")),
            products,
            messages,
            self.settings,
            mode,
        )

        if mode == "warn" and any(
            message.code == "notification_not_offered" for message in warnings
        ):
            data.setdefault("additionalServices", {}).pop("notification", None)

        return warnings
```

Place `_match_answer` and `_notification_messages` after `_product_match_messages`, before `find_product_matches`.

- [ ] **Step 4: Run the full suite and pyright**

```bash
.venv/bin/python -m unittest discover -s tests
pyright
```

Expected: the whole suite passes (including `test_product_match_guard.py` against the refactored proxy) and pyright reports no new errors.

- [ ] **Step 5: Commit**

```bash
git add karrio/mappers/dhl_freight_sweden/proxy.py tests/dhl_freight_sweden/test_notification_guard.py
git commit -m "feat(proxy): wire the notification guard into create_shipment"
```

---

### Task 6: Document the setting

**Files:**
- Modify: `README.md` (settings table row after `address_validation`, options row `dhl_freight_sweden_notification`)
- Modify: `docs/concepts/booking-rules.md` (new section after `## Product matches`)

- [ ] **Step 1: README settings row**

Insert after the `address_validation` row of the settings table:

```markdown
| `notifications` | `enforce` | `off`, `warn`, or `enforce` the notification flag check before every booking, which refuses or drops the notification additional service when the product's matches answer does not list it, as [Booking rules](docs/concepts/booking-rules.md#notification-guard) describes. |
```

- [ ] **Step 2: README options row**

Change the options-table row:

```markdown
| `dhl_freight_sweden_notification`, `..._pre_advice`, `..._tail_lift_unloading` | boolean | DHL additional services; karrio's `email_notification` maps to the first |
```

to:

```markdown
| `dhl_freight_sweden_notification`, `..._pre_advice`, `..._tail_lift_unloading` | boolean | DHL additional services; karrio's `email_notification` and `sms_notification` map to the first |
```

- [ ] **Step 3: Booking-rules section**

Insert a new section after the `## Product matches` section in `docs/concepts/booking-rules.md`:

```markdown
## Notification guard

The `notifications` connection setting guards the notification additional service that karrio's `email_notification` and `sms_notification` options and the native `dhl_freight_sweden_notification` option set on the transport instruction.
`enforce`, the default, fails with `NotificationNotOfferedError` keyed by `notification` and sends no booking when the product's product matches answer does not list the `notification` service, `warn` drops the flag and books with a `notification_not_offered` warning, and `off` sends the flag verbatim.
The message names the product, the lane, and the additional services the answer does list.
The capability is read from the same product matches answer as [product matches](#product-matches): one lookup serves both guards, so no extra call is made, and when no answer is available — the lookup did not run because `product_matches` is `off`, or it failed — the booking proceeds with a `notification_availability_unverified` warning and the flag unchanged, like a failed product matches lookup.
An explicit `notification: false` passes through untouched in every mode.
The sandbox SE to SE answer lists `notification` for 102 and 211 only, and neither `notification` nor any delivery monitoring service for 118 ([lookup-product-matches-se-se-additional-services.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-se-additional-services.json)).
The Product API's "via SMS or e-mail" wording belongs to the separate `deliveryMonitoring*` services, a wire concept the notification flag does not touch.
```

- [ ] **Step 4: Verify the docs tests**

```bash
cd tests && ../.venv/bin/python -m unittest dhl_freight_sweden.test_doc_links -v
```

Expected: pass (the fixture remains linked from the findings note; the new booking-rules link resolves).

- [ ] **Step 5: Commit**

```bash
git add README.md docs/concepts/booking-rules.md
git commit -m "docs: document the notifications guard setting"
```

---

### Task 7: Land the change

**Files:**
- Modify: `CLAUDE.md` (Current State), `docs/notes/integration/notification-guard.md` (Status), `docs/notes/README.md` (row status)
- Delete: `docs/notes/integration/notification-guard-plan.md` (this plan)

- [ ] **Step 1: Append the Current State entry to CLAUDE.md**

```markdown
- 2026-10-23: the notification additional service is guarded per product by the `notifications` connection setting (off/warn/enforce, default enforce); karrio's `sms_notification` joined `email_notification` as an alias of `dhl_freight_sweden_notification`, whose flag is refused up front with NotificationNotOfferedError (details key `notification`, message code `notification_not_offered`) when the product-matches answer lists no `notification` service, dropped with that warning in warn mode, and sent verbatim in off mode or without an answer (`notification_availability_unverified`; an explicit false passes through); the capability comes from the same single matches lookup the product guard uses, `_match_answer` in the proxy, and `_normalize_product` now exposes per-product `additional_services`; a live 118 rejection (24000, `notification`) motivated the guard, and the committed SE-SE capture (lookup-product-matches-se-se-additional-services.json) lists `notification` for 102 and 211 only — the Product API's SMS/e-mail channels live in the separate `deliveryMonitoring*` family, recorded as a follow-up decision in docs/notes/integration/notification-guard.md; tests in tests/dhl_freight_sweden/test_notification_guard.py
```

- [ ] **Step 2: Flip the design note and index**

In `docs/notes/integration/notification-guard.md`, change the Status opening to `Implemented on 2026-10-23.` keeping the rest of the section, and update the two "is to be committed"/"moves to" sentences to plain past tense ("was committed", "moved to").
In `docs/notes/README.md`, change the notification-guard row's Status from `active` to `implemented` and Last changed to `2026-10-23`, and delete the plan file's row.

- [ ] **Step 3: Delete this plan**

```bash
git rm docs/notes/integration/notification-guard-plan.md
```

- [ ] **Step 4: Final verification**

```bash
.venv/bin/python -m unittest discover -s tests
pyright
```

Expected: the full suite and pyright pass.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/notes/integration/notification-guard.md docs/notes/README.md
git commit -m "docs: land the notification guard"
```

- [ ] **Step 6: Integrate**

Ask the user, then fast-forward main:

```bash
git checkout main
git merge --ff-only notification-guard
```

---

## Self-review record

Spec coverage: the note's five decisions map to Task 3 (tri-state + alias + truthy trigger in `_notification_messages`' `not flag` check — an explicit false is falsy and passes through), Tasks 4-5 (dynamic capability, warn strips, enforce refuses, unverified semantics, single lookup), Task 1 (fixture + state-dir move), Task 6 (README/booking-rules), Task 7 (status flip, CLAUDE.md). The 24000 rejection and 118 no-stage-2-rescue facts live in the design note, which this plan implements without change.
Type consistency: `notification_unverified_warning(reason, settings)` argument order is used identically in `check_booking_notification` and `_notification_messages`; `check_booking_notification(criteria, product, products, messages, settings, mode)` matches both call sites; `_match_answer` returns `None` or `(products, messages)` and both consumers destructure accordingly.
