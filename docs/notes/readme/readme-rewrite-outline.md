---
title: "README rewrite outline: consumer guide, phase 1"
created: 2026-10-06
---

## Reader and scope

The reader is a developer or operator who is integrating Karrio for a shipper and arrives cold, with no knowledge of this repository's history, the sandbox campaign, or the product manual.
They want to know what the plugin does and does not do, how to install and configure it, and how to book the shipments their shipper actually sends.
The plugin is generic, but the worked journey follows a Swedish B2C e-commerce shipper that sends single parcels under DAP to three kinds of destination.
The first is domestic, both home delivery and service-point (PUDO) delivery.
The second is EU exports, where no customs data is sent.
The third is non-EU exports, with NO and CH as the examples.

The README is also the PyPI long description (`readme = "README.md"` in `pyproject.toml`), so it must read well with relative links that do not resolve there.
This phase produces only this outline, and README.md stays unchanged until the outline is approved.

## Facts verified for the guide

Each fact below was checked against code, fixtures, or the local v5.26 text copy on 2026-10-06, and the rewrite carries it with the citation shown.

The connector reads `customs.commercial_invoice`, a field of the Karrio `Customs` model rather than a shipping option.
When the field is true the connector sends a `CommercialInvoice` document, and otherwise it sends a `ProformaInvoice` (`_customs_information` in `shipment/create.py`).
A booking is refused with `CommercialInvoiceRequiredError` when four conditions hold: the content is sale-like (an unset content type or anything other than documents, gift, return_merchandise, or sample, per `NOT_SALE_LIKE_CONTENT` in `units.py`), the lane leaves the EU VAT area, customs data is present, and the field is false or unset (`_check_commercial_invoice`).
The refusal is the connector's own rule, because DHL accepted a proforma on 109 to NO ([booking-2906761305-109-se-no.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761305-109-se-no.json)).
The check runs only when customs data is present, meaning commodities, an invoice number, or an invoice date (`has_customs_data`), so a non-EU booking that carries no customs at all is not refused and goes out without customs information.
That gap becomes a connector refusal on branch `require-customs-outside-eu` (decision 3), and the guide documents the refused behaviour once that branch lands on main.

The connector sends customs data electronically inside the booking and nothing else.
It uploads no document and sends no email, and the Print call returns only the label (`_extract_details` takes the first report).
For each product the guide covers, the manual says that customs documents and invoices must be sent by email to dhlfreight.int.se@dhl.com: 112 at §5.3 p18, 109 at §5.14 p62, 202 at §5.4 p22, and 601 at §5.19 p81.
For 109 the manual also asks for two copies of the customs documents on the outside of the package (§5.14 p62).
Full service says a commercial invoice must be sent to DHL (§6.5 p92), and the customs overview of §7.6 p163 repeats that the invoice is still sent to DHL for both handling services.
DHL has not said whether these steps still apply to API bookings that carry full customs data, so the guide states them as the manual's requirement and makes no claim about DHL's practice.

The invoice amount is `customs.duty.declared_value` when that is set.
Otherwise it is the sum of the commodity line values, each value times quantity, and only when every line carries a value; when any line lacks one, no amount is sent (`_invoice_amount_from_lines`).
The connector also requires an invoice number, taking `customs.invoice` or else the shipment reference (`CustomsInvoiceNumberError`).
It rejects commodity currencies that conflict with the declaration currency (`DeclarationCurrencyError`).
The procedure code defaults to `1042` and can be changed with `dhl_freight_sweden_customs_procedure_code`.

