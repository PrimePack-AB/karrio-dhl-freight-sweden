---
title: "DHL Freight SE sandbox findings, 2026-10-05"
---

## Environment and method

All calls went to the DHL Freight (Sweden) API Farm test host `test-api.freight-logistics.dhl.com` on 2026-10-05, and all times below are UTC.
Every booking used customer number 116768 as the Consignor party id, which DHL API Farm support needs to trace these bookings.
The rules are compared against the DHL Freight Sweden product manual version 5.23, valid from 2025-04-14 (sha256 `c16b0a0dcb1a1cfe8c7ca767ff11e2192d8d86fd233ed6ef77693981fc5d3295`), and page numbers below refer to that version.
The manual uses the deprecated names DHL EUROCONNECT, DHL EUROLINE, and DHL EURAPID for the products now named DHL ROAD FREIGHT STANDARD (202), DHL ROAD FREIGHT DIRECT (205), and DHL ROAD FREIGHT PRIORITY (233); the Product API already returns the current names for 202 and 233 ([lookup-product-matches-se-pl.json][l-pm-pl]).

The calls came from three sources.
A read-only probe script called the Product, AdditionalService, ServicePointLocator, and PostalCode APIs at 14:14.
Two scripts booked directly against TransportInstruction (14:31) and through the connector (14:48).
The opt-in sandbox suite in `sandbox_tests/` ran its lookup and booking segments between 16:20 and 16:31 its rejection and declaration segments at 16:53, and its 109 DK ParcelShop case at 17:14, and a manual capacity probe with the connector ran at 16:21.

Each finding has one evidence file in `tests/dhl_freight_sweden/fixtures/sandbox/`, named by kind: `booking-<id>-...`, `rejection-<error code>-...`, `lookup-...`, or `label-<id>-...`.
An evidence file holds the request and response bodies of the calls behind the finding, with metadata naming the endpoint, product, route, booking id or error code, and the capturing script or suite test.
Each call records the path of its original capture relative to `$XDG_STATE_HOME` (`~/.local/state`) and the sha256 of that capture file, so the original can be checked against the committed copy.
The committed copies drop the `client-key` header and the response headers, and replace label base64 with a length marker.
The original captures masked the customer number in the Consignor party id; the evidence files restore it and record the restored placeholder under `account_number_restored`.
Product API responses are reduced to the fields a finding uses, and such calls carry a `response_reduced` note.
A `label` file holds a Print API call with the label's page size and its `pdftotext -layout` text, citing the PDF and text files it was taken from.
The two `label` files come from an earlier probe on 2026-09-10 that sent 1234567 as the Consignor party id; they back the README's consignee phone statement and are not part of the findings below.
`tests/dhl_freight_sweden/test_sandbox_evidence.py` checks the files offline for these redactions and parses every response body with the connector's parsers.
`sandbox_tests/dhl_freight_sweden/evidence.py` builds the files from the captures, and rebuilding over the same captures reproduces them byte for byte.

## Bookings

All 18 bookings returned status `Succes`, a transport instruction id, a piece id, and a routing code, and every shipper was Stockholm SE 11143.
Every booking had one piece of 1 kg, and only those marked in the table carried customs data.
None was cancelled, because the API Farm has no cancellation operation.

