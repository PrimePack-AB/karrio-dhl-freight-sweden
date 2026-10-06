---
title: "DHL Freight SE sandbox findings, 2026-10-05 and 2026-10-06"
---

## Environment and method

All calls went to the DHL Freight (Sweden) API Farm test host `test-api.freight-logistics.dhl.com` on 2026-10-05, except the suite runs on 2026-10-06 named below, and all times below are UTC.
Every booking used customer number 116768 as the Consignor party id, which DHL API Farm support needs to trace these bookings.
The rules are compared against the DHL Freight (Sweden) product manual version 5.26, updated 2026-10-01 and valid from 2026-11-01 (sha256 `050660c37ba93d1ae9514c50dfa42c2010bc87763ccaff51a740b2526af11b73`), which DHL lists at <https://dhlpaket.se/dashboard/specifications/products/>, and page numbers below refer to that version.
The manual names 202, 205, and 233 DHL ROAD FREIGHT STANDARD, DHL ROAD FREIGHT DIRECT, and DHL ROAD FREIGHT PRIORITY (§5.4, §5.9, §5.10), the names the Product API returns for 202 and 233 ([lookup-product-matches-se-pl.json][l-pm-pl]).

The calls came from three sources.
A read-only probe script called the Product, AdditionalService, ServicePointLocator, and PostalCode APIs at 14:14.
Two scripts booked directly against TransportInstruction (14:31) and through the connector (14:48).
The opt-in sandbox suite in `sandbox_tests/` ran its lookup and booking segments between 16:20 and 16:31, its rejection and declaration segments at 16:53, its 109 DK ParcelShop case at 17:14, and its 103 id-only AccessPoint rejection at 17:31, and on 2026-10-06 its 112 FR case at 08:10, its 112 GB case at 08:29, skipped by the product matches check, and at 08:39 without that check, its thirteen special-territory product matches probes at 08:52, and its 112 and 109 Åland and 202 Northern Ireland cases at 09:07.
A manual capacity probe with the connector ran at 16:21.

Each finding has one evidence file in `tests/dhl_freight_sweden/fixtures/sandbox/`, named by kind: `booking-<id>-...`, `rejection-<error code>-...`, `lookup-...`, or `label-<id>-...`.
An evidence file holds the request and response bodies of the calls behind the finding, with metadata naming the endpoint, product, route, booking id or error code, and the capturing script or suite test.
Each call records the path of its original capture relative to `$XDG_STATE_HOME` (`~/.local/state`) and the sha256 of that capture file, so the original can be checked against the committed copy.
The committed copies drop the `client-key` header and the response headers, and replace label base64 with a length marker.
The original captures masked the customer number in the Consignor party id; the evidence files restore it and record the restored placeholder under `account_number_restored`.
Product API responses are reduced to the fields a finding uses, and such calls carry a `response_reduced` note.
A `label` file holds a Print API call with the label's page size and its `pdftotext -layout` text, citing the PDF and text files it was taken from.
The `label` files come from the suite's print calls of bookings 2906761222, 2906761230, 2906761248, 2906761255, 2906761297, 2906761305, 2906761354, and 2906761867.
`tests/dhl_freight_sweden/test_sandbox_evidence.py` checks the files offline for these redactions and parses every response body with the connector's parsers.
`sandbox_tests/dhl_freight_sweden/evidence.py` builds the files from the captures, and rebuilding over the same captures reproduces them byte for byte.

## Bookings

All 21 bookings returned status `Succes`, a transport instruction id, a piece id, and a routing code, and every shipper was Stockholm SE 11143.
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
| 2906761867 | 2026-10-06 08:10:52 | 112 | SE → FR 75004 | 023 | none | none | 2LFR75004+74000000 | [booking-2906761867][b-867] |
| 2906761917 | 2026-10-06 09:07:41 | 109 | SE → FI 22100 (Åland) | 022 | none | 8011-221003201 ParcelShop | 2LFI22100+70530000 | [booking-2906761917][b-917] |
| 2906761925 | 2026-10-06 09:07:54 | 202 | SE → GB BT1 1AA (Northern Ireland) | DAP | none | none | 2LGBBT11AA+11000000 | [booking-2906761925][b-925] |

