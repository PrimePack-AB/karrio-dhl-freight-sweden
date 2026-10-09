---
title: "DHL Freight SE sandbox findings, 2026-10-05 to 2026-10-09"
---

## Method

All calls went to the DHL Freight (Sweden) API Farm test host `test-api.freight-logistics.dhl.com`, and all times below are UTC.
Every booking used customer number 116768 as the Consignor party id, which DHL API Farm support needs to trace these bookings.
On 2026-10-09 DHL API Farm support reviewed the bookings and said that 202 and 233 take the international customer number (utrikeskundnummer) as the Consignor id instead of the domestic 116768.
The sandbox did not reject the earlier bookings that used 116768 on 202 ([2906762121][b-121], [2906762139][b-139]), 233 ([2906762147][b-147], [2906762154][b-154]), and 601 ([2906761248][b-248]).
The connector now sends `international_account_number` for 202, 205, 233, SPI, and 601, per IFTMIN v3.7 p10 and the manual's account number format rows ([booking-rules.md#customer-numbers](../../concepts/booking-rules.md#customer-numbers)), and no sandbox booking has used an international customer number yet.
The rules are compared against the DHL Freight (Sweden) product manual version 5.26, updated 2026-10-01 and valid from 2026-11-01 (sha256 `050660c37ba93d1ae9514c50dfa42c2010bc87763ccaff51a740b2526af11b73`), which DHL lists at <https://dhlpaket.se/dashboard/specifications/products/>, and page numbers below refer to that version.
The manual names 202, 205, and 233 DHL ROAD FREIGHT STANDARD, DHL ROAD FREIGHT DIRECT, and DHL ROAD FREIGHT PRIORITY (§5.4, §5.9, §5.10), the names the Product API returns for 202 and 233 ([lookup-product-matches-se-pl.json][l-pm-pl]).

The calls came from three sources: a read-only probe script, two booking scripts, one direct against TransportInstruction and one through the connector, and the opt-in sandbox suite in `sandbox_tests/`.
A manual capacity probe with the connector also ran once.

| Date | Time | Source | Calls |
|------|------|--------|-------|
| 2026-10-05 | 14:14 | probe script | Product, AdditionalService, ServicePointLocator, and PostalCode APIs, read only |
| 2026-10-05 | 14:31 | direct script | bookings sent directly to TransportInstruction |
| 2026-10-05 | 14:48 | connector script | bookings through the connector |
| 2026-10-05 | 16:20-16:31 | suite | lookup and booking segments |
| 2026-10-05 | 16:21 | manual probe | capacity probe with the connector |
| 2026-10-05 | 16:53 | suite | rejection and declaration segments |
| 2026-10-05 | 17:14 | suite | 109 DK ParcelShop case |
| 2026-10-05 | 17:31 | suite | 103 id-only AccessPoint rejection |
| 2026-10-06 | 08:10 | suite | 112 FR case |
| 2026-10-06 | 08:29 | suite | 112 GB case, skipped by the product matches check |
| 2026-10-06 | 08:39 | suite | 112 GB case without the product matches check |
| 2026-10-06 | 08:52 | suite | thirteen special-territory product matches probes |
| 2026-10-06 | 09:07 | suite | 112 and 109 Åland and 202 Northern Ireland cases |
| 2026-10-06 | 09:12 | suite | 112 Åland case with customs handling Standard |
| 2026-10-06 | 10:39 | suite | freight and Standard customs bookings |
| 2026-10-06 | 11:12 | suite | 401 domestic booking |
| 2026-10-06 | 11:26 | suite | 205 booking forced past the product matches check |
| 2026-10-06 | 12:27 | suite | CH and LI lookups |
| 2026-10-06 | 12:41 | suite | 601 CH booking |
| 2026-10-06 | 13:30 | suite | 109 Åland booking with customs data |
| 2026-10-08 | 08:04 | suite | 601 HU and RO bookings without EKAER or UIT options |
| 2026-10-08 | 08:11 | suite | lookup, rejection, and approved booking segments, with eight TransportInstruction requests of which this note cites only the 109 PL request without SENT entries |
| 2026-10-08 | 08:26 | suite | 601 PL and RO bookings with default SENT free, placeholder SENT identifiers, and a placeholder UIT number |
| 2026-10-08 | 08:48 | suite | 202 and 233 HU and RO bookings without EKAER or UIT options |
| 2026-10-08 | 15:12 | suite | PostalCode route lookups and `enforce` pre-flights |
| 2026-10-08 | 15:27 | suite | PostalCode route lookup and `enforce` pre-flight with an unknown client key |
| 2026-10-09 | 07:49 | suite | 103 service point booking with the four-digit terminal id |