| Id | Time | Product | Route | Payer code | Customs | Service point | Routing code | Evidence |
|----|------|---------|-------|------------|---------|---------------|--------------|----------|
| 2906761073 | 14:31:56 (file time) | 109 | SE → PL 30-079 | 022 | none | 8005-PL-4507446 ParcelShop | 2LPL30079+70530000 | [booking-2906761073][b-073] |
| 2906761081 | 14:31:56 (file time) | 112 | SE → PL 30-079 | 023 | none | none | 2LPL30079+74000000 | [booking-2906761081][b-081] |
| 2906761123 | 14:48:37 | 109 | SE → PL 30-079 | 022 | none | 8005-PL-4507446 ParcelShop | 2LPL30079+70530000 | [booking-2906761123][b-123] |
| 2906761131 | 14:48:39 | 112 | SE → PL 30-079 | 023 | none | none | 2LPL30079+74000000 | [booking-2906761131][b-131] |
| 2906761149 | 14:48:40 (file time) | 112 | SE → PL 30-079 | 022 | none | none | 2LPL30079+74000000 | [booking-2906761149][b-149] |
| 2906761222 | 16:21:37 | 102 | SE → SE 11151 | 1 | none | none | 2LSE11151+02000000 | [booking-2906761222][b-222] |
| 2906761230 | 16:21:45 | 103 | SE → SE 11151 | 1 | none | SE-982000 ParcelShop | 2LSE11157+02000000 | [booking-2906761230][b-230] |
| 2906761248 | 16:29:32 | 601 | SE → DK 1620 | DAP | none | none | 2LDK1620+00000000 | [booking-2906761248][b-248] |
| 2906761255 | 16:29:38 | 118 | SE → SE 11151 | 1 | none | none | 2LSE11151+02000000 | [booking-2906761255][b-255] |
| 2906761263 | 16:29:49 | 109 | SE → RO 030031 | 022 | none | 8023-231652 ParcelShop | 2LRO040011+70530000 | [booking-2906761263][b-263] |
| 2906761271 | 16:29:53 | 112 | SE → RO 030031 | 023 | none | none | 2LRO030031+74000000 | [booking-2906761271][b-271] |
| 2906761289 | 16:30:05 | 109 | SE → HU 1052 | 022 | none | 8013-118530 ParcelStation | 2LHU1826+70540000 | [booking-2906761289][b-289] |
| 2906761297 | 16:30:08 | 112 | SE → HU 1052 | 023 | none | none | 2LHU1052+74000000 | [booking-2906761297][b-297] |
| 2906761305 | 16:30:17 | 109 | SE → NO 0154 | 022 | full service, ProformaInvoice | 8009-129635 ParcelShop | 2LNO0186+70530001 | [booking-2906761305][b-305] |
| 2906761313 | 16:30:20 | 112 | SE → NO 0154 | 023 | full service, ProformaInvoice | none | 2LNO0154+000000 | [booking-2906761313][b-313] |
| 2906761339 | 16:53:40 | 601 | SE → HU 1052 | DAP | none | none | 2LHU1052+00000000 | [booking-2906761339][b-339] |
| 2906761347 | 16:53:52 | 601 | SE → RO 030031 | DAP | none | none | 2LRO030031+00000000 | [booking-2906761347][b-347] |
| 2906761354 | 17:14:34 | 109 | SE → DK 1620 | 022 | none | 8009-115191 ParcelShop | 2LDK1620+70530000 | [booking-2906761354][b-354] |

The time is the response `Date` header, except for the three direct bookings whose captures carry no header, where it is the capture file's modification time.
The 109 and 112 bookings to PL declared `SENT_FREE` `"true"`; 2906761339 sent `EKAER_FREE` `"false"` with the placeholder `EKAER_NUMBER` `E0000SANDBOX0001`, and 2906761347 sent `UIT_FREE` `"false"` without a number, and DHL echoed these entries in the responses.
No other booking sent additional information entries.
Every booking except 2906761073, 2906761081, and 2906761149 was followed by a Print API call that returned a PDF label (`label_<id>.pdf`).
Booking 2906761255 (118) was preceded by a PostalCode route lookup for SE 11151 that returned `homeDeliveryParcel` `true`, the connector's `enforce` pre-flight ([booking-2906761255][b-255]).
The suite's lookup segment returned the same flags for SE 11151, `bookable` `true` and `homeDeliveryParcel` `true` ([lookup-postal-code-se-11151-route.json][l-pc-11151]), the route flag the manual ties to 118 (p243).
The 103 and 109 bookings to RO, HU, NO, and DK were preceded by the service point lookup the point was taken from, and those lookups are included in the evidence files.

## Rejections

The suite's rejection segment built a valid request through the connector and changed the serialized payload just before sending, and DHL answered each with HTTP 400 and one validation error.
No booking was created by any of them.

| Error code | Field | Message | Payload | Evidence |
|------------|-------|---------|---------|----------|
| 22001 | `AdditionalInformation` | SENT_REF and SENT_CARKEY are mandatory unless SENT_FREE is true. | 109 SE → PL 30-079, payer code 022, ParcelShop 8005-PL-4504339, no SENT entries | [rejection-22001][r-22001] |
| 22015 | `Parties[2]` | AccessPoint Party is not allowed for this product | 112 SE → PL 30-079, payer code 023, `SENT_FREE` `"true"`, added AccessPoint ParcelShop 8005-PL-4504339 | [rejection-22015][r-22015] |
| 22020 | `PayerCode.Code` | Payercode 1 is not valid for product | 112 SE → PL 30-079, payer code 1, `SENT_FREE` `"true"` | [rejection-22020][r-22020] |