The time is the response `Date` header, except for the three direct bookings whose captures carry no header, where it is the capture file's modification time.
The 109 and 112 bookings to PL declared `SENT_FREE` `"true"`; 2906761339 sent `EKAER_FREE` `"false"` with the placeholder `EKAER_NUMBER` `E0000SANDBOX0001`, and 2906761347 sent `UIT_FREE` `"false"` without a number, and DHL echoed these entries in the responses.
No other booking sent additional information entries.
The response to 2906761867 (112 to FR) carried three `additionalInformation` entries the request did not send, `ChronoPostReference` `XY222000028`, `ChronopostLicencePlate` `0075004XY222000028336835250C`, and `CHRONOPOST` `"true"` ([booking-2906761867][b-867]).
Every booking except 2906761073, 2906761081, and 2906761149 was followed by a Print API call that returned a PDF label (`label_<id>.pdf`).
The label of 2906761354, printed with page type `Label`, is one PDF page of 297.638 × 595.276 pt (105 × 210 mm) ([label-2906761354][lb-354]).
Its text shows the Consignee name below the sender block and the Consignee name and address at the bottom, and its only `Phn.` line carries the sender's +46 8 123 456, although the booking sent the consignee phone +45 20 12 34 56.
The 109 NO label of 2906761305 shows the Consignee name and address, Karl Johans gate 10, 0154 Oslo, at the bottom, apart from the shop's CHRISTIAN KROHGS GATE 1, 0186 OSLO, and likewise prints only the sender's phone ([label-2906761305][lb-305]).
The home-delivery labels of 102, 118, and 601, the 112 label to HU, and the 103 service-point label print a `Phn.` line with no number ([label-2906761222][lb-222], [label-2906761297][lb-297], [label-2906761255][lb-255], [label-2906761248][lb-248], [label-2906761230][lb-230]); the section [Phone numbers on labels](#phone-numbers-on-labels) compares these labels with the manual.
The 112 FR label of 2906761867, printed with page type `Label`, is one PDF page of 283.46 × 425.2 pt (100 × 150 mm) in a different layout from the other labels: it shows the Chronopost reference XY22 2000 028, the licence plate, and the routing code (403)25075004+74000000, and no `Phn.` line ([label-2906761867][lb-867]).
Booking 2906761255 (118) was preceded by a PostalCode route lookup for SE 11151 that returned `homeDeliveryParcel` `true`, the connector's `enforce` pre-flight ([booking-2906761255][b-255]).
The suite's lookup segment returned the same flags for SE 11151, `bookable` `true` and `homeDeliveryParcel` `true` ([lookup-postal-code-se-11151-route.json][l-pc-11151]), the route flag the manual ties to 118 (§10.14.7 p235).
The 103 and 109 bookings to RO, HU, NO, DK, and FI 22100 were preceded by the service point lookup the point was taken from, and those lookups are included in the evidence files.
The five service points nearest Mariehamn 22100 were Posti points in Åland of type `postoffice`, with ids 8011-221003201 to 8011-224103201 ([booking-2906761917][b-917]).

## Rejections

The suite's rejection segment built a valid request through the connector and changed the serialized payload just before sending, and DHL answered each with HTTP 400, the first three with one validation error and the 103 case with four.
The booking-export segment's 112 GB case, sent without its product matches check, was answered with HTTP 400 and two validation errors, and its 112 Åland case, which passed the check, with HTTP 400 and one.
No booking was created by any of them.

| Error code | Field | Message | Payload | Evidence |
|------------|-------|---------|---------|----------|
| 22001 | `AdditionalInformation` | SENT_REF and SENT_CARKEY are mandatory unless SENT_FREE is true. | 109 SE → PL 30-079, payer code 022, ParcelShop 8005-PL-4504339, no SENT entries | [rejection-22001][r-22001] |
| 22015 | `Parties[2]` | AccessPoint Party is not allowed for this product | 112 SE → PL 30-079, payer code 023, `SENT_FREE` `"true"`, added AccessPoint ParcelShop 8005-PL-4504339 | [rejection-22015][r-22015] |
| 22020 | `PayerCode.Code` | Payercode 1 is not valid for product | 112 SE → PL 30-079, payer code 1, `SENT_FREE` `"true"` | [rejection-22020][r-22020] |
| 22001 | `Parties[2].Address.Address` | Address is mandatory for party AccessPoint | 103 SE → SE 11151, AccessPoint SE-982000 with only id, type, and sub type | [rejection-22001-103][r-22001-103] |
| 22001 | `Parties[2].Name` | Name is mandatory for party AccessPoint | same request | [rejection-22001-103][r-22001-103] |
| 22026 | `Parties[2]` | AccessPoint CountryCode is not valid for this product | same request | [rejection-22001-103][r-22001-103] |
| 22006 | `Parties[2].PostalCode` | Error retrieving gateway linehaul for shipment | same request | [rejection-22001-103][r-22001-103] |
| 22005 | `ProductCode` | No valid product was found for given productcode and countries | 112 SE → GB W1D 1AN, payer code 023, customs handling full service, one commodity | [rejection-22005-112-gb][r-22005-gb] |
| 22026 | `Parties[1]` | Consignee CountryCode is not valid for this product | same request | [rejection-22005-112-gb][r-22005-gb] |
| 24003 | `customsHandlingFullService` | customsHandlingFullService is not available for this country combination | 112 SE → FI 22100, payer code 023, customs handling full service, one commodity, proforma invoice | [rejection-24003-112-fi-aland][r-24003-ax] |

The PostalCode API rejected the unknown SE postal code 99999 with HTTP 400 and the PascalCase ErrorResult `{"ErrorCode": 16010, "Status": 400, "UserMessage": "Post code '99999' not found."}` ([lookup-postal-code-se-99999-16010.json][l-pc-99999]).
Its route lookup for PL 30-079 answered HTTP 400 with 16009 "Country code 'PL' not supported." ([lookup-postal-code-pl-route-16009.json][l-pc-pl]), which matches the manual listing the route service only for domestic products (§10.14.1 p230).

## Special territories in product matches

The lookup segment asked product matches which products ship a 2.5 kg piece of 40 × 30 × 15 cm from SE 11143 to thirteen recipients, each sent with the country code and postal code as given.
Every call answered HTTP 200 without an error message.

| Recipient | Area | Products matched | Evidence |
|-----------|------|------------------|----------|
| FI 00100 | mainland Finland (control) | HDI, 109, 202, 112, 601, 233 | [se-fi-00100][l-t-fi-00100] |
| FI 22100 | Åland under FI | HDI, 109, 202, 112, 601, 233 | [se-fi-22100][l-t-fi-22100] |
| AX 22100 | Åland under AX | none | [se-ax-22100][l-t-ax] |
| GB W1D 1AN | London (control) | HDI, 202, 601, 233 | [se-gb-w1d1an][l-t-gb-w1d] |
| GB BT1 1AA | Northern Ireland under GB | HDI, 202, 601, 233 | [se-gb-bt11aa][l-t-gb-bt] |
| GB IM1 1AA | Isle of Man under GB | HDI, 202, 601, 233 | [se-gb-im11aa][l-t-gb-im] |
| GB JE2 3AB | Jersey under GB | HDI, 233 | [se-gb-je23ab][l-t-gb-je] |
| GB GY1 1AA | Guernsey under GB | HDI, 233 | [se-gb-gy11aa][l-t-gb-gy] |
| JE JE2 3AB | Jersey under JE | none | [se-je-je23ab][l-t-je] |
| GG GY1 1AA | Guernsey under GG | none | [se-gg-gy11aa][l-t-gg] |
| DK 3900 | Greenland under DK | HDI, 109 | [se-dk-3900][l-t-dk] |
| FO 100 | Faroe Islands under FO | none | [se-fo-100][l-t-fo] |
| ES 35001 | Canary Islands under ES | HDI | [se-es-35001][l-t-es] |

The territory codes AX, JE, GG, and FO matched no product, while the same postal codes under FI and GB did.
Product matches treated FI 22100 like mainland Finland, offering 109 and 112 to Åland.
The evidence files keep each matched product's `toCountries` entries with a `postalCodeExcludes` value and the entry of the recipient country.
The excludes the matches applied agree with these entries: 202 and 601 list GB `GY*,JE*`, while 233 lists no GB excludes and was matched to GB JE2 3AB and GY1 1AA ([se-gb-je23ab][l-t-gb-je], [se-gb-w1d1an][l-t-gb-w1d]); 202, 601, and 233 list DK `39*`, ES `35*`, and were not matched to DK 3900 or ES 35001 ([se-dk-3900][l-t-dk], [se-es-35001][l-t-es]).
The entries list no excludes for GB `BT` or `IM`, and 202 and 601 were matched to GB BT1 1AA and IM1 1AA.

| Product | DK | ES | FR | GB | IT | NO | PT | UA |
|---------|----|----|----|----|----|----|----|----|
| 109 | `38*,???,2412` | `35*,38*,51*,52*` | `97*,98*,99*` | | `00120,22061,23041,4789?` | `917*,8099` | `9*` | |
| 112 | `39*, ???,2412` | `35*,38*,51080,52080` | | | `22061,23041,23030,4789*,04020,04027,25050,25080,28898,58012` | `917*,8099` | `9*` | |
| 202 | `39*, ???,2412` | `35*,38*,51*,52*` | `97*` | `GY*,JE*` | | `917*,8099` | `9*` | `95*, 96*,97*,98*,99*` |
| 233 | `39*, ???,2412` | `35*,38*,51*,52*` | | | | `917*,8099` | `9*` | |
| 601 | `39*,???,2142` | `35*,38*,51*,52*` | `97*` | `GY*,JE*` | | `917*,8099` | `9*` | |

The table quotes the `postalCodeExcludes` strings of the FI 00100 answer, the one that matched all five products ([se-fi-00100][l-t-fi-00100]); HDI carries none.
For 601 DK the string ends in `2142` where 109, 112, 202, and 233 have `2412` ([se-fi-00100][l-t-fi-00100]); the connector treats 601's `2142` as a typo for 2412, Christiansø, and excludes 2412 for 601 like the other products.

The catalog differs from the manual's excluded areas for 109 and 112.
The manual excludes DK 3800-3999 for both (§5.3 p18, §5.14 p63), while the 109 entry excludes `38*` and three-character codes only, and product matches offered 109 to DK 3900 ([se-dk-3900][l-t-dk]).
The manual excludes FR 97100-99999 for both, while the 109 entry excludes `97*,98*,99*`, which adds 97000-97099, and the 112 entry lists no FR excludes.
The manual excludes ES Ceuta (51080) and Melilla (52080) for both, while the 109 entry excludes `51*,52*`.
For 112 to IT the manual lists Serle (25080) and Bella Island (28838), while the 112 entry lists 25050, 25080, and 28898.
The manual excludes GB Jersey (JE), Guernsey (GY), and Northern Ireland (BT) and the NL Caribbean islands for both, while neither entry lists GB or NL excludes, and product matches offered neither 109 nor 112 to any GB postal code.

### Bookings to special territories

109 to FI 22100 booked to the Posti ParcelShop 8011-221003201 in Mariehamn without customs data and returned routing code 2LFI22100+70530000 ([booking-2906761917][b-917]).
112 to FI 22100 with customs information and `customsHandlingFullService` was rejected with 24003 "customsHandlingFullService is not available for this country combination", although product matches had offered 112 for the lane ([rejection-24003-112-fi-aland][r-24003-ax]).
The manual names Åland (FI 22) as an area outside the tax area where customs proceedings are mandatory (§7.4 p162), while the sandbox refused the full-service customs handling for SE to FI 22100 and accepted a 109 booking there without customs data; the evidence does not show how DHL handles customs for Åland.
202 to GB BT1 1AA booked with payer code DAP and without customs data and returned routing code 2LGBBT11AA+11000000 ([booking-2906761925][b-925]); the catalog marks GB `customs` `true` for 202 ([se-gb-bt11aa][l-t-gb-bt]).
202 to GB JE2 3AB was not sent, because the connector refuses it under the catalog's `JE*` exclude and product matches did not offer 202 there ([se-gb-je23ab][l-t-gb-je]).

## Deviations from manual v5.26

### Payer codes for 109 and 112

The manual lists only payer code 023 for 112 (§5.3 p19), but the sandbox accepted 112 to PL with payer code 022 ([booking-2906761149][b-149]) as well as 023 ([booking-2906761131][b-131]).
It rejected payer code 1 for 112 with 22020 ([rejection-22020][r-22020]).
The Product API catalog lists CPT, 022, DPU, DAP, 023, CIP, and DDP for both 109 and 112, with `customs` `true` only for DDP ([lookup-products-109-112-payer-codes.json][l-products]), while the manual lists only the Combiterms 022 and 023 for 109 (§5.14 p63) and 023 for 112 (p19).
No booking used an Incoterm as the payer code for 109 or 112.

### SENT for PL

The manual makes `SENT_FREE` ("Is shipment SENT free?") mandatory for shipments to or from PL in the related-fields tables of 202 (§5.4 p23), 205 (§5.9 p42), 233 (§5.10 p47), SPI (§5.11 p52), and 601 (§5.19 p82), with the SENT reference and carrier key mandatory when the shipment is not SENT free, and its API example sends `SENT_FREE` `"false"` with `SENT_REF` and `SENT_CARKEY`.
It does not mention SENT in the sections of 109 (§5.14 pp62-64) or 112 (§5.3 pp17-20).
The sandbox applied the same rule to 109: it rejected 109 to PL without SENT entries with 22001 "SENT_REF and SENT_CARKEY are mandatory unless SENT_FREE is true." ([rejection-22001][r-22001]), and it accepted 109 and 112 to PL with `SENT_FREE` `"true"` at shipment level ([booking-2906761123][b-123], [booking-2906761131][b-131]).
The vendored transport-instruction spec 2.10.0 (`vendor/se-api-farm/transport-instruction-2.10.0.json`) defines an `AdditionalInformation` schema that no other schema references.
No booking sent `SENT_REF` and `SENT_CARKEY`, so the sandbox's acceptance of real SENT identifiers is untested.

### EKAER and UIT for HU and RO

The manual lists EKAER (HU) and UIT (RO) entries in the related-fields tables of 202 (§5.4 p23), 205 (§5.9 p42), 233 (§5.10 p47), SPI (§5.11 p52), and 601 (§5.19 p82), and not for 109 or 112.
The sandbox accepted 109 and 112 to RO and HU without these entries ([booking-2906761263][b-263], [booking-2906761271][b-271], [booking-2906761289][b-289], [booking-2906761297][b-297]), which matches the manual.
For 601 it accepted `EKAER_FREE` `"false"` with a placeholder EKAER number to HU ([booking-2906761339][b-339]) and `UIT_FREE` `"false"` without a UIT number to RO ([booking-2906761347][b-347]); the latter matches the related-fields tables, which mark the UIT code for a shipment that is not UIT free conditional, "Code should be provided if possible" (§5.19 p82).
The EKAER number in that booking, `E0000SANDBOX0001`, is made up, and the sandbox accepted it.

### Service point capacity filter

The ServicePointLocator applied the piece capacity filter for PL but not for SE.
For Stockholm a 2.5 kg piece of 40 × 30 × 15 cm and a 500 kg piece of 300 × 200 × 200 cm returned the same ten service points in the same order ([lookup-service-points-se-capacity-not-applied.json][l-sp-se]).
For Warszawa the 2.5 kg piece returned points, while the 500 kg piece was answered with HTTP 400 "The dimensions are too large for servicepoint", and with `locationTypes` `["locker"]` "The dimensions are too large for locationtype locker" ([lookup-service-points-pl-capacity-too-large.json][l-sp-pl]).

### Service point ids and sub types

For 103 the manual says only the four-digit part nnnn of an id like SE-nnnn00 is to be used (§10.14.2.1 p231), but the sandbox accepted the full id SE-982000 ([booking-2906761230][b-230]).
For SE the lookup's `id` and `servicePointId` are equal (SE-982000), while elsewhere they differ, for example `id` 101 and `servicePointId` 8005-PL-4516440 in Warszawa ([lookup-service-points-pl-capacity-too-large.json][l-sp-pl]) and `id` 231652 and `servicePointId` 8023-231652 in București ([booking-2906761263][b-263]).
Appendix M states that the AccessPoint sub type carries the location type `servicepoint`, `locker`, or `postoffice` (§10.14.2.2 p232), while the vendored spec enumerates `ParcelShop` and `ParcelStation`.
The sandbox accepted `ParcelShop` for PL, RO, NO, and DK ([booking-2906761123][b-123], [booking-2906761263][b-263], [booking-2906761305][b-305], [booking-2906761354][b-354]) and `ParcelStation` for a HU locker ([booking-2906761289][b-289]).
Their routing codes carry 53 and 54 respectively (for example 2LPL30079+70530000 and 2LHU1826+70540000), which matches the routing code column of the table on p232.

### Service types and lookup size for service point products

The manual says only shops and stations with service type `parcel:pick-up` can be selected for 109 (§10.14.2.2 p232), but the sandbox accepted 109 to the HU locker 8013-118530, whose lookup entry lists only `parcel:pick-up-unregistered` ([booking-2906761289][b-289]).
For 103 the manual says to always search the ten closest service points (§5.12 p57), while the suite's 103 booking searched five ([booking-2906761230][b-230]); the lookup segment's capacity check searched ten ([lookup-service-points-se-capacity-not-applied.json][l-sp-se]).

### Customs to NO

The manual's Customs handling - Full service section says a commercial invoice must be sent to DHL and lists routing barcode 001 on the label (§6.5 p92), and for 109 it asks for two copies of the customs documents on the outside of the package (§5.14 p62).
The sandbox accepted 109 and 112 to NO with `customsHandlingFullService`, one commodity, and a `ProformaInvoice` document without an invoice amount or EORI ([booking-2906761305][b-305], [booking-2906761313][b-313]).
No documents were e-mailed to DHL for these bookings, and the evidence does not show whether DHL would act on a missing commercial invoice.
109 to NO returned routing code 2LNO0186+70530001, ending in 001, while 112 to NO returned 2LNO0154+000000 without it.

### Routing code reference and product codes

For 112 (§5.3 p18) and 109 (§5.14 p62) the manual asks for the label's routing code to be sent as a reference in the IFTMIN shipment instruction.
The API bookings sent no routing code, and every booking response returned `routingCode` (for example [booking-2906761131][b-131] and [booking-2906761123][b-123]).
Product matches for SE to PL returned both 601 and HDI ([lookup-product-matches-se-pl.json][l-pm-pl]), and the manual names HDI as the invoice-file code for 601 (§5.19 p81).
Product matches for SE 11143 to SE 41101 returned 502, 118, 104, 102, 402, 211, 401, and 103 ([lookup-product-matches-se-se.json][l-pm-se]).

### Phone numbers on labels

The manual's label field description (§9.4.2) marks the sender phone, field 6 "Consignor or pickup party phone number", conditional, and does not allow printing it for 104, for 402/502, or for 107 from AT, BE, BG, CZ, DE, DK, EE, ES, FI, FR, HR, HU, IE, IT, LT, LU, LV, NL, NO, PL, PT, RO, and SI, while making it mandatory for 107 from SK (p168).
For field 9 it marks the consignee or delivery party phone number conditional and the receiving parcelshop's phone number mandatory for 103 (p170).
It does not allow printing the receiver phone for 109 and 112 to AT, BE, BG, CZ, DE, DK, EE, ES, FI, FR, HR, HU, IE, IT, LT, LU, LV, NL, NO, PL, PT, RO, and SI, makes it mandatory for 109 and 112 to SK, and does not allow it for 118 or 401 (p170).
It makes the receiver's mobile phone number mandatory in the shipment data for 118 (§5.16 p68) and the consignee phone number and e-mail address mandatory for 601 (§5.19 p81).
Every suite booking sent the consignor phone +46 8 123 456 and a consignee phone, and the 103 booking sent no AccessPoint phone.
The 109 labels to DK and NO print the sender phone and no consignee phone, although the bookings sent +45 20 12 34 56 and +47 400 00 000 ([label-2906761354][lb-354], [label-2906761305][lb-305]), which matches the field 9 rule for 109 to DK and NO.
The 112 label to FR prints neither the sender phone nor the consignee phone +33 6 12 34 56 78 and has no `Phn.` line ([label-2906761867][lb-867]), which matches the field 9 rule for 112 to FR and the conditional field 6.
The 112 label to HU prints a `Phn.` line with neither the sender phone nor the consignee phone +36 30 000 0000 ([label-2906761297][lb-297]), and the 118 label prints a `Phn.` line with no number ([label-2906761255][lb-255]); both match the field 9 rules for 112 to HU and for 118, and the missing sender phone matches the conditional field 6.
The 102 and 601 labels print a `Phn.` line with no number ([label-2906761222][lb-222], [label-2906761248][lb-248]), where fields 6 and 9 are conditional.
The 103 service-point label prints a `Phn.` line with no number ([label-2906761230][lb-230]), while the manual makes the receiving parcelshop's phone number mandatory for 103; this remains a deviation.

## Pending verification

The README lists PostalCode error 16012 as "not supported", and no capture shows 16012; the sandbox answered the PL route lookup with 16009 "Country code 'PL' not supported." ([lookup-postal-code-pl-route-16009.json][l-pc-pl]).

## Untested

No booking used the freight products 205, 209, 210, 211, 212, 233, or SPI, 202 was booked only to GB BT1 1AA without customs data, or the parcel and home delivery products 104, 107, 401, 402, and 502.
601 was booked only to DK, HU, and RO; 601 to HU or RO without EKAER or UIT entries, with a free flag `"true"`, or with a UIT number, and 601 to PL, are untested.
109 with home addressing and no AccessPoint party is untested.
112 to GB was not booked: product matches for SE 11143 to GB W1D 1AN returned HDI, 202, 601, and 233 but neither 109 nor 112 ([lookup-product-matches-se-gb.json][l-pm-gb]), and the 112 booking sent regardless was rejected with 22005 and 22026 ([rejection-22005-112-gb][r-22005-gb]); the manual lists GB for 109 and 112 only according to a separate agreement (§5.3 p18, §5.14 p63, Appendix G p200), and 109 to GB was not sent.
Customs was tested only as Customs handling - Full service to NO, and to FI 22100, where it was rejected with 24003; Customs handling - Standard, the customer's own declaration, the joint declaration (including 109 with payer code 023), VOEC, and other destinations outside the EU VAT area are untested.
No additional service other than `customsHandlingFullService` was sent, payer codes 3 and 4 with a freight payer party were not used, and 601 used only DAP.
Every booking had a single piece of 1 kg and 30 × 20 × 10 cm, so multi-piece shipments and bookings below the minimum piece dimensions the manual states for 102 (§5.2 p14) and 112 (§5.3 p17) are untested.
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
[b-867]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761867-112-se-fr.json
[b-917]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761917-109-se-fi-aland.json
[b-925]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761925-202-se-gb-northern-ireland.json
[r-22001]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22001-109-se-pl-without-sent.json
[r-22001-103]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22001-103-se-access-point-id-only.json
[r-22005-gb]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22005-112-se-gb.json
[r-22015]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22015-112-se-pl-access-point.json
[r-24003-ax]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland.json
[r-22020]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22020-112-se-pl-payer-code-1.json
[l-pc-99999]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-99999-16010.json
[l-pc-11151]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-11151-route.json
[l-pc-pl]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-pl-route-16009.json
[l-sp-se]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-se-capacity-not-applied.json
[l-sp-pl]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-pl-capacity-too-large.json
[l-pm-gb]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb.json
[l-pm-pl]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-pl.json
[l-pm-se]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-se.json
[l-products]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-products-109-112-payer-codes.json
[lb-222]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761222-102-se-se.json
[lb-230]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761230-103-se-se-service-point.json
[lb-248]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761248-601-se-dk.json
[lb-255]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761255-118-se-se.json
[lb-297]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761297-112-se-hu.json
[lb-305]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761305-109-se-no-parcelshop.json
[lb-354]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761354-109-se-dk-parcelshop.json
[lb-867]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761867-112-se-fr.json
[l-t-fi-00100]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-fi-00100.json
[l-t-fi-22100]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-fi-22100.json
[l-t-ax]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ax-22100.json
[l-t-gb-w1d]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb-w1d1an.json
[l-t-gb-bt]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb-bt11aa.json
[l-t-gb-im]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb-im11aa.json
[l-t-gb-je]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb-je23ab.json
[l-t-gb-gy]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb-gy11aa.json
[l-t-je]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-je-je23ab.json
[l-t-gg]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gg-gy11aa.json
[l-t-dk]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-dk-3900.json
[l-t-fo]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-fo-100.json
[l-t-es]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-es-35001.json
