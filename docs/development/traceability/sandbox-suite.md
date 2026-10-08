---
title: "Sandbox suite and evidence"
---

`sandbox_tests/` holds a suite that calls the DHL Freight SE sandbox, so the connector's rules stay anchored to live behaviour.
It is opt-in and sits outside `tests/`, so the default offline run never discovers it, and the wheel does not ship it.

## Running

Credentials come from the environment only, so export them from a git-ignored `.env` before running:

```bash
set -a; . ./.env; set +a
DHL_FREIGHT_SWEDEN_SANDBOX=1 .venv/bin/python -m unittest discover -v -s sandbox_tests
```

Every test skips unless `DHL_FREIGHT_SWEDEN_SANDBOX=1` and `KARRIO_DHL_FREIGHT_SWEDEN_CLIENT_KEY` are set, and the booking segments also skip without `KARRIO_DHL_FREIGHT_SWEDEN_ACCOUNT_NUMBER`.
The gateway always runs in test mode on the connector's sandbox host `test-api.freight-logistics.dhl.com`, no variable can change the host, and the run fails if a carrier call targets any other host.

| Variable | Default | Effect |
|----------|---------|--------|
| `DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS` | `lookups` | comma-separated segments to run |
| `DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS` | all | comma-separated product codes the booking segments may book |
| `DHL_FREIGHT_SWEDEN_SANDBOX_COUNTRIES` | all | comma-separated ISO recipient country codes the booking segments may book to |
| `DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS` | `30` | booking attempts allowed in one process |
| `DHL_FREIGHT_SWEDEN_SANDBOX_CAPTURE_DIR` | `$XDG_STATE_HOME/karrio-dhl-freight-sweden/sandbox/<YYYYmmdd-HHMMSS>` | capture directory (`~/.local/state` when `XDG_STATE_HOME` is unset) |

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

## Booking budget and narrowing

Each booking attempt, rejections included, is counted before the TransportInstruction call, and once the budget is spent the remaining booking tests skip.
To book a single product, lane, or case, narrow the selectors and add `-k`, which is repeatable and matches a substring of the test id:

```bash
DHL_FREIGHT_SWEDEN_SANDBOX=1 DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS=booking-export \
  DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS=112 DHL_FREIGHT_SWEDEN_SANDBOX_COUNTRIES=NO DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=1 \
  .venv/bin/python -m unittest discover -v -s sandbox_tests -k test_book_112_no_customs_standard
```

The selectors alone cannot separate two cases that share a product and country, so `-k` pins exactly one case.

## Captures

Every live call writes its request and response as JSON to the capture directory, with the `client-key` header and the client key redacted.
The account number stays in the captures, because DHL API Farm support traces sandbox bookings by it.
Sandbox bookings cannot be cancelled through the API, so `bookings.jsonl` in the capture directory records the product, shipment id, and timestamp of every attempt.

## Evidence

Each finding is backed by an evidence file in [`tests/dhl_freight_sweden/fixtures/sandbox/`](../../../tests/dhl_freight_sweden/fixtures/sandbox/) holding the redacted request and response bodies, the source capture path, and the capture's sha256, and `tests/dhl_freight_sweden/test_sandbox_evidence.py` checks those files offline.
A new sandbox finding gets its own evidence file there before the README or the findings note cites it.
`sandbox_tests/dhl_freight_sweden/evidence.py` builds those files from the captures: its `CATALOG` names each evidence file and the capture files behind it, relative to the state directory.
Rebuilding over the same captures reproduces the committed files byte for byte, so `git diff` after a rebuild shows only new or changed findings:

```bash
.venv/bin/python -m sandbox_tests.dhl_freight_sweden.evidence [--state-root DIR] [--out DIR] [NAME ...]
```

`--state-root` defaults to `$XDG_STATE_HOME` (`~/.local/state` when unset), `--out` to `tests/dhl_freight_sweden/fixtures/sandbox/`, and without names it builds every catalog entry.

## Coverage gaps

Still unbooked: SPI, a 205 booking at or above its 2500.0 chargeable-weight minimum, the customer's own declaration, the joint declaration including 109 with payer code 023, VOEC, and destinations outside the EU VAT area other than NO and CH.