The connector sends no customs service unless the shipper selects one; each service carries a DHL fee, as the `ShippingOption` comment in `units.py` notes.
The guide lists the four services neutrally and recommends none (decision 2), stating for each its prerequisite, its manual citation, and what the sandbox booked.
Full service needs no registration identifier (§6.5 p92); the sandbox booked it to NO with 109, 112, 202, 233, and 601 ([booking-2906761305-109-se-no.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761305-109-se-no.json), [booking-2906761313-112-se-no.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761313-112-se-no.json), [booking-2906762139-202-se-no.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762139-202-se-no.json), [booking-2906762154-233-se-no.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762154-233-se-no.json), [booking-2906762162-601-se-no.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762162-601-se-no.json)) and to CH with 601 ([booking-2906762477-601-se-ch.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762477-601-se-ch.json)).
Standard is limited to NO and Åland (FI 22) by the manual (§6.6 p94) and needs `customs.options.eori_number` (`CustomsServiceIdentifierError`); the sandbox booked it to NO with 109 and 112 ([booking-2906762105-109-se-no-standard-customs.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762105-109-se-no-standard-customs.json), [booking-2906762113-112-se-no-standard-customs.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762113-112-se-no-standard-customs.json)).
Own declaration needs an MRN in `dhl_freight_sweden_customs_own_declaration_id` (§6.7 p96).
Joint declaration needs an SFID in `dhl_freight_sweden_customs_joint_declaration_id`, is NO only under a separate agreement (§6.8 p98), and is the only basis for payer 023 on 109.
Own declaration, joint declaration, and VOEC (`customs.options.voec_number`) have never been booked in the sandbox, and the guide says so.
To or from Åland the connector refuses Standard and full service (`AlandCustomsServiceError`, DHL 24003: [rejection-24003-112-se-fi-aland.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland.json), [rejection-24003-112-se-fi-aland-standard.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland-standard.json)).

For destinations, the sandbox booked 109 and 112 to NO (the 109 booking cited above, and [booking-2906761313-112-se-no.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761313-112-se-no.json)).
For CH on account 116768, product matches did not offer 109, 112, or 107, and 601 was booked with DAP and full service as 2906762477 (fixture cited above, and [lookup-product-matches-se-ch-8001.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-8001.json)).
GB needs a separate agreement (§5.3 p18, §5.14 p63), and DHL rejected 112 to GB for account 116768 ([rejection-22005-112-se-gb.json](../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22005-112-se-gb.json)).
Territory codes are sent as their parent country (`with_parent_country`, `TERRITORY_PARENTS`).

The nordic_conventions package (`karrio.advisor_nordic_conventions`) is an optional advisory plugin that only adds warnings.
Its advisories need the unmerged karrio fork branch `feat-shipment-advisors`, as its own README states, and its known gaps in Åland advice and territory codes are deferred.

Finally, there is no tracking API and no cancel endpoint.
`meta.carrier_tracking_link` is a public DHL web URL built from the shipment id (`Settings.tracking_url` in `utils.py`), not a tracking capability.
Rates come from a static rate sheet whose prices are placeholders at 0.0.

## Proposed section tree

The tree keeps headings to at most three levels, and each line gives the section's purpose in journey order.

1. `# karrio.dhl_freight_sweden`: one paragraph on what the plugin is, which DHL API it targets, and who it is for.
   1. `## What it does and does not do`: a capability table (book with label, static rating, product matches, service points, postal-code validation) followed by explicit limits (no tracking API, only a web link; no cancel; no document upload or email; rates are placeholders; SE shippers only through the unified API).
2. `## Install and register`: Python 3.11+, the pip install line, entry-point registration, and how to confirm the carrier loaded through `karrio.gateway` and the server's `/v1/references`, including the restart-after-upgrade note.
3. `## Connect`: the Settings fields (`client_key`, `account_number`, `test_mode`) and one connection-config table that covers all six configs, adding `shipping_options` and `shipping_services`, which are undocumented today.
   1. `### Sandbox and production hosts`: the two hosts, `server_url`, and the warning that sandbox bookings cannot be cancelled.
4. `## Your first domestic shipment`: the 102 within SE request quoted from `examples/domestic_parcel.py`, the one-line `karrio.Shipment.create(...).from_(gateway).parse()` call that books it, with the response fields explained (tracking number = transport instruction id, `docs.label`, `meta.carrier_tracking_link`).
   1. `### Labels`: the format (PDF default, how the tag is detected), `label_page_type`, the phone-number formatting rule (Appendix E §10.6 p197), and a statement that receiver phones are not printed on most labels, linking to `docs/concepts/labels.md` for evidence.
   2. `### Home delivery with address validation`: 118 and the `address_validation` modes off, warn, and enforce, with `karrio.Address.validate`, placed before PUDO so the connection table needs no forward link.