The PostalCode API rejected the unknown SE postal code 99999 with HTTP 400 and the PascalCase ErrorResult `{"ErrorCode": 16010, "Status": 400, "UserMessage": "Post code '99999' not found."}` ([lookup-postal-code-se-99999-16010.json][l-pc-99999]).
Its route lookup for PL 30-079 answered HTTP 400 with 16009 "Country code 'PL' not supported." ([lookup-postal-code-pl-route-16009.json][l-pc-pl]), which matches the manual listing the route service only for domestic products (p236).

## Deviations from manual v5.23

### Payer codes for 109 and 112

The manual lists only payer code 023 for 112 (§5.3 p15), but the sandbox accepted 112 to PL with payer code 022 ([booking-2906761149][b-149]) as well as 023 ([booking-2906761131][b-131]).
It rejected payer code 1 for 112 with 22020 ([rejection-22020][r-22020]).
The Product API catalog lists CPT, 022, DPU, DAP, 023, CIP, and DDP for both 109 and 112, with `customs` `true` only for DDP ([lookup-products-109-112-payer-codes.json][l-products]), while the manual lists only the Combiterms 022 and 023 for 109 (§5.16 p67) and 023 for 112 (p15).
No booking used an Incoterm as the payer code for 109 or 112.

### SENT for PL

The manual marks the SENT reference and carrier key optional in the related-fields tables of 202 (p19) and 601 (p87) and does not mention SENT for 109 (pp65-69) or 112 (pp13-16), and it does not document `SENT_FREE`.
The sandbox rejected 109 to PL without SENT entries with 22001 ([rejection-22001][r-22001]) and accepted 109 and 112 to PL with `SENT_FREE` `"true"` at shipment level ([booking-2906761123][b-123], [booking-2906761131][b-131]).
The vendored transport-instruction spec 2.10.0 (`vendor/se-api-farm/transport-instruction-2.10.0.json`) defines an `AdditionalInformation` schema that no other schema references.
No booking sent `SENT_REF` and `SENT_CARKEY`, so the sandbox's acceptance of real SENT identifiers is untested.

### EKAER and UIT for HU and RO

The manual lists EKAER (HU) and UIT (RO) entries in the related-fields tables of 202 (p19), 205 (p38), 233 (p46), SPI (p51), PPI (p56), and 601 (p87), and not for 109 or 112.
The sandbox accepted 109 and 112 to RO and HU without these entries ([booking-2906761263][b-263], [booking-2906761271][b-271], [booking-2906761289][b-289], [booking-2906761297][b-297]), which matches the manual.
For 601 it accepted `EKAER_FREE` `"false"` with a placeholder EKAER number to HU ([booking-2906761339][b-339]) and `UIT_FREE` `"false"` without a UIT number to RO ([booking-2906761347][b-347]); the latter matches the v5.23 release note that the UIT code is not mandatory even when a shipment is not UIT free (p7).
The EKAER number in that booking, `E0000SANDBOX0001`, is made up, and the sandbox accepted it.

### Service point capacity filter

The ServicePointLocator applied the piece capacity filter for PL but not for SE.
For Stockholm a 2.5 kg piece of 40 × 30 × 15 cm and a 500 kg piece of 300 × 200 × 200 cm returned the same ten service points in the same order ([lookup-service-points-se-capacity-not-applied.json][l-sp-se]).
For Warszawa the 2.5 kg piece returned points, while the 500 kg piece was answered with HTTP 400 "The dimensions are too large for servicepoint", and with `locationTypes` `["locker"]` "The dimensions are too large for locationtype locker" ([lookup-service-points-pl-capacity-too-large.json][l-sp-pl]).

### Service point ids and sub types

For 103 the manual says only the four-digit part nnnn of an id like SE-nnnn00 is to be used (p239), but the sandbox accepted the full id SE-982000 ([booking-2906761230][b-230]).
For SE the lookup's `id` and `servicePointId` are equal (SE-982000), while elsewhere they differ, for example `id` 101 and `servicePointId` 8005-PL-4516440 in Warszawa ([lookup-service-points-pl-capacity-too-large.json][l-sp-pl]) and `id` 231652 and `servicePointId` 8023-231652 in București ([booking-2906761263][b-263]).
Appendix M states that the AccessPoint sub type carries the location type `servicepoint`, `locker`, or `postoffice` (p237, p240), while the vendored spec enumerates `ParcelShop` and `ParcelStation`.
The sandbox accepted `ParcelShop` for PL, RO, NO, and DK ([booking-2906761123][b-123], [booking-2906761263][b-263], [booking-2906761305][b-305], [booking-2906761354][b-354]) and `ParcelStation` for a HU locker ([booking-2906761289][b-289]).
Their routing codes carry 53 and 54 respectively (for example 2LPL30079+70530000 and 2LHU1826+70540000), which matches the routing code column of the table on p240.

