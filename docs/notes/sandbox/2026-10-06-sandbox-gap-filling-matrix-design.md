---
title: "Gap-filling sandbox matrix design, 2026-10-06"
---

Status: design approved in session on 2026-10-06; not yet implemented.
Line references point at `main` commit f7b4eba, where the supporting recon was done.

## Goal

Expand sandbox booking coverage for products 202 (Road Freight Standard), 205 (Road Freight Direct), 233 (Road Freight Priority), 601 (Home Delivery International B2C), 401 (Home Delivery B2C), 109 (Parcel Connect B2C), and 112 (Parcel Connect Plus) across the domestic, intra-EU, and extra-EU lane classes, filling every product-by-lane-class gap that lacks booked evidence.
Relax the suite's booking-budget self-limit so the whole matrix can run in one pass while the `bookings.jsonl` journal keeps recording every spend.
The spend policy is the user's choice: full matrix, spend freely.
The probe-first gate, the never-retry rule for rejected bookings, and all transport guards stay in force, and the API has no cancel endpoint, so every booking is permanent.

## Coverage the matrix fills

The recon of 2026-10-06 found:

- 202 has one extra-EU booking (SE to GB Northern Ireland, without customs, `sandbox_tests/dhl_freight_sweden/test_booking_export.py:229-236`) and neither an intra-EU booking nor a customs-carrying booking.
- 205 has no coverage of any kind and was never matched by a product-matches probe (`karrio/providers/dhl_freight_sweden/units.py:299-300`).
- 233 appears in matches fixtures only and was never booked.
- 601 covers intra-EU DK, HU with EKAER, and RO with UIT, but no extra-EU lane.
- 401 was never booked; it is a domestic-only product (`units.py:1153-1160`) and the SE-to-SE matches fixture lists it as offered.
- 109 covers PL, RO, HU, NO with customs Full Service, DK ParcelShop, FI Åland, a service-point PL booking, and rejection paths.
- 112 covers PL, RO, HU, NO with Full Service, FR, a forced GB case (rejected 22005 and 22026, recorded), Åland pre-booking refusals, and rejection paths.

## Case matrix

| # | Case | Segment | Lane class | Notes |
|---|------|---------|------------|-------|
| 1 | `test_book_401_domestic` | booking-approved | SE to SE | First 401 booking; default payer `1` (`units.py:500-502`); offered per the SE-to-SE matches fixture. |
| 2 | `test_book_202_dk` | booking-export | intra-EU | Explicit DAP payer code; 202 has no default (`units.py:458-460`, `shipment/create.py:783-793`). |
| 3 | `test_book_202_no_customs_full` | booking-export | extra-EU | Customs Full Service; first customs-carrying freight booking. |
| 4 | `test_book_205_dk` | booking-export | intra-EU | DAP (`units.py:474-476`); skips for free if probes still never offer 205. |
| 5 | `test_book_205_no_customs_full` | booking-export | extra-EU | Customs Full Service. |
| 6 | `test_book_233_dk` | booking-export | intra-EU | DAP; first 233 booking. |
| 7 | `test_book_233_no_customs_full` | booking-export | extra-EU | Customs Full Service. |
| 8 | `test_book_601_no_customs_full` | booking-export | extra-EU | Fills 601's only lane-class gap; DAP as in the existing DK booking. |
| 9 | `test_book_112_no_customs_standard` | booking-export | extra-EU | Customs Standard with EORI; only Full Service is evidenced today (`test_booking_export.py:182-183`). |
| 10 | `test_book_109_no_customs_standard` | booking-export | extra-EU | Customs Standard with EORI, only if the findings note's Untested list names it (`docs/notes/sandbox/sandbox-findings.md:226-235`). |
| 11 | `test_book_205_no_forced` | booking-export | extra-EU | Conditional: only if cases 4 and 5 both skip as unoffered; `require_product_match=False` with budget 1 records DHL's own answer, the 112 GB precedent (`test_booking_export.py:190-193`). |

At most ten bookings run: cases 1 through 10 when the probes offer 205 (case 11 then never fires), or eight plus the forced case 11 when they do not.
The extra-EU anchor is NO, already a proven lane for 109 and 112; the intra-EU anchor is DK, already proven for 601.

## Prerequisite code changes