5. `## Service-point (PUDO) delivery`: the three-step flow, with the diagram kept.
   1. `### Find eligible products`: a minimal `find_product_matches` example, linking to `docs/guides/lookups.md` for the key tables.
   2. `### Choose a service point`: a minimal `find_service_points` example and the ranking policy (complete address, capacity, distance, sub type, no opening hours).
   3. `### Book to the point`: the 103 request quoted from `examples/service_point_parcel.py`, including its point-to-options mapping, followed by the fallback loop and the non-idempotency warning.
6. `## Choosing a product`: a product catalogue table giving the karrio service code, the carrier code, the name, domestic or international, home or service point, the default payer code, and the minimum piece dimensions with their manual citation (re-read 2026-10-06: 15 x 11 x 2 cm for 102 §5.2 p14, 112 §5.3 p17, 103 §5.12 p55, 104 §5.13 p59, and 118 §5.16 p68; 15 x 11 x 3 cm for 202 §5.4 p21, 233 §5.10 p45, and 601 §5.19 p80; 15 x 11 x 3.5 cm for 211 §5.7 p33, 401 §5.17 p71, and 402/502 §5.18 p75; 109 varies by destination §5.14 p62), so the reader can map 102, 103, 109, 112, 601, and the others.
   1. `### Payer codes and Incoterms`: the resolution order (option, then Incoterm, then default) and the Combiterm translation for 109 and 112, linking to the full payer table in `docs/concepts/booking-rules.md`.
7. `## Exporting`: the decision tree for a Swedish shipper.
   1. `### Inside the EU VAT area`: customs data and services are dropped with `customs_omitted_intra_eu`, so a shipper may send customs data maximally, plus the PL, HU, and RO transport declarations (SENT, EKAER, UIT) and GR tax ids as lane rules the reader must answer explicitly.
   2. `### Outside the EU VAT area`: what is sent, the commodity requirements, invoice number and currency rules, how the invoice amount is derived, and the CH 601 request quoted from `examples/export_to_switzerland.py`, which mirrors sandbox booking 2906762477 (DAP, full service, commercial invoice, declared value), presented as what was booked rather than as advice.
   3. `### Customs services`: a neutral four-row table (full service, Standard, own declaration, joint declaration) with prerequisites, manual citations, and the destinations each was booked to with fixtures or "never booked", the note that nothing is selected by default, and the Åland refusal.
   4. `### Commercial or proforma invoice`: `customs.commercial_invoice`, sale-like content, the connector-only refusal and its evidence, and the refusal of a non-EU export without customs data once `require-customs-outside-eu` lands.
   5. `### Sending the invoice copy to DHL`: the manual's email and outside-copy requirements, stated as the manual's requirement, with DHL's answer still pending and a reminder that the connector neither uploads nor emails.
   6. `### GB, NO, and CH`: the per-destination facts (GB agreement and rejection, NO booked, CH only 601 on account 116768), each stated once.
8. `## Special territories and excluded postal codes`: one place for parent-country mapping, the territories outside the EU VAT area, and product exclusions, as a single merged territory table, linking to `docs/concepts/destinations.md` for the full exclusion tables and normalisation rules.
9. `## Options reference`: every `ShippingOption` and customs option in one table with its type, the DHL field, the products it applies to, and the rule section it belongs to, including the undocumented notification, pre-advice, tail-lift, insurance, procedure code, EORI, VOEC, and the unified aliases (`email_notification`, `insurance`, `shipper_instructions`, `recipient_instructions`).
10. `## Errors reference`: one table of every connector error class (all 17 found by the audit) with its message stem, `details` key, and fix, followed by the DHL validation codes seen in the sandbox (22001, 22005, 22006, 22015, 22020, 22026, 24003, 16009, 16010).
11. `## Operational notes and troubleshooting`: no cancel and the customer-service route, the caching advice for lookups, the placeholder rates, the fact that product matches are authoritative over the rate sheet, the server restart, and the REST-only driver variant in brief, linking to `docs/guides/lookups.md`.
12. `## Optional: nordic_conventions advisories`: what the plugin adds, the plain statement that it needs the unmerged karrio fork branch `feat-shipment-advisors`, and its known gaps.
13. `## Further documentation`: links to the product manual (URL, version, sha), the `docs/concepts/` and `docs/guides/` pages, the development docs, and the sandbox findings and evidence, with a two-line pointer to the sandbox suite in `docs/development/`.