Each finding cites one evidence file in `tests/dhl_freight_sweden/fixtures/sandbox/`.
[Sandbox suite and evidence](../../development/traceability/sandbox-suite.md#evidence) describes the files' naming, metadata, and redaction, and how they are rebuilt byte for byte from the captures.
The `label` files come from the suite's print calls of bookings 2906761222, 2906761230, 2906761248, 2906761255, 2906761297, 2906761305, 2906761354, and 2906761867.

## Bookings

All 42 bookings returned status `Succes`, a transport instruction id, a piece id, and a routing code, and every shipper was Stockholm SE 11143.
Every booking had one piece of 1 kg and 30 × 20 × 10 cm, except 2906762477 with one piece of 2 kg and 30 × 20 × 15 cm.
None was cancelled, because the API Farm has no cancellation operation.
The evidence files keep each booking's routing code; the routing codes that bear on a finding are quoted under [Deviations from manual v5.26](#deviations-from-manual-v526).
The 103 and 109 bookings to RO, HU, NO, DK, FI 22100, and, for 2906769613, PL were preceded by the service point lookup the point was taken from, and those lookups are included in the evidence files.
The Options column gives the payer code, any service point, customs data, and additional information entries; only the bookings that list customs data carried any, and DHL echoed every additional information entry sent.
The direct-script bookings 2906761073 and 2906761081 and the connector-script booking 2906761149 were not printed; every other booking was followed by a Print API call that returned a PDF label (`label_<id>.pdf`).

### Domestic SE

| Date | Product | Lane | Options | Shipment id | Evidence |
|------|---------|------|---------|-------------|----------|
| 2026-10-05 | 102 | SE → SE 11151 | payer code 1 | 2906761222 | [booking][b-222], [label][lb-222] |
| 2026-10-05 | 103 | SE → SE 11151 | payer code 1, ParcelShop SE-982000 sent as the full id | 2906761230 | [booking][b-230], [label][lb-230] |
| 2026-10-05 | 118 | SE → SE 11151 | payer code 1, after an `enforce` PostalCode route pre-flight | 2906761255 | [booking][b-255], [label][lb-255] |
| 2026-10-06 | 401 | SE → SE 11151 | payer code 1 | 2906762303 | [booking][b-303] |
| 2026-10-09 | 103 | SE → SE 11151 | payer code 1, ParcelShop SE-982000 sent as the four-digit terminal id 9820 | 2906771650 | [booking][b-650] |

### Intra-EU

| Date | Product | Lane | Options | Shipment id | Evidence |
|------|---------|------|---------|-------------|----------|
| 2026-10-05 | 109 | SE → PL 30-079 | 022, ParcelShop 8005-PL-4507446, `SENT_FREE` `"true"`, sent directly to TransportInstruction | 2906761073 | [booking][b-073] |
| 2026-10-05 | 112 | SE → PL 30-079 | 023, `SENT_FREE` `"true"`, sent directly to TransportInstruction | 2906761081 | [booking][b-081] |
| 2026-10-05 | 109 | SE → PL 30-079 | 022, ParcelShop 8005-PL-4507446, `SENT_FREE` `"true"` | 2906761123 | [booking][b-123] |
| 2026-10-05 | 112 | SE → PL 30-079 | 023, `SENT_FREE` `"true"` | 2906761131 | [booking][b-131] |
| 2026-10-05 | 112 | SE → PL 30-079 | 022, `SENT_FREE` `"true"` | 2906761149 | [booking][b-149] |
| 2026-10-05 | 601 | SE → DK 1620 | DAP | 2906761248 | [booking][b-248], [label][lb-248] |
| 2026-10-05 | 109 | SE → RO 030031 | 022, ParcelShop 8023-231652 | 2906761263 | [booking][b-263] |
| 2026-10-05 | 112 | SE → RO 030031 | 023 | 2906761271 | [booking][b-271] |
| 2026-10-05 | 109 | SE → HU 1052 | 022, ParcelStation 8013-118530, a locker | 2906761289 | [booking][b-289] |
| 2026-10-05 | 112 | SE → HU 1052 | 023 | 2906761297 | [booking][b-297], [label][lb-297] |
| 2026-10-05 | 601 | SE → HU 1052 | DAP, `EKAER_FREE` `"false"`, placeholder `EKAER_NUMBER` `E0000SANDBOX0001` | 2906761339 | [booking][b-339] |
| 2026-10-05 | 601 | SE → RO 030031 | DAP, `UIT_FREE` `"false"` without a number | 2906761347 | [booking][b-347] |
| 2026-10-05 | 109 | SE → DK 1620 | 022, ParcelShop 8009-115191 | 2906761354 | [booking][b-354], [label][lb-354] |
| 2026-10-06 | 112 | SE → FR 75004 | 023 | 2906761867 | [booking][b-867], [label][lb-867] |
| 2026-10-06 | 202 | SE → DK 1620 | DAP | 2906762121 | [booking][b-121] |
| 2026-10-06 | 233 | SE → DK 1620 | DAP | 2906762147 | [booking][b-147] |
| 2026-10-08 | 601 | SE → HU 1052 | DAP, `EKAER_FREE` `"true"` alone, the connector's default | 2906769555 | [booking][b-555] |
| 2026-10-08 | 601 | SE → RO 030031 | DAP, `UIT_FREE` `"true"` alone, the connector's default | 2906769563 | [booking][b-563] |
| 2026-10-08 | 109 | SE → PL 30-079 | 022, ParcelShop 8005-PL-4504339, no SENT entries | 2906769613 | [booking][b-613] |
| 2026-10-08 | 601 | SE → PL 30-079 | DAP, `SENT_FREE` `"true"` alone, the connector's default | 2906769647 | [booking][b-647] |
| 2026-10-08 | 601 | SE → PL 30-079 | DAP, `SENT_FREE` `"false"`, placeholder `SENT_REF` `SENT20261008000001` and `SENT_CARKEY` `SANDBOXCARKEY0001` | 2906769654 | [booking][b-654] |
| 2026-10-08 | 601 | SE → RO 030031 | DAP, `UIT_FREE` `"false"`, placeholder `UIT_NUMBER` `0000-0000-0000-0001` | 2906769662 | [booking][b-662] |
| 2026-10-08 | 202 | SE → HU 1052 | DAP, `EKAER_FREE` `"true"` alone, the connector's default | 2906769969 | [booking][b-969] |
| 2026-10-08 | 202 | SE → RO 030031 | DAP, `UIT_FREE` `"true"` alone, the connector's default | 2906769977 | [booking][b-977] |
| 2026-10-08 | 233 | SE → HU 1052 | DAP, `EKAER_FREE` `"true"` alone, the connector's default | 2906769985 | [booking][b-985] |
| 2026-10-08 | 233 | SE → RO 030031 | DAP, `UIT_FREE` `"true"` alone, the connector's default | 2906769993 | [booking][b-993] |

The response to 2906761867 (112 to FR) carried three `additionalInformation` entries the request did not send, `ChronoPostReference` `XY222000028`, `ChronopostLicencePlate` `0075004XY222000028336835250C`, and `CHRONOPOST` `"true"` ([booking-2906761867][b-867]).

### Outside the EU VAT area and special territories

| Date | Product | Lane | Options | Shipment id | Evidence |
|------|---------|------|---------|-------------|----------|
| 2026-10-05 | 109 | SE → NO 0154 | 022, ParcelShop 8009-129635, customs handling full service, one commodity, `ProformaInvoice` without invoice amount or EORI | 2906761305 | [booking][b-305], [label][lb-305] |
| 2026-10-05 | 112 | SE → NO 0154 | 023, customs handling full service, one commodity, `ProformaInvoice` without invoice amount or EORI | 2906761313 | [booking][b-313] |
| 2026-10-06 | 109 | SE → FI 22100 (Åland) | 022, Posti ParcelShop 8011-221003201, no customs data | 2906761917 | [booking][b-917] |
| 2026-10-06 | 202 | SE → GB BT1 1AA (Northern Ireland) | DAP, no customs data | 2906761925 | [booking][b-925] |
| 2026-10-06 | 109 | SE → NO 0154 | 022, ParcelShop 8009-129635, customs handling Standard, made-up EORI SE0000000000, one commodity, `ProformaInvoice` | 2906762105 | [booking][b-105] |
| 2026-10-06 | 112 | SE → NO 0154 | 023, customs handling Standard, made-up EORI SE0000000000, one commodity, `ProformaInvoice` | 2906762113 | [booking][b-113] |
| 2026-10-06 | 202 | SE → NO 0154 | DAP, customs handling full service, one commodity, `ProformaInvoice` | 2906762139 | [booking][b-139] |
| 2026-10-06 | 233 | SE → NO 0154 | DAP, customs handling full service, one commodity, `ProformaInvoice` | 2906762154 | [booking][b-154] |
| 2026-10-06 | 601 | SE → NO 0154 | DAP, customs handling full service, one commodity, `ProformaInvoice` | 2906762162 | [booking][b-162] |
| 2026-10-06 | 601 | SE → CH 8001 | DAP, customs handling full service, one commodity, `CommercialInvoice` with `invoiceAmount` 200.0 SEK, consignee phone and e-mail address | 2906762477 | [booking][b-477] |
| 2026-10-06 | 109 | SE → FI 22100 (Åland) | 022, Posti ParcelShop 8011-221003201, customs data without a customs service, `CommercialInvoice` | 2906762592 | [booking][b-592] |

Booking 2906762592 sent an export `CommercialInvoice` document SANDBOX-INV-1 with invoice amount 200 SEK and one commodity, HS code 610910, origin SE, customs value 200 SEK, procedure code 1042, net weight 0.5 kg, and one unit, and no customs service.
DHL echoed the document and the commodity unchanged except for the invoice date, returned as `2026-10-06T00:00:00`, echoed empty `additionalServices`, and returned the same routing code as booking 2906761917 without customs data.
The response shows only that DHL accepted and stored the customs information; the evidence does not show what DHL does with it after booking.
Booking 2906762477 sent the consignee phone and e-mail address the manual makes mandatory for 601 (§5.19 p81), and its response echoed `customsHandlingFullService` `true` and the `CommercialInvoice` document with its amount and currency, returning the invoice date as `2026-10-06T00:00:00` and the routing code 2LCH8001+00000001, which ends in the routing barcode 001 that the manual lists for Customs handling - Full service (§6.5 p92).
No documents were e-mailed to DHL for the NO and CH bookings, so the evidence does not show what DHL does after booking with the commercial invoice it asks for, or whether DHL would act on a missing one.
The catalog marks GB `customs` `true` for 202 ([se-gb-bt11aa][l-t-gb-bt]), while booking 2906761925 to Northern Ireland carried no customs data.
202 to GB JE2 3AB was not sent, because the connector refuses it under the catalog's `JE*` exclude and product matches did not offer 202 there ([se-gb-je23ab][l-t-gb-je]).
No booking was sent to LI, and no CH booking used 202, 233, HDI, or customs handling Standard, which the manual limits to NO and Åland (§6.6 p94).

## Labels

All eight labels with evidence files were printed with page type `Label`.
Every suite booking sent the consignor phone +46 8 123 456 and a consignee phone, and the 103 booking sent no AccessPoint phone.

| Booking | Product and lane | Page | Content | Evidence |
|---------|------------------|------|---------|----------|
| 2906761222 | 102 SE → SE | one page, 297.638 × 595.276 pt (105 × 210 mm) | a `Phn.` line with no number | [label-2906761222][lb-222] |
| 2906761230 | 103 SE → SE, service point SE-982000 | one page, 105 × 210 mm | a `Phn.` line with no number | [label-2906761230][lb-230] |
| 2906761248 | 601 SE → DK | one page, 105 × 210 mm | a `Phn.` line with no number, and not the consignee phone +45 20 12 34 56 | [label-2906761248][lb-248] |
| 2906761255 | 118 SE → SE | one page, 105 × 210 mm | a `Phn.` line with no number | [label-2906761255][lb-255] |
| 2906761297 | 112 SE → HU | one page, 105 × 210 mm | a `Phn.` line with neither the sender phone nor the consignee phone +36 30 000 0000 | [label-2906761297][lb-297] |
| 2906761305 | 109 SE → NO, ParcelShop 8009-129635 | one page, 105 × 210 mm | the Consignee name and address, Karl Johans gate 10, 0154 Oslo, at the bottom, apart from the shop's CHRISTIAN KROHGS GATE 1, 0186 OSLO; the sender's phone as the only `Phn.` line, and not the consignee phone +47 400 00 000 | [label-2906761305][lb-305] |
| 2906761354 | 109 SE → DK, ParcelShop 8009-115191 | one page, 297.638 × 595.276 pt (105 × 210 mm) | the Consignee name below the sender block and the Consignee name and address at the bottom; the sender's +46 8 123 456 as the only `Phn.` line, and not the consignee phone +45 20 12 34 56 | [label-2906761354][lb-354] |
| 2906761867 | 112 SE → FR | one page, 283.46 × 425.2 pt (100 × 150 mm), in a different layout from the other labels | the Chronopost reference XY22 2000 028, the licence plate, and the routing code (403)25075004+74000000; no `Phn.` line, and not the consignee phone +33 6 12 34 56 78 | [label-2906761867][lb-867] |

The print calls for 2906762477 (601 to CH) and 2906762592 (109 to Åland) each returned one PDF label, the first as one report of type `Label`.

The manual's label field description (§9.4.2) marks the sender phone, field 6 "Consignor or pickup party phone number", conditional, and does not allow printing it for 104, for 402/502, or for 107 from AT, BE, BG, CZ, DE, DK, EE, ES, FI, FR, HR, HU, IE, IT, LT, LU, LV, NL, NO, PL, PT, RO, and SI, while making it mandatory for 107 from SK (p168).
For field 9 it marks the consignee or delivery party phone number conditional and the receiving parcelshop's phone number mandatory for 103 (p170).
It does not allow printing the receiver phone for 109 and 112 to AT, BE, BG, CZ, DE, DK, EE, ES, FI, FR, HR, HU, IE, IT, LT, LU, LV, NL, NO, PL, PT, RO, and SI, makes it mandatory for 109 and 112 to SK, and does not allow it for 118 or 401 (p170).
It makes the receiver's mobile phone number mandatory in the shipment data for 118 (§5.16 p68) and the consignee phone number and e-mail address mandatory for 601 (§5.19 p81).
The 109 labels to DK and NO, the 112 labels to FR and HU, and the 118 label match the field 9 rules, and the missing sender phone on the 112 and 118 labels matches the conditional field 6.
On the 102 and 601 labels fields 6 and 9 are conditional.
The 103 label is the one deviation, listed under [Deviations from manual v5.26](#deviations-from-manual-v526).

## Rejections

Every answer below was HTTP 400 and created no booking.
The rejection segment built a valid request through the connector and changed the serialized payload just before sending (the four 2026-10-05 rows); the booking-export segment sent the GB and 205 cases without their product matches check and the two Åland cases after it.

| Date | Product | Lane | Mutation or request | DHL code and message | Evidence |
|------|---------|------|---------------------|----------------------|----------|
| 2026-10-05; accepted 2026-10-08 | 109 | SE → PL 30-079 | payer code 022, ParcelShop 8005-PL-4504339, SENT entries removed | 22001 `AdditionalInformation` "SENT_REF and SENT_CARKEY are mandatory unless SENT_FREE is true."; on 2026-10-08 DHL accepted the unchanged request as booking 2906769613, and the request was not retried since | [rejection-22001][r-22001], [booking-2906769613][b-613] |
| 2026-10-05 | 112 | SE → PL 30-079 | payer code 023, `SENT_FREE` `"true"`, AccessPoint ParcelShop 8005-PL-4504339 added | 22015 `Parties[2]` "AccessPoint Party is not allowed for this product" | [rejection-22015][r-22015] |
| 2026-10-05 | 112 | SE → PL 30-079 | payer code changed to 1, `SENT_FREE` `"true"` | 22020 `PayerCode.Code` "Payercode 1 is not valid for product" | [rejection-22020][r-22020] |
| 2026-10-05 | 103 | SE → SE 11151 | AccessPoint SE-982000 reduced to id, type, and sub type | 22001 `Parties[2].Address.Address` "Address is mandatory for party AccessPoint"; 22001 `Parties[2].Name` "Name is mandatory for party AccessPoint"; 22026 `Parties[2]` "AccessPoint CountryCode is not valid for this product"; 22006 `Parties[2].PostalCode` "Error retrieving gateway linehaul for shipment" | [rejection-22001-103][r-22001-103] |
| 2026-10-06 | 112 | SE → GB W1D 1AN | payer code 023, customs handling full service, one commodity, sent without the product matches check | 22005 `ProductCode` "No valid product was found for given productcode and countries"; 22026 `Parties[1]` "Consignee CountryCode is not valid for this product" | [rejection-22005-112-gb][r-22005-gb] |
| 2026-10-06 | 112 | SE → FI 22100 (Åland) | payer code 023, customs handling full service, one commodity, proforma invoice, after product matches offered 112 | 24003 `customsHandlingFullService` "customsHandlingFullService is not available for this country combination" | [rejection-24003-112-fi-aland][r-24003-ax] |
| 2026-10-06 | 112 | SE → FI 22100 (Åland) | payer code 023, customs handling Standard, made-up EORI number SE0000000000, one commodity, proforma invoice | 24003 `customsHandlingStandard` "customsHandlingStandard is not available for this country combination" | [rejection-24003-112-fi-aland-standard][r-24003-ax-std] |
| 2026-10-06 | 205 | SE → NO 0154 | payer code DAP, customs handling full service, one commodity, one 1 kg piece, sent without the product matches check | 22020 `ChargeableWeight` "ChargeableWeight is lower than product min 2500.0" | [rejection-22020-205-no][r-22020-205-no] |

## Lookup errors

| Date | Code | API | Input | Message | Evidence |
|------|------|-----|-------|---------|----------|
| 2026-10-05 | 16010 | PostalCode | SE 99999 | HTTP 400 with the PascalCase ErrorResult `{"ErrorCode": 16010, "Status": 400, "UserMessage": "Post code '99999' not found."}` | [lookup-postal-code-se-99999-16010.json][l-pc-99999] |
| 2026-10-08 | 16011 | PostalCode | SE 84094 | "Post code '84094' (Landsbygd) not supported." | [lookup-postal-code-se-84094-16011.json][l-pc-84094] |
| 2026-10-08 | 16012 | PostalCode | SE 98060 | "Post code '98060' not supported." | [lookup-postal-code-se-98060-16012.json][l-pc-98060] |
| 2026-10-05 | 16009 | PostalCode route | PL 30-079 | HTTP 400, "Country code 'PL' not supported." | [lookup-postal-code-pl-route-16009.json][l-pc-pl] |
| 2026-10-06 | 16009 | PostalCode route | CH 8001 | HTTP 400, "Country code 'CH' not supported." | [lookup-postal-code-ch-8001-16009][l-pc-ch] |
| 2026-10-08 | none | PostalCode route | SE 11151 with the client key `not-a-real-key` | HTTP 401, `{"error": "No valid application matching client key"}` | [lookup-postal-code-se-11151-401-unknown-client-key.json][l-pc-401] |
| 2026-10-05 | none | ServicePointLocator | Warszawa, one 500 kg piece of 300 × 200 × 200 cm | HTTP 400, "The dimensions are too large for servicepoint" | [lookup-service-points-pl-capacity-too-large.json][l-sp-pl] |
| 2026-10-05 | none | ServicePointLocator | the same piece with `locationTypes` `["locker"]` | HTTP 400, "The dimensions are too large for locationtype locker" | [lookup-service-points-pl-capacity-too-large.json][l-sp-pl] |
| 2026-10-06 | none | ServicePointLocator | Bahnhofstrasse 1, 8001 Zürich, one 2 kg piece | HTTP 400, "No matching servicepoint was found" | [lookup-service-points-ch-8001-none][l-sp-ch] |

The PL route answer matches the manual, which lists the route service only for domestic products (§10.14.1 p230).
`karrio.Address.validate` reported the 401 as `postal_code_api_unavailable` without validation details.

## Other lookups

| Date | Lookup | Input | Answer | Evidence |
|------|--------|-------|--------|----------|
| 2026-10-05 | PostalCode route | SE 11151 | `bookable` `true` and `homeDeliveryParcel` `true`, the route flag the manual ties to 118 (§10.14.7 p235) | [lookup-postal-code-se-11151-route.json][l-pc-11151] |
| 2026-10-05 | 118 `enforce` pre-flight | SE 11151, before booking 2906761255 | `homeDeliveryParcel` `true`, and the booking went ahead | [booking-2906761255][b-255] |
| 2026-10-08 | PostalCode route | SE 98138 Kiruna | `bookable` `true` and `homeDeliveryParcel` `false`, unscoped and scoped to 118 alike, so `karrio.Address.validate` reports success unscoped and failure scoped to 118 | [lookup-postal-code-se-98138-no-home-delivery.json][l-pc-98138] |
| 2026-10-08 | 118 `enforce` pre-flight | SE 98138 | only the route lookup, then `PostalCodeNotServableError` for `homeDeliveryParcel` `false`, with no TransportInstruction call | [98138 pre-flight][l-pf-98138] |
| 2026-10-08 | 118 `enforce` pre-flight | SE 99999 | only the route lookup, then `PostalCodeNotServableError` for 16010, with no TransportInstruction call | [99999 pre-flight][l-pf-99999] |
| 2026-10-08 | 118 `enforce` pre-flight | SE 11151 with the client key `not-a-real-key` | only the route lookup, which answered 401, then `PostalCodeApiUnavailableError`, with no TransportInstruction call | [401 pre-flight][l-pf-401] |
| 2026-10-05 | ServicePointLocator, ten points | Stockholm, one 2.5 kg piece of 40 × 30 × 15 cm and one 500 kg piece of 300 × 200 × 200 cm | the same ten service points in the same order for both pieces | [lookup-service-points-se-capacity-not-applied.json][l-sp-se] |
| 2026-10-05 | ServicePointLocator | Warszawa, one 2.5 kg piece | points, with `id` 101 and `servicePointId` 8005-PL-4516440 for one of them | [lookup-service-points-pl-capacity-too-large.json][l-sp-pl] |
| 2026-10-05 | ServicePointLocator, five points | SE 11151, before booking 2906761230 | `id` and `servicePointId` both SE-982000 | [booking-2906761230][b-230] |
| 2026-10-05 | ServicePointLocator | București, before booking 2906761263 | `id` 231652 and `servicePointId` 8023-231652 | [booking-2906761263][b-263] |
| 2026-10-05 | ServicePointLocator | Budapest 1052, before booking 2906761289 | the locker 8013-118530, whose entry lists only the service type `parcel:pick-up-unregistered` | [booking-2906761289][b-289] |
| 2026-10-06 | ServicePointLocator, five points | Mariehamn 22100, before booking 2906761917 | five Posti points in Åland of type `postoffice`, with ids 8011-221003201 to 8011-224103201 | [booking-2906761917][b-917] |

Every pre-flight above ran with the connection setting `address_validation` `enforce`.

## Product matches

Every product matches call answered HTTP 200 without an error message, each with one piece, from SE 11143, and with the recipient country code and postal code as given.

| Lane | Piece | Products matched | Date | Evidence |
|------|-------|------------------|------|----------|
| SE → SE 41101 | 2.5 kg, 40 × 30 × 15 cm | 502, 118, 104, 102, 402, 211, 401, 103 | 2026-10-05 | [se-se][l-pm-se] |
| SE → PL 00-251 | 2.5 kg, 40 × 30 × 15 cm | HDI, 109, 202, 112, 601, 233 | 2026-10-05 | [se-pl][l-pm-pl] |
| SE → GB W1D 1AN | 1 kg, 30 × 20 × 10 cm | HDI, 202, 601, 233 | 2026-10-06 | [se-gb][l-pm-gb] |
| SE → FI 00100, mainland Finland (control) | 2.5 kg, 40 × 30 × 15 cm | HDI, 109, 202, 112, 601, 233 | 2026-10-06 | [se-fi-00100][l-t-fi-00100] |
| SE → FI 22100, Åland under FI | 2.5 kg, 40 × 30 × 15 cm | HDI, 109, 202, 112, 601, 233 | 2026-10-06 | [se-fi-22100][l-t-fi-22100] |
| SE → AX 22100, Åland under AX | 2.5 kg, 40 × 30 × 15 cm | none | 2026-10-06 | [se-ax-22100][l-t-ax] |
| SE → GB W1D 1AN, London (control) | 2.5 kg, 40 × 30 × 15 cm | HDI, 202, 601, 233 | 2026-10-06 | [se-gb-w1d1an][l-t-gb-w1d] |
| SE → GB BT1 1AA, Northern Ireland under GB | 2.5 kg, 40 × 30 × 15 cm | HDI, 202, 601, 233 | 2026-10-06 | [se-gb-bt11aa][l-t-gb-bt] |
| SE → GB IM1 1AA, Isle of Man under GB | 2.5 kg, 40 × 30 × 15 cm | HDI, 202, 601, 233 | 2026-10-06 | [se-gb-im11aa][l-t-gb-im] |
| SE → GB JE2 3AB, Jersey under GB | 2.5 kg, 40 × 30 × 15 cm | HDI, 233 | 2026-10-06 | [se-gb-je23ab][l-t-gb-je] |
| SE → GB GY1 1AA, Guernsey under GB | 2.5 kg, 40 × 30 × 15 cm | HDI, 233 | 2026-10-06 | [se-gb-gy11aa][l-t-gb-gy] |
| SE → JE JE2 3AB, Jersey under JE | 2.5 kg, 40 × 30 × 15 cm | none | 2026-10-06 | [se-je-je23ab][l-t-je] |
| SE → GG GY1 1AA, Guernsey under GG | 2.5 kg, 40 × 30 × 15 cm | none | 2026-10-06 | [se-gg-gy11aa][l-t-gg] |
| SE → DK 3900, Greenland under DK | 2.5 kg, 40 × 30 × 15 cm | HDI, 109 | 2026-10-06 | [se-dk-3900][l-t-dk] |
| SE → FO 100, Faroe Islands under FO | 2.5 kg, 40 × 30 × 15 cm | none | 2026-10-06 | [se-fo-100][l-t-fo] |
| SE → ES 35001, Canary Islands under ES | 2.5 kg, 40 × 30 × 15 cm | HDI | 2026-10-06 | [se-es-35001][l-t-es] |
| SE → DK 1620 | 1 kg, 30 × 20 × 10 cm | HDI, 109, 202, 112, 601, 233 | 2026-10-06 | [se-dk-1620][l-pm-205-dk] |
| SE → NO 0154 | 1 kg, 30 × 20 × 10 cm | HDI, 109, 202, 112, 601, 233 | 2026-10-06 | [se-no-0154][l-pm-205-no], [with customs services][l-no-0154-customs] |
| SE → CH 8001, Zürich | 2 kg, 30 × 20 × 15 cm | HDI, 202, 601, 233 | 2026-10-06 | [se-ch-8001][l-ch-8001] |
| SE → CH 8001, Zürich | 20 kg, 30 × 20 × 15 cm | HDI, 202, 601, 233 | 2026-10-06 | [se-ch-8001-20kg][l-ch-8001-20kg] |
| SE → CH 1201, Geneva | 2 kg, 30 × 20 × 15 cm | HDI, 202, 601, 233 | 2026-10-06 | [se-ch-1201][l-ch-1201] |
| SE → CH 3011, Bern | 2 kg, 30 × 20 × 15 cm | HDI, 202, 601, 233 | 2026-10-06 | [se-ch-3011][l-ch-3011] |
| SE → CH 6900, Lugano | 2 kg, 30 × 20 × 15 cm | HDI, 202, 601, 233 | 2026-10-06 | [se-ch-6900][l-ch-6900] |
| SE → LI 9490, Vaduz | 2 kg, 30 × 20 × 15 cm | 202 | 2026-10-06 | [se-li-9490][l-li-9490] |
| SE → HU 1052 | 1 kg, 30 × 20 × 10 cm | HDI, 109, 202, 112, 601, 233 | 2026-10-08 | [se-hu-1052][l-pm-hu] |
| SE → RO 030031 | 1 kg, 30 × 20 × 10 cm | HDI, 109, 202, 112, 601, 233 | 2026-10-08 | [se-ro-030031][l-pm-ro] |

No lane matched 205 or SPI, so the booking-export 205 cases to DK 1620 and NO 0154 skip, and the EKAER and UIT entries could not be tried on 205 or SPI to HU or RO.
No GB postal code matched 109 or 112, so the booking-export 112 GB case skipped until it was sent without the check (see [Rejections](#rejections)).
The territory codes AX, JE, GG, and FO matched no product, while the same postal codes under FI and GB did, and FI 22100 matched like mainland Finland, offering 109 and 112 to Åland.
No CH lane matched 109, 112, or 107, and the manual lists CH, but not LI, among the valid countries of 601 (§5.19 p82).
Every product matched to CH marks its CH entry `customs` `true` with no `postalCodeExcludes`, and DDP is the only payer code each of them flags `customs` `true`.
Every lane that matched 601 also matched HDI, which the manual names as the invoice-file code for 601 (§5.19 p81).

### Catalog postal-code excludes

The territory evidence files keep each matched product's `toCountries` entries with a `postalCodeExcludes` value and the entry of the recipient country.
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

## Deviations from manual v5.26

Where the sandbox contradicts the manual the connector follows the sandbox, and where the sandbox has no evidence it follows the manual.
Rows whose topic a published page covers point to that page; the bookings, rejections, and lookups above hold the full evidence.

| Topic | Manual v5.26 says | Sandbox did | Connector follows | Published page |
|-------|-------------------|-------------|-------------------|----------------|
| Payer codes for 109 and 112 | 022 and 023 for 109 (§5.14 p63), 023 only for 112 (§5.3 p19) | accepted 112 with 022 ([2906761149][b-149]) and 023 ([2906761131][b-131]) and rejected payer code 1 with 22020 ([rejection-22020][r-22020]); the Product API catalog lists CPT, 022, DPU, DAP, 023, CIP, and DDP for both products, with `customs` `true` only for DDP ([lookup-products-109-112-payer-codes.json][l-products]); no booking used an Incoterm as the payer code for 109 or 112 | the sandbox: 022 and 023 for 112 | [booking-rules.md#payer-codes](../../concepts/booking-rules.md#payer-codes) |
| SENT for PL | `SENT_FREE` mandatory to or from PL in the related-fields tables of 202 (§5.4 p23), 205 (§5.9 p42), 233 (§5.10 p47), SPI (§5.11 p52), and 601 (§5.19 p82), with `SENT_REF` and `SENT_CARKEY` when not free, as in its API example; no SENT in the sections of 109 (§5.14 pp62-64) or 112 (§5.3 pp17-20) | applied the rule to 109 on 2026-10-05 ([rejection-22001][r-22001]) and accepted the same request on 2026-10-08 ([2906769613][b-613]), so whether the change is lasting is unknown; accepted `SENT_FREE` at shipment level ([2906761123][b-123], [2906761131][b-131]), although the vendored transport-instruction spec 2.10.0 (`vendor/se-api-farm/transport-instruction-2.10.0.json`) defines an `AdditionalInformation` schema that no other schema references; accepted placeholder identifiers not issued by the Polish SENT system ([2906769654][b-654]) | sends `SENT_FREE` `"true"` when no SENT option is given | [booking-rules.md#sent](../../concepts/booking-rules.md#sent) |
| EKAER and UIT for HU and RO | entries in the related-fields tables of 202 (§5.4 p23), 205 (§5.9 p42), 233 (§5.10 p47), SPI (§5.11 p52), and 601 (§5.19 p82), not for 109 or 112; the UIT code for a shipment that is not UIT free is conditional, "Code should be provided if possible" (§5.19 p82), as `1234-5678-9012-3456` in its example | accepted 109 and 112 without entries, as the manual has it ([2906761263][b-263], [2906761271][b-271], [2906761289][b-289], [2906761297][b-297]); accepted 601 with `UIT_FREE` `"false"` without a number ([2906761347][b-347]) and the made-up EKAER number and the placeholder UIT number ([2906761339][b-339], [2906769662][b-662]), so it did not check them at booking | `"true"` free flags by default below 500 kg | [booking-rules.md#ekaer-and-uit](../../concepts/booking-rules.md#ekaer-and-uit) |
| Excluded areas for 109 and 112 | see [Catalog postal-code excludes](#catalog-postal-code-excludes) | product matches offered 109 to DK 3900, which the manual excludes ([se-dk-3900][l-t-dk]); no booking tested it | the manual's excludes for 109 and 112, the catalog's for 202, 233, and 601 | [destinations.md#excluded-postal-codes](../../concepts/destinations.md#excluded-postal-codes) |
| Customs to Åland | Customs handling - Standard valid to "NO and Åland Islands (FI 22)" (§6.6 p94); Åland (FI 22) is outside the tax area and customs proceedings are mandatory (§7.4 p162) | rejected full service and Standard with 24003 ([full service][r-24003-ax], [Standard][r-24003-ax-std]), and booked 109 without customs data ([2906761917][b-917]) and with customs data and no customs service ([2906762592][b-592]) | the sandbox: refuses both customs handling services to or from FI 22000-22999, and the two 112 Åland suite cases assert that refusal; also refuses any booking crossing the EU VAT area border without customs data, so the 109 Åland case without customs data asserts that refusal | [destinations.md#åland](../../concepts/destinations.md#åland) |
| Service point capacity filter | no manual citation recorded | applied the piece filter for PL but not for SE ([SE][l-sp-se], [PL][l-sp-pl]) | sends the caller's parcel as the `piece` filter | [lookups.md#service-points](../../guides/lookups.md#service-points) |
| Service point id for 103 | use only the four-digit part nnnn of an id like SE-nnnn00 (§10.14.2.1 p231) | booking 2906761230 used the full id SE-982000 ([2906761230][b-230]) and booking 2906771650 used the four-digit terminal id 9820 ([2906771650][b-650]); the lookup's `id` and `servicePointId` are equal in SE and differ elsewhere | the manual since 2026-10-09: sends the four-digit terminal id nnnn and refuses other 103 ids | [booking-rules.md#access-points](../../concepts/booking-rules.md#access-points) |
| AccessPoint sub type | Appendix M: the sub type carries the location type `servicepoint`, `locker`, or `postoffice` (§10.14.2.2 p232), while the vendored spec enumerates `ParcelShop` and `ParcelStation` | accepted `ParcelShop` for PL, RO, NO, and DK ([2906761123][b-123], [2906761263][b-263], [2906761305][b-305], [2906761354][b-354]) and `ParcelStation` for a HU locker ([2906761289][b-289]); their routing codes carry 53 and 54 respectively (for example 2LPL30079+70530000 and 2LHU1826+70540000), which matches the routing code column of the table on p232 | `ParcelShop` and `ParcelStation` | [booking-rules.md#access-points](../../concepts/booking-rules.md#access-points) |
| Service type for 109 | only shops and stations with service type `parcel:pick-up` can be selected for 109 (§10.14.2.2 p232) | accepted the HU locker 8013-118530, whose lookup entry lists only `parcel:pick-up-unregistered` ([2906761289][b-289]) | no service type check | [booking-rules.md#access-points](../../concepts/booking-rules.md#access-points) |
| Lookup size for 103 | always search the ten closest service points (§5.12 p57) | the suite's 103 booking searched five ([2906761230][b-230]); the lookup segment's capacity check searched ten ([SE][l-sp-se]) | the caller's `max_items` | none |
| Customs to NO | Customs handling - Full service: a commercial invoice must be sent to DHL and routing barcode 001 is on the label (§6.5 p92); for 109 two copies of the customs documents on the outside of the package (§5.14 p62); NO is valid for Customs handling - Standard (§6.6 p94) | accepted full service with a `ProformaInvoice` without an invoice amount or EORI for 109, 112, 202, 233, and 601 ([2906761305][b-305], [2906761313][b-313], [2906762139][b-139], [2906762154][b-154], [2906762162][b-162]) and Standard with a `ProformaInvoice` and the made-up EORI SE0000000000 for 109 and 112 ([2906762105][b-105], [2906762113][b-113]); routing codes 2LNO0186+70530001 (109, both services), 2LNO0154+11000001 (202), and 2LNO0154+00000001 (233 and 601) end in 001, while 112 returned 2LNO0154+000000 for both services | requires a `CommercialInvoice` for sales outside the EU VAT area, its own rule | [README.md#commercial-or-proforma-invoice](../../../README.md#commercial-or-proforma-invoice) |
| Joint declaration to CH | Customs, joint declaration lists NO as its only valid country and needs a separate agreement (§6.8 p98) | product matches list `customsJointDeclaration` among 601's customs services on all five CH lookups ([8001][l-ch-8001], [8001 20 kg][l-ch-8001-20kg], [1201][l-ch-1201], [3011][l-ch-3011], [6900][l-ch-6900]) and for 601, 109, and 112 to NO 0154 ([se-no-0154-customs][l-no-0154-customs]); 601, 202, 233, and HDI list the same customs services to NO 0154 as to CH, which suggests the lists do not vary by destination; no booking sent the service | the sandbox: the README names NO and CH, and the connector refuses the service to other recipient countries before booking | [README.md#customs-services](../../../README.md#customs-services) |
| Routing code reference | send the label's routing code as a reference in the IFTMIN shipment instruction for 112 (§5.3 p18) and 109 (§5.14 p62) | the API bookings sent no routing code, and every response returned `routingCode` (for example [2906761131][b-131] and [2906761123][b-123]) | sends no routing code | none |
| Phone numbers on labels | the receiving parcelshop's phone is mandatory on the 103 label (§9.4.2 p170) | the 103 label prints a `Phn.` line with no number ([label-2906761230][lb-230]); the other labels match (see [Labels](#labels)) | transmits the consignee phone on every booking | [labels.md#phone-numbers](../../concepts/labels.md#phone-numbers) |

## Pending verification

In the same 2026-10-09 review DHL said that 109 takes "the short customer ID, e.g. "id": "103"".
Whether that refers to the Consignor customer number or to the AccessPoint id is unresolved and awaits an answer from DHL, and the connector's 109 bookings are unchanged.

The answer to a valid client key whose DHL application lacks the PostalCode API is not captured; the connector treats 401 and 403 alike, on the strength of the 401 the sandbox gives an unknown key ([lookup-postal-code-se-11151-401-unknown-client-key.json][l-pc-401]).

## Coverage

The matrix gives each product's sandbox result per lane class, where not offered means product manual v5.26 offers the product on no lane of that class.
The connector rates and books a product only on the lanes the manual offers ([products.md#lanes](../../concepts/products.md#lanes)).
Every cell's evidence is in the tables above.

| Product | Domestic SE | Intra-EU | Outside the EU VAT area and special territories |
|---------|-------------|----------|-------------------------------------------------|
| 102 | booked | not offered | not offered |
| 103 | booked; rejected with an id-only AccessPoint | not offered | not offered |
| 104 | untested, matched to SE 41101 | not offered | not offered |
| 107 | not offered | untested; returns from the EU countries the manual lists to SE | untested; returns from NO to SE |
| 109 | not offered | booked to PL, RO, HU, and DK; rejected and later booked to PL without SENT entries | booked to NO and FI 22100 |
| 112 | not offered | booked to PL, RO, HU, and FR; rejected to PL with an AccessPoint and with payer code 1 | booked to NO; rejected to GB and FI 22100 |
| 118 | booked | not offered | not offered |
| 202 | not offered | booked to DK, HU, and RO | booked to NO and GB BT1 1AA |
| 205 | not offered | untested, not matched to DK 1620, HU 1052, or RO 030031 | rejected to NO below the chargeable-weight minimum |
| 209, 210, 212 | untested | not offered | not offered |
| 211 | untested, matched to SE 41101 | not offered | not offered |
| 233 | not offered | booked to DK, HU, and RO | booked to NO |
| 401 | booked | not offered | not offered |
| 402, 502 | untested, matched to SE 41101 | not offered | not offered |
| 601 | not offered | booked to DK, HU, PL, and RO | booked to NO and CH |
| SPI | not offered | untested, not matched to HU 1052 or RO 030031 | untested |

Availability follows the valid countries of each product section of manual v5.26: SE only for 102 (§5.2 p15), 209 (§5.5 p27), 210 (§5.6 p30), 211 (§5.7 p34), 212 (§5.8 p38), 103 (§5.12 p56), 104 (§5.13 p59), 118 (§5.16 p68), 401 (§5.17 p72), and 402 and 502 (§5.18 p76); the EU countries other than SE, CY, GR, and MT, with NO and GB, for 112 (§5.3 p18) and 109 (§5.14 p63); the same countries without GB for 107, a return sent from those countries to the original sender in SE (§5.15 pp65-66); and EU and non-EU countries including SE, for traffic to and from Sweden, for 202 (§5.4 p23), 205 (§5.9 p43), 233 (§5.10 p47), SPI (§5.11 p52), and 601 (§5.19 p82), which the products overview lists as international (§5.1 p13).

These were never exercised:

- the PickupRequest, TimeTable, PriceQuote, and HomeDeliveryLocator APIs, and the Print API for anything but labels
- any additional service other than `customsHandlingFullService` and `customsHandlingStandard`
- the customer's own declaration, the joint declaration (including 109 with payer code 023), and VOEC
- customs to destinations outside the EU VAT area other than NO, CH, and FI 22100, and customs data without a customs service anywhere but FI 22100
- payer codes 3 and 4 with a freight payer party, and 601 with any payer code but DAP
- 205 at or above its 2500.0 chargeable-weight minimum
- 601, 202, or 233 to HU or RO without EKAER or UIT entries, which the connector never sends, and 202 and 233 there with anything but the default `"true"` free flags
- EKAER and UIT entries on 205 or SPI
- whether DHL production checks SENT, EKAER, and UIT identifiers, which the sandbox accepted as placeholders; the connector checks only their length and combination and passes them through
- 109 with home addressing and no AccessPoint party
- 109 to GB, which the manual lists for 109 and 112 only according to a separate agreement (§5.3 p18, §5.14 p63, Appendix G p200)
- any booking to LI or GR, and any 107 booking with `qrCode`
- multi-piece shipments, and pieces below the minimum dimensions the manual states for 102 (§5.2 p14) and 112 (§5.3 p17)

[b-073]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761073-109-se-pl.json
[b-081]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761081-112-se-pl.json
[b-123]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761123-109-se-pl.json
[b-131]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761131-112-se-pl.json
[b-149]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761149-112-se-pl-payer-022.json
[b-222]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761222-102-se-se.json
[b-230]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761230-103-se-se.json
[b-650]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906771650-103-se-se-terminal-id.json
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
[b-105]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762105-109-se-no-standard-customs.json
[b-113]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762113-112-se-no-standard-customs.json
[b-121]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762121-202-se-dk.json
[b-139]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762139-202-se-no.json
[b-147]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762147-233-se-dk.json
[b-154]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762154-233-se-no.json
[b-162]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762162-601-se-no.json
[b-477]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762477-601-se-ch.json
[b-592]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762592-109-se-fi-aland-customs.json
[b-555]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769555-601-se-hu-default-ekaer-free.json
[b-563]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769563-601-se-ro-default-uit-free.json
[b-613]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769613-109-se-pl-without-sent.json
[b-647]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769647-601-se-pl-default-sent-free.json
[b-654]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769654-601-se-pl-sent-identifiers.json
[b-662]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769662-601-se-ro-uit-number.json
[b-969]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769969-202-se-hu-default-ekaer-free.json
[b-977]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769977-202-se-ro-default-uit-free.json
[b-985]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769985-233-se-hu-default-ekaer-free.json
[b-993]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769993-233-se-ro-default-uit-free.json
[b-303]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762303-401-se-se.json
[r-22001]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22001-109-se-pl-without-sent.json
[r-22001-103]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22001-103-se-access-point-id-only.json
[r-22005-gb]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22005-112-se-gb.json
[r-22015]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22015-112-se-pl-access-point.json
[r-24003-ax]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland.json
[r-24003-ax-std]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland-standard.json
[r-22020]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22020-112-se-pl-payer-code-1.json
[r-22020-205-no]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22020-205-se-no.json
[l-pc-99999]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-99999-16010.json
[l-pc-11151]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-11151-route.json
[l-pc-98138]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-98138-no-home-delivery.json
[l-pc-98060]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-98060-16012.json
[l-pc-84094]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-84094-16011.json
[l-pf-98138]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-98138-118-enforce-preflight.json
[l-pf-99999]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-99999-118-enforce-preflight.json
[l-pc-401]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-11151-401-unknown-client-key.json
[l-pf-401]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-11151-118-enforce-preflight-401.json
[l-pc-pl]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-pl-route-16009.json
[l-pc-ch]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-ch-8001-16009.json
[l-sp-ch]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-ch-8001-none.json
[l-no-0154-customs]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-no-0154-customs.json
[l-ch-8001]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-8001.json
[l-ch-8001-20kg]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-8001-20kg.json
[l-ch-1201]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-1201.json
[l-ch-3011]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-3011.json
[l-ch-6900]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-6900.json
[l-li-9490]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-li-9490.json
[l-sp-se]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-se-capacity-not-applied.json
[l-sp-pl]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-pl-capacity-too-large.json
[l-pm-gb]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb.json
[l-pm-205-dk]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-dk-1620.json
[l-pm-205-no]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-no-0154.json
[l-pm-hu]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-hu-1052.json
[l-pm-ro]: ../../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ro-030031.json
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
