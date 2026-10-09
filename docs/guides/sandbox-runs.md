---
title: "Running the sandbox suite"
---

This guide runs the opt-in suite in `sandbox_tests/` against the DHL Freight SE sandbox, and narrows it to the bookings you need.
[Sandbox suite and evidence](../development/traceability/sandbox-suite.md) describes the segments, the captures, and how captures become committed evidence.

## Run the suite

Credentials come from the environment only, so export them from a git-ignored `.env` before running:

```bash
set -a; . ./.env; set +a
DHL_FREIGHT_SWEDEN_SANDBOX=1 .venv/bin/python -m unittest discover -v -s sandbox_tests
```

Every test skips unless `DHL_FREIGHT_SWEDEN_SANDBOX=1` and `KARRIO_DHL_FREIGHT_SWEDEN_CLIENT_KEY` are set, and the booking segments also skip without `KARRIO_DHL_FREIGHT_SWEDEN_ACCOUNT_NUMBER`.
Bookings of the international products 202, 205, 233, SPI, and 601 also skip without `KARRIO_DHL_FREIGHT_SWEDEN_INTERNATIONAL_ACCOUNT_NUMBER`, the international customer number they send as the consignor id.
The gateway always runs in test mode on the connector's sandbox host `test-api.freight-logistics.dhl.com`, no variable can change the host, and the run fails if a carrier call targets any other host.

| Variable | Default | Effect |
|----------|---------|--------|
| `DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS` | `lookups` | comma-separated [segments](../development/traceability/sandbox-suite.md#segments) to run |
| `DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS` | all | comma-separated product codes the booking segments may book |
| `DHL_FREIGHT_SWEDEN_SANDBOX_COUNTRIES` | all | comma-separated ISO recipient country codes the booking segments may book to |
| `DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS` | `30` | booking attempts allowed in one process |
| `DHL_FREIGHT_SWEDEN_SANDBOX_CAPTURE_DIR` | `$XDG_STATE_HOME/karrio-dhl-freight-sweden/sandbox/<YYYYmmdd-HHMMSS>` | capture directory (`~/.local/state` when `XDG_STATE_HOME` is unset) |

## Narrow a run within the booking budget

Each booking attempt, rejections included, is counted before the TransportInstruction call, and once the budget is spent the remaining booking tests skip.
To book a single product, lane, or case, narrow the selectors and add `-k`, which is repeatable and matches a substring of the test id:

```bash
DHL_FREIGHT_SWEDEN_SANDBOX=1 DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS=booking-export \
  DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS=112 DHL_FREIGHT_SWEDEN_SANDBOX_COUNTRIES=NO DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=1 \
  .venv/bin/python -m unittest discover -v -s sandbox_tests -k test_book_112_no_customs_standard
```

The selectors alone cannot separate two cases that share a product and country, so `-k` pins exactly one case.