The current spine is improved in four ways.
Address validation now sits inside the domestic journey, which removes the forward link.
The product catalogue comes before exporting, because product choice decides customs and payer behaviour.
nordic_conventions gets its own optional section rather than a passing mention.
Development material leaves the README altogether.
Every code block of a full request is quoted from a tested script in `examples/`, so the README snippets cannot drift from the connector.

## Mapping from the current README

Line ranges refer to README.md at ae4e4c3 (705 lines).
New-section numbers refer to the tree above, and new files are listed in the next section.

| Lines | Current section | Destination |
|-------|-----------------|-------------|
| 1-6 | Title and summary | Kept in 1 and 1.1, rewritten; "URL-only tracking link" is reconciled with 1.1's limits |
| 8-10 | Requirements | Merged into 2 |
| 12-19 | Installation | Kept in 2; the `METADATA` sentence moves to `docs/development/architecture/plugin-layout.md` |
| 21-38 | Usage | Merged into 3 and 4; the "Mutli-carrier" line is fixed and moved to 13 |
| 40-49 | Connection settings | Kept in 3, with the 46 label-format evidence moving to `docs/concepts/labels.md` and the 48 forward link removed |
| 51-60 | Label printing behavior | Summary in 4.1; the full evidence paragraphs (53-57) move to `docs/concepts/labels.md` |
| 62-71 | Per-product requirements: minimum dimensions | Moved to the product catalogue in 6 (as a column or note), with every product's minimum and citation (decision 8) |
| 72 | 205 chargeable weight | Moved to `docs/concepts/products.md`, keeping its fixture |
| 73 | 401 doorstep access code | Kept in 9 (option row) and 6 (catalogue note) |
| 74, 80-81 | 112 to FR | Moved to `docs/concepts/products.md`; the exclusion is merged into the reference exclusion table |
| 75-79 | 112/109 to GB | Kept once in 7.6; the duplicate rejection sentence (76 vs 79) is deleted, and the detail moves to `docs/concepts/products.md` |
| 83-88 | Booking rules intro, manual citation | The manual version and sha move to 13 and to `docs/concepts/booking-rules.md`; the incomplete check list is replaced by 10 |
| 90-96 | Commercial invoice and invoice amount | Kept in 7.2 and 7.4 |
| 98-123 | Payer codes | Summary in 6.1; the full table moves to `docs/concepts/booking-rules.md` |
| 125-140 | Access points | Summary in 5.2 and 5.3; the table and the subtype evidence move to `docs/concepts/booking-rules.md` |
| 142-160 | SENT | Lane summary in 7.1 and option rows in 9; the rules and evidence move to `docs/concepts/booking-rules.md` |
| 162-188 | EKAER and UIT | Same treatment as SENT |
| 190-196 | GR VAT number/TIN | Summary in 7.1; detail moves to `docs/concepts/booking-rules.md` |
| 198-204 | QR code for 107 | Option row in 9; detail moves to `docs/concepts/booking-rules.md` |
| 206-229 | Customs and the EU VAT area | Rule in 7 and 8; the range table and normalisation move to `docs/concepts/destinations.md`; the nordic_conventions parity sentence moves to 12 and to the development docs |
| 231-256 | Special territories | Merged into 8 (one table); the evidence and booking paragraphs move to `docs/concepts/destinations.md` |
| 258-311 | Excluded postal codes | Summary in 8; both tables and the normalisation rules move to `docs/concepts/destinations.md` |
| 313-317 | Additional information pass-through | Kept in 9 |
| 319-323 | Discrepancies | Deleted from the README as a duplicate of the payer row (111) and of the findings note's "Payer codes for 109 and 112"; the catalogue fixture citation moves to the payer table in `docs/concepts/booking-rules.md` |
| 325-335 | Capabilities | Kept in 1.1 |
| 337-356 | PUDO intro and diagram | Kept in 5 |
| 358-405 | Step 1 | Short example in 5.1; the key tables (394-405) move to `docs/guides/lookups.md` |
| 407-462 | Step 2 | Example and ranking kept in 5.2; the output key table moves to `docs/guides/lookups.md` |
| 464-505 | Step 3 | Kept in 5.3 with undefined names fixed and the customs comment replaced by a link to 7 |
| 507-522 | Errors and fallback loop | The fallback is kept in 5.3, and the table is merged into 10 |
| 524-579 | REST-only variant | Moved to `docs/guides/lookups.md`, with a pointer in 11 |
| 581-612 | Address validation | Kept in 4.2; the server-restart lines (611-612) move to 2 |
| 614-618 | Operational notes | Kept in 11 |
| 620-642 | Development | Moved to `docs/development/index.md` and `docs/development/architecture/plugin-layout.md` |
| 644-692 | Sandbox tests | Moved to `docs/development/traceability/sandbox-suite.md`; the CH lookup results (667-668) and the 601 CH booking (676) are summarised in 7.6 with their fixtures |
| 693 | Still unbooked | Moved to the findings note's "Untested" section, which already covers it, so it is deleted as a duplicate |
| 695-705 | Evidence tooling | Moved to `docs/development/traceability/sandbox-suite.md`; 13 links to the findings note and the fixtures directory |

