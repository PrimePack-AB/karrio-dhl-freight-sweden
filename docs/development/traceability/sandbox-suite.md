---
title: "Sandbox suite and evidence"
---

`sandbox_tests/` holds an opt-in suite that calls the DHL Freight SE sandbox; it sits outside `tests/`, so the default offline run never discovers it, and the wheel does not ship it.
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

The `lookups` segment books nothing: it checks PostalCodes routes (a valid SE code, the 118 home-delivery flag, and an unknown code), product matches for SE to SE and SE to PL, and the nearest service points for SE and PL, including the parcel capacity filter and `location_types`.
Its `test_product_matches_territory_*` cases record the products matched from SE to special territories under their own and their parent country codes (see [Special territories](../../concepts/destinations.md#special-territories)).
Its `test_product_matches_ch_*` and `test_product_matches_li_9490` cases record the products matched from SE 11143 to Zürich (CH 8001, with a 2 kg and a 20 kg piece), Geneva (CH 1201), Bern (CH 3011), Lugano (CH 6900), and Vaduz (LI 9490), and `test_postal_code_route_ch_8001` and `test_service_points_ch` record DHL's answers to a PostalCode route request and a nearest-service-points request for Zürich 8001.
On 2026-10-06 the CH lanes matched HDI, 202, 601, and 233 and none of 109, 112, and 107, LI 9490 matched 202 alone, the PostalCode route answered 16009, and the service points request found no point ([lookup-product-matches-se-ch-8001.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-8001.json), [lookup-product-matches-se-li-9490.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-li-9490.json), [lookup-postal-code-ch-8001-16009.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-ch-8001-16009.json), [lookup-service-points-ch-8001-none.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-ch-8001-none.json)).
The `booking-approved` segment books 102 and 401 within SE, 601 to DK, and 118 within SE behind the `enforce` address validation pre-flight, and prints each label.
The `booking-pudo` segment looks up the service points nearest the recipient and books the first complete candidate as the AccessPoint party, for 103 within SE and 109 from SE to PL with payer code 022 and SENT free.
The `booking-export` segment books 109 to a service point and 112 to the home from SE to PL, RO, HU, and NO, 109 to a ParcelShop in DK, and 112 to the home in FR and GB, declaring the PL lanes SENT free.
It also books to the special territories Åland (FI 22100), 109 with customs data and no customs handling service, which the sandbox accepted as 2906762592 ([booking-2906762592-109-se-fi-aland-customs.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762592-109-se-fi-aland-customs.json)), and Northern Ireland (GB BT1 1AA), 202 with payer code DAP and without customs data.
To Åland it checks without booking that the connector refuses 112 with customs handling full service or Standard, which DHL rejected with 24003 when these cases booked, and 109 without customs data, which DHL booked before the connector required customs data.
The freight lanes book 202, 205, and 233 to DK inside the EU VAT area and 202, 205, 233, and 601 to NO with customs handling full service, each with the explicit DAP payer code, and 112 and 109 book to NO with customs handling Standard and a made-up EORI number.
The 205 cases skip unless product matches offer 205, which they did not in the 2026-10-06 run ([lookup-product-matches-se-dk-1620.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-dk-1620.json), [lookup-product-matches-se-no-0154.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-no-0154.json)); the NO case books even so, like the 112 GB case, and DHL answered 22020 "ChargeableWeight is lower than product min 2500.0" (2026-10-06: [rejection-22020-205-se-no.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22020-205-se-no.json)).
The 112 GB case books even when product matches do not offer 112, to record DHL's answer to the booking.
The 601 CH case books one 2 kg 30 × 20 × 15 cm piece to Zürich 8001 with payer code DAP, customs handling full service, and a `CommercialInvoice` whose amount comes from the `customs.duty.declared_value` the case sets; the sandbox accepted it as 2906762477 with routing code 2LCH8001+00000001 and printed one PDF label (2026-10-06: [booking-2906762477-601-se-ch.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762477-601-se-ch.json)).
Before each booking it checks for free that product matches offer the product for the lane and, for 109, that a nearby service point accepts the product, and it skips the lane otherwise.
The full-service NO and GB bookings carry one commodity, an invoice number, and the `dhl_freight_sweden_customs_handling_full_service` option, the customs service that needs no registration identifier; the Incoterm DAP gives payer code 022 on 109, avoiding the joint declaration that 023 requires, and DDP gives 023 on 112.
The `booking-declarations` segment books 601 from SE with payer code DAP and a transport declaration that is not free: to HU with a placeholder `dhl_freight_sweden_ekaer_number`, which sends `EKAER_FREE` `"false"` and `EKAER_NUMBER`, and to RO with `dhl_freight_sweden_uit_free` `false` and no number, which sends `UIT_FREE` `"false"` alone.
Its `test_book_601_hu_default_ekaer_free` and `test_book_601_ro_default_uit_free` cases book the same lanes with no EKAER or UIT option and assert before booking that the connector's default for a shipment below 500 kg serializes as `EKAER_FREE` or `UIT_FREE` `"true"` alone; the sandbox accepted them as 2906769555 with routing code 2LHU1052+00000000 and 2906769563 with routing code 2LRO030031+00000000 (2026-10-08: [booking-2906769555-601-se-hu-default-ekaer-free.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769555-601-se-hu-default-ekaer-free.json), [booking-2906769563-601-se-ro-default-uit-free.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769563-601-se-ro-default-uit-free.json)).
It checks product matches for the lane first and skips when 601 is not offered.
The `rejections` segment sends payloads that DHL rejects and asserts the DHL error code, so the connector's rules stay anchored to live behaviour: 109 to PL without its SENT entries (22001), which the connector never sends because it adds `SENT_FREE` `"true"` by default, 112 to PL with an AccessPoint party (22015), 112 to PL with payer code 1 (22020), and 103 within SE with an AccessPoint party carrying only its id (22001 and 22006).
Each case builds a valid request through the connector and `harness.mutated_request` changes the serialized TransportInstruction just before the call, so connector validation stays intact.
Rejection attempts count against the booking budget, and a response carrying a shipment id fails the test and reports the id as a finding.
The sandbox enforced the capacity filter for PL but returned the same SE points for a 2.5 kg and a 500 kg parcel (2026-10-05: [lookup-service-points-pl-capacity-too-large.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-pl-capacity-too-large.json), [lookup-service-points-se-capacity-not-applied.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-se-capacity-not-applied.json)), so the capacity check runs against PL.

Each booking attempt is counted before the TransportInstruction call, and once the budget is spent the remaining booking tests skip.
To book a single product or lane, narrow the selectors, for example `DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS=booking-approved DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS=102 DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=1`.
The selectors cannot separate two cases that share a product and country, so add `unittest -k <method name>` per case (repeatable, matched as a substring of the test id) to rerun exactly one case, for example `-k test_book_112_no_customs_standard`.
Every live call writes its request and response as JSON to the capture directory, with the `client-key` header and the client key redacted.
The account number stays in the captures, because DHL API Farm support traces sandbox bookings by it.
Sandbox bookings cannot be cancelled through the API, so `bookings.jsonl` in the capture directory records the product, shipment id, and timestamp of every attempt.

Still unbooked: a 205 booking at or above its 2500.0 chargeable-weight minimum, the customer's own declaration, the joint declaration including 109 with payer code 023, VOEC, and destinations outside the EU VAT area other than NO and CH.

The sandbox findings so far, with every booking, rejection, and deviation from the product manual, are in [docs/notes/sandbox/sandbox-findings.md](../../notes/sandbox/sandbox-findings.md).
Each finding is backed by an evidence file in [`tests/dhl_freight_sweden/fixtures/sandbox/`](../../../tests/dhl_freight_sweden/fixtures/sandbox/) holding the redacted request and response bodies, the source capture path, and the capture's sha256, and `tests/dhl_freight_sweden/test_sandbox_evidence.py` checks those files offline.
A new sandbox finding gets its own evidence file there before the README or the findings note cites it.
`sandbox_tests/dhl_freight_sweden/evidence.py` builds those files from the captures: its `CATALOG` names each evidence file and the capture files behind it, relative to the state directory.
Rebuilding over the same captures reproduces the committed files byte for byte, so `git diff` after a rebuild shows only new or changed findings:

```bash
.venv/bin/python -m sandbox_tests.dhl_freight_sweden.evidence [--state-root DIR] [--out DIR] [NAME ...]
```

`--state-root` defaults to `$XDG_STATE_HOME` (`~/.local/state` when unset), `--out` to `tests/dhl_freight_sweden/fixtures/sandbox/`, and without names it builds every catalog entry.