Add Incoterm entries for the freight products to the customs helper: `INCOTERMS = {"109": "DAP", "112": "DDP"}` at `test_booking_export.py:32` gains `"202"`, `"205"`, `"233"`, and `"601"`, each mapped to `"DAP"`.
DAP is an explicit export Incoterm for 205 (`units.py:474-476`) and belongs to the shared export Incoterm set the existing 601 DK booking already books with, so the mapping is valid for all four; without the entries, `export_customs` raises `KeyError` for any customs-carrying freight case (`test_booking_export.py:58,68`).
Every freight case also passes an explicit `dhl_freight_sweden_payer_code` of `DAP` through `extra_options`, as the GB-NI case does, because freight products have no default payer code (`shipment/create.py:783-793`).
Raise `DEFAULT_MAX_BOOKINGS` from 10 to 30 at `sandbox_tests/dhl_freight_sweden/harness.py:40`; this is the self-limit relaxation.
Every guard stays: reserve-before-call, the transport guard refusing unreserved booking calls (`harness.py:261-280`), the forced sandbox host check, and the per-run env override for tighter budgets.

## Execution plan

The product and country env filters cannot isolate case 9 from the existing 112 NO Full-Service case, because they share product and country, so runs select cases with `unittest -k` patterns, which OR together when repeated, combined with segment, product, and country narrowing.
Three passes, each sourcing `.env` with the client key never printed:

1. booking-export for cases 2 through 10 with `DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=12`.
2. booking-approved with `DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS=401` and budget 1 for case 1.
3. only if cases 4 and 5 skipped as unoffered, case 11 with budget 1.

Rejected bookings are never retried.
The `-k` narrowing becomes documented behavior in the README sandbox-tests section, since it is the rerun-safe selection mechanism for same-product-same-country variants.

## Evidence flow

Each pass writes captures to the XDG state directory.
Afterwards `sandbox_tests/dhl_freight_sweden/evidence.py` gains a CATALOG entry per new booking binding the capture paths, the fixtures rebuild redacted and byte-reproducible into `tests/dhl_freight_sweden/fixtures/sandbox/`, and the offline contract tests in `tests/dhl_freight_sweden/test_sandbox_evidence.py` must pass.
The findings note gains bookings-table rows and whatever deviations DHL produces; the 205 forced case, if it runs and DHL rejects, adds a rejection row instead.
The README gains the new case descriptions, the budget-default change, and the `-k` note, and the findings note's Untested section shrinks accordingly.
The CLAUDE.md sandbox line is updated so it stops prescribing budget-1-only runs and describes matrix runs instead.

## Verification and commits

Work happens on branch `sandbox-gap-filling-matrix`.
Commits in order: Incoterm entries; new test cases; budget default with its documentation updates; then one commit per live pass bundling fixtures, catalog entries, findings-note rows, and README rows.
Offline gates for every commit: `.venv/bin/python -m unittest discover -s tests` green, `pyright` clean, and the evidence contract green once fixtures land.
The live passes are the integration verification themselves: each case asserts a truthy tracking number equal to the shipment identifier and a present label, or records DHL's rejection.

## Constraints every case honors

- PL lanes require explicit SENT information for any product (`shipment/create.py:826-915`); no case in this matrix books PL.
- HU and RO lanes require explicit transport declarations for 202, 205, 233, and 601 (`units.py:373-379`); no case in this matrix books those lanes for those products.
- GR lanes require party tax ids for 202 and 601 (`units.py:407-412`); no case books GR.
- Åland postcodes FI 22000-22999 refuse customs handling services before booking (`shipment/create.py:685-712`).
- Per-product postal exclusions apply (`units.py:931-999`, `units.py:1044-1072`), including the UA Crimea range for 202 and 205 and the GB `JE*`/`GY*` patterns for 202, 601, 109, and 112; DK, NO, and the SE domestic lane carry no exclusion for the chosen cases.
- GB `BT*` sits inside the EU VAT area (`units.py:197-199`), so the existing 202 GB-NI booking dropped customs; the NO cases in this matrix are outside the EU VAT area and carry customs.

## Out of scope

GB-mainland freight variants for 202, 233, and 601, further declaration-lane coverage on HU and RO for the freight products, and any new rejection cases beyond the conditional forced 205 booking.
