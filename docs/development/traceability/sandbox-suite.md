---
title: "Sandbox suite and evidence"
---

`sandbox_tests/` holds a suite that calls the DHL Freight SE sandbox, so the connector's rules stay anchored to live behaviour.
It is opt-in and sits outside `tests/`, so the default offline run never discovers it, and the wheel does not ship it.
[Running the sandbox suite](../../guides/sandbox-runs.md) covers credentials, variables, the booking budget, and narrowing a run.

## Segments

| Segment | Books | Covers |
|---------|-------|--------|
| `lookups` | nothing | PostalCode routes, `enforce` pre-flight, product matches including [special territories](../../concepts/destinations.md#special-territories), service points |
| `booking-approved` | 102, 401, 601, 118 | SE and DK lanes, 118 pre-flight, labels |
| `booking-pudo` | 103, 109 | service point as AccessPoint party |
| `booking-export` | 109, 112, 202, 205, 233, 601 | export lanes, special territories, customs handling |
| `booking-declarations` | 601, 202, 233 | SENT, EKAER, and UIT entries |
| `rejections` | nothing accepted | expected DHL error codes |

Before each booking a free product-match lookup, and for 109 a service-point lookup, checks that DHL offers the product on the lane, and the case skips otherwise; the few cases that book past this check exist to record DHL's answer.
The `rejections` cases build a valid request through the connector and `harness.mutated_request` changes the serialized TransportInstruction just before the call, so connector validation stays intact, and a response carrying a shipment id fails the test and reports the id as a finding.
Results, with every booking, rejection, and deviation from the product manual, are in [docs/notes/sandbox/sandbox-findings.md](../../notes/sandbox/sandbox-findings.md).

## Captures

Every live call writes its request and response as JSON to the capture directory set by `DHL_FREIGHT_SWEDEN_SANDBOX_CAPTURE_DIR`, with the `client-key` header and the client key redacted.
The account number stays in the captures, because DHL API Farm support traces sandbox bookings by it.
Sandbox bookings cannot be cancelled through the API, so `bookings.jsonl` in the capture directory records the product, shipment id, and timestamp of every attempt.

## Evidence

```mermaid
flowchart TD
  call["Live sandbox call"] --> capture["Capture directory: request and response JSON, client key redacted"]
  capture --> build["sandbox_tests/dhl_freight_sweden/evidence.py builds each CATALOG entry"]
  build --> fixture["Committed evidence file in tests/dhl_freight_sweden/fixtures/sandbox/"]
  fixture --> check["test_sandbox_evidence.py checks metadata, redaction, and parsing offline"]
  fixture --> cite["README, docs pages, and the findings note cite it"]
  cite --> links["test_doc_links.py checks the links resolve and every evidence file is linked"]
```

Each finding is backed by an evidence file in [`tests/dhl_freight_sweden/fixtures/sandbox/`](../../../tests/dhl_freight_sweden/fixtures/sandbox/) holding the redacted request and response bodies, the source capture path, and the capture's sha256.
A new sandbox finding gets its own evidence file and `CATALOG` entry, naming the capture files relative to the state directory, before anything cites it.
Rebuilding over the same captures reproduces the committed files byte for byte, so `git diff` after a rebuild shows only new or changed findings:

```bash
.venv/bin/python -m sandbox_tests.dhl_freight_sweden.evidence [--state-root DIR] [--out DIR] [NAME ...]
```

`--state-root` defaults to `$XDG_STATE_HOME` (`~/.local/state` when unset), `--out` to `tests/dhl_freight_sweden/fixtures/sandbox/`, and without names it builds every catalog entry.

## Coverage gaps

No sandbox booking yet covers:

- SPI
- 205 at or above its 2500.0 chargeable-weight minimum
- the customer's own declaration
- the joint declaration, including 109 with payer code 023
- VOEC
- destinations outside the EU VAT area other than NO and CH