### Service types and lookup size for service point products

The manual says only shops and stations with service type `parcel:pick-up` can be selected for 109 (p240), but the sandbox accepted 109 to the HU locker 8013-118530, whose lookup entry lists only `parcel:pick-up-unregistered` ([booking-2906761289][b-289]).
For 103 the manual says to always search the ten closest service points (p61), while the suite's 103 booking searched five ([booking-2906761230][b-230]); the lookup segment's capacity check searched ten ([lookup-service-points-se-capacity-not-applied.json][l-sp-se]).

### Customs to NO

The manual's Customs handling - Full service section says a commercial invoice must be sent to DHL and lists routing barcode 001 on the label (p97), and for 109 it asks for two copies of the customs documents on the outside of the package (p66).
The sandbox accepted 109 and 112 to NO with `customsHandlingFullService`, one commodity, and a `ProformaInvoice` document without an invoice amount or EORI ([booking-2906761305][b-305], [booking-2906761313][b-313]).
No documents were e-mailed to DHL for these bookings, and the evidence does not show whether DHL would act on a missing commercial invoice.
109 to NO returned routing code 2LNO0186+70530001, ending in 001, while 112 to NO returned 2LNO0154+000000 without it.

### Routing code reference and product codes

For 112 (p14) and 109 (p66) the manual asks for the label's routing code to be sent as a reference in the IFTMIN shipment instruction.
The API bookings sent no routing code, and every booking response returned `routingCode` (for example [booking-2906761131][b-131] and [booking-2906761123][b-123]).
Product matches for SE to PL returned both 601 and HDI ([lookup-product-matches-se-pl.json][l-pm-pl]), and the manual names HDI as the invoice-file code for 601 (p86).
Product matches for SE 11143 to SE 41101 returned 502, 118, 104, 102, 402, 211, 401, and 103 ([lookup-product-matches-se-se.json][l-pm-se]).

## Untested

No booking used the freight products 202, 205, 209, 210, 211, 212, 232, 233, SPI, or PPI, or the parcel and home delivery products 104, 107, 401, 402, and 502.
601 was booked only to DK, HU, and RO; 601 to HU or RO without EKAER or UIT entries, with a free flag `"true"`, or with a UIT number, and 601 to PL, are untested.
109 with home addressing and no AccessPoint party is untested.
Customs was tested only as Customs handling - Full service to NO; Customs handling - Standard, the customer's own declaration, the joint declaration (including 109 with payer code 023), VOEC, and other destinations outside the EU VAT area are untested.
No additional service other than `customsHandlingFullService` was sent, payer codes 3 and 4 with a freight payer party were not used, and 601 used only DAP.
Every booking had a single piece of 1 kg and 30 × 20 × 10 cm, so multi-piece shipments and bookings below the minimum piece dimensions the manual states for 102 (p10) and 112 (p13) are untested.
The Print API was called only for labels, and the PickupRequest, TimeTable, PriceQuote, and HomeDeliveryLocator APIs were not called.

[b-073]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761073-109-se-pl.json
[b-081]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761081-112-se-pl.json
[b-123]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761123-109-se-pl.json
[b-131]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761131-112-se-pl.json
[b-149]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761149-112-se-pl-payer-022.json
[b-222]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761222-102-se-se.json
[b-230]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761230-103-se-se.json
[b-248]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761248-601-se-dk.json
[b-255]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761255-118-se-se.json
[b-263]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761263-109-se-ro.json
[b-271]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761271-112-se-ro.json
[b-289]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761289-109-se-hu.json
[b-297]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761297-112-se-hu.json
[b-305]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761305-109-se-no.json
[b-313]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761313-112-se-no.json
[b-339]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761339-601-se-hu.json
[b-347]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761347-601-se-ro.json
[b-354]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761354-109-se-dk.json
[r-22001]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22001-109-se-pl-without-sent.json
[r-22015]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22015-112-se-pl-access-point.json
[r-22020]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22020-112-se-pl-payer-code-1.json
[l-pc-99999]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-99999-16010.json
[l-pc-11151]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-11151-route.json
[l-pc-pl]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-pl-route-16009.json
[l-sp-se]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-se-capacity-not-applied.json
[l-sp-pl]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-pl-capacity-too-large.json
[l-pm-pl]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-pl.json
[l-pm-se]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-se.json
[l-products]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-products-109-112-payer-codes.json