Every fixture link in the current README is carried into a destination above.
The rewrite is checked by diffing the set of `fixtures/sandbox/*.json` names linked from README.md plus `docs/concepts/` and `docs/guides/` against the set linked today, and every name must remain linked somewhere.

## Known defects to fix

The defects named in the brief, with locations:

1. The 112 to GB rejection appears twice, at 76 and 79, with the same fixture.
2. The payer discrepancy for 112 appears in the payer row at 111, in Discrepancies at 319-323, and again in the findings note.
3. Territory facts are repeated three times: in the EU VAT area table (213-224), in the special territories table and paragraph (236-256), and in the excluded-patterns table and paragraphs (293-305).
4. "URL-only tracking link" at 6 sits beside "no tracking ... capability" at 335, and the plugin comment calls it "tracking via a public URL", so all three should say that the link is a web page and no tracking API exists.
5. The forward link to address validation is at 48.
6. The up-front check list at 85 omits the Åland customs services, the commercial invoice, the customs-service identifiers, the invoice number, currency conflicts, the additional-information codes, and the service-point details.
   The errors table at 509-520 likewise omits `DeclarationCurrencyError`, `CustomsInvoiceNumberError`, `CustomsServiceIdentifierError`, `AlandCustomsServiceError`, `ExcludedDestinationError`, `QrCodeEligibilityError`, `AdditionalInformationError`, `PostalCodeNotServableError`, and `ProductMatchPartiesError`.
7. The `shipping_options` and `shipping_services` connection configs are undocumented (`ConnectionConfig` in `units.py`).
8. "Mutli-carrier" at 38 is a typo.

The audit found these as well:

9. Options with no documentation at all: `dhl_freight_sweden_notification`, `dhl_freight_sweden_pre_advice`, `dhl_freight_sweden_tail_lift_unloading`, `dhl_freight_sweden_insurance`, `dhl_freight_sweden_customs_procedure_code` (default 1042), the four customs-service options and their identifiers, and `customs.options.eori_number` and `voec_number`.
10. Customs services are not explained anywhere in the README beyond their names inside the sandbox-suite prose (673, 678).
11. The invoice-copy email and outside-copy requirements are absent, as is the statement that the connector sends no documents.
12. No product catalogue maps karrio service codes to carrier codes; only `dhl_freight_sweden_parcel_connect_b2c` and `dhl_freight_sweden_hemleverans_paket_b2c` appear.
13. The Step 3 example uses the undefined names `accepted_points`, `SHIPPER_ADDRESS`, `RECIPIENT_ADDRESS`, and `gateway` (the gateway is called `dhl_freight_sweden` in Usage), and the README has no complete non-PUDO booking example.
14. The minimum-dimension table (66-69) lists 102 and 601 with no citation, while the findings note cites minimums for 102 (§5.2 p14) and 112 (§5.3 p17), and a re-read of the manual shows both are correct but incomplete, since every product section states its own minimum (see section 6 of the tree).
15. The README describes PostalCode error 16012 as "not supported" at 597, which the findings note marks as pending verification because no capture shows it.
16. The test command at 626 (`discover -v -f tests`) differs from CLAUDE.md (`discover -s tests`).
17. 335 says neither tracking nor cancel is "advertised", but `shipment/cancel.py` exists as a stub; the developer docs should explain it, and the consumer docs need only "no cancel".
18. The Step 3 code comment (490-494) explains customs without mentioning the commercial invoice rule, so it is stale after c8fff36.
19. Notes and booking rules cite manual pages inside long sentences, so the rewrite should move citations into table columns or trailing parentheses for scanning.
20. `docs/notes/README.md` is missing, although the documentation conventions require it as an index.

## Proposed new files

All new files use frontmatter titles and `##` content headings, matching the existing notes.

| Path | Purpose |
|------|---------|
| `docs/concepts/booking-rules.md` | Payer codes, access points, SENT, EKAER, UIT, GR tax ids, QR code, and additional information, with every manual citation and fixture |
| `docs/concepts/destinations.md` | EU VAT area ranges, postal-code normalisation, special territories with evidence, and both excluded-postal-code tables |
| `docs/concepts/products.md` | Per-product facts: minimum dimensions, 205 chargeable weight, 112 FR and GB, 109 GB, and 401 doorstep delivery |
| `docs/guides/lookups.md` | Product-matches and service-points inputs and outputs, and the REST-only driver variant |
| `docs/concepts/labels.md` | Label format detection, page types, and the phone-number and customer-information evidence |
| `docs/development/index.md` | Development setup, the editable SDK checkout, the test and pyright commands, and links to the subpages |
| `docs/development/architecture/plugin-layout.md` | `METADATA` and the entry point, the namespace and `__init__.pyi` arrangement, and the cancel stub |
| `docs/development/traceability/sandbox-suite.md` | The opt-in sandbox suite, its variables and segments, and the evidence tooling and its rules |
| `docs/notes/README.md` | Index of working notes with dates, as the conventions require |
| `examples/domestic_parcel.py` | 102 within SE, built offline through the mapper and printed as the TransportInstruction body |
| `examples/service_point_parcel.py` | 103 to service point SE-982000, mapping a normalised service point to the booking options |
| `examples/export_to_switzerland.py` | 601 to CH 8001 with DAP, full service, and a commercial invoice, mirroring booking 2906762477 |
| `examples/offline.py` | The shared offline gateway (placeholder credentials, test mode) and the request printer |
| `tests/dhl_freight_sweden/test_examples.py` | Runs every example with all network calls patched to fail and asserts the request fields the README describes |

The conventions in preferences-documentation reserve `docs/reference/` for API reference generated from docstrings (its Code section), so the hand-written pages go into two directories its Diátaxis tree sanctions.
Rule and destination pages, which explain each rule with its manual citation and evidence, go into `docs/concepts/`.
The lookups page, a task-oriented how-to for drivers that call the lookups or the REST API, goes into `docs/guides/`.

## Decisions

The user answered the open questions on 2026-10-06, and the coordinator supplied defaults for the rest, which the user may override.

1. The README holds the guide at about 350-450 lines and is also the PyPI page; reference tables and developer and evidence documentation move to `docs/`.
2. Customs services are listed neutrally with facts and fixtures, and the guide recommends none.
3. A non-EU export without customs data becomes a connector refusal on branch `require-customs-outside-eu`, and the guide documents the refusal once it lands.
4. Runnable examples go under `examples/` (domestic, PUDO, and a CH export), built through the mapper offline, kept honest by an offline test in `tests/`, and quoted in the README.
5. The sandbox-suite documentation moves to `docs/development/`, with a two-line pointer in the README (default).
6. Reference tables are hand-written for now (default).
7. The CH guidance says "on account 116768" (default).
8. The minimum-dimension table follows a re-read of the manual, with each product cited by §/p, as listed under section 6 of the tree (default).
9. The nordic_conventions section ships and states its fork-branch prerequisite plainly (default).
10. Hand-written pages use `docs/concepts/` and `docs/guides/` rather than `docs/reference/`, as explained under the new files (default).

The README's relative links to `docs/`, `examples/`, and evidence files will not resolve on PyPI, and fixing them is deferred until the package is published (user decision, 2026-10-06).

The README rewrite waits until the branches `label-type-validation` and `require-customs-outside-eu` land on main, and this branch is then rebased onto main.
