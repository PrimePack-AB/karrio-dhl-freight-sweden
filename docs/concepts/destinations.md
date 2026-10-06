---
title: "Destinations: the EU VAT area, special territories, and excluded postal codes"
---

These rules decide whether a booking carries customs information, which country code DHL receives, and which products a postal code can use.
Manual references are to product manual v5.26 (sha256 `050660c37ba93d1ae9514c50dfa42c2010bc87763ccaff51a740b2526af11b73`), written `§x.y pN`.

## The EU VAT area

The connector sends customs information and the requested customs services only when the shipper or the recipient lies outside the EU VAT area for goods; within it, customs data and customs services are dropped with a `customs_omitted_intra_eu` warning.
Outside the area a booking without customs data fails before the booking request, as the README's exporting section explains.
To or from Åland the customs handling services Standard and full service fail before the booking request, because DHL rejected both with 24003 (see [Special territories](#special-territories)).
The manual makes customs proceedings mandatory for deliveries outside the European Union or the tax area and names Åland (FI 22) and the Canary Islands as areas outside the tax area (§7.4 p162).
An address lies inside the area when its country is an EU member state, GR, or MC, its postal code is not in one of the ranges below, and, for DK, the code is neither led by FO or GL nor a three-digit Faroese code, or when it is a GB postcode starting with `BT` (Northern Ireland), which is inside the area for goods.

| Country | Postal codes | Territory |
|---------|--------------|-----------|
| FI | 22000-22999 | Åland |
| ES | 35000-35999, 38000-38999 | Canary Islands |
| ES | 51000-51999, 52000-52999 | Ceuta, Melilla |
| DE | 78266, 27498 | Büsingen, Heligoland |
| GR, EL | 63086 | Mount Athos |
| IT | 23041, 22061 | Livigno, Campione d'Italia |
| FR | 97000-97999 | French overseas departments and collectivities |
| DK | 3800-3999 | Faroe Islands and Greenland |
| FR | 98600-98899 | Wallis and Futuna, French Polynesia, New Caledonia |

Postal codes are compared upper-cased and trimmed, without a leading prefix code, and without spaces.
The prefix codes are the address's own country code and, under FI, DK, and ES, the codes of their territories with numeric postal codes, AX, FO, GL, IC, and EA; one is removed when a hyphen, whitespace, or, except for GB, a digit follows it, so `FI-22100`, `FI 22 100`, `FI22100`, and `AX-22100` read as `22100` under FI.
`JE`, `GY`, `IM`, and `BT` begin United Kingdom postcodes and are never removed.
The excluded postal codes below are normalised the same way, and the code sent to DHL is not changed.
The rule and the tables match the nordic_conventions plugin's territories module; a test in that repository checks the parity.

## Special territories

Product matches answered no product for the territory codes AX, JE, GG, and FO, while the same postal codes under FI and GB matched products (2026-10-06: [AX 22100](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ax-22100.json), [FI 22100](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-fi-22100.json), [JE JE2 3AB](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-je-je23ab.json), [GB JE2 3AB](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb-je23ab.json), [GG GY1 1AA](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gg-gy11aa.json), [FO 100](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-fo-100.json)).
The connector therefore rates, books, and looks up product matches and service points for an address with a territory code under its parent country, sending the parent country code with the postal code as given, before the customs area and excluded postal code checks.

| Territory | Code | Sent as | Customs | Product matches (2026-10-06) | Excluded from |
|-----------|------|---------|---------|------------------------------|---------------|
| Åland | AX | FI | yes, FI 22000-22999 | FI 22100: HDI, 109, 202, 112, 601, 233 ([evidence](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-fi-22100.json)); AX 22100: none | none |
| Jersey | JE | GB | yes | GB JE2 3AB: HDI, 233 ([evidence](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb-je23ab.json)); JE JE2 3AB: none | 109, 112, 202, 601 |
| Guernsey | GG | GB | yes | GB GY1 1AA: HDI, 233 ([evidence](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb-gy11aa.json)); GG GY1 1AA: none | 109, 112, 202, 601 |
| Isle of Man | IM | GB | yes | GB IM1 1AA: HDI, 202, 601, 233 ([evidence](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb-im11aa.json)) | none |
| Northern Ireland | XI | GB | no, GB `BT` postcodes are inside for goods | GB BT1 1AA: HDI, 202, 601, 233 ([evidence](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb-bt11aa.json)) | 109, 112 |
| Faroe Islands | FO | DK | yes, three-digit codes and codes led by FO | FO 100: none ([evidence](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-fo-100.json)) | 109, 112, 202, 233, 601 |
| Greenland | GL | DK | yes, DK 3800-3999 | DK 3900: HDI, 109 ([evidence](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-dk-3900.json)) | 109, 112, 202, 233, 601 |
| Canary Islands | IC | ES | yes, ES 35000-35999, 38000-38999 | ES 35001: HDI ([evidence](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-es-35001.json)) | 109, 112, 202, 233, 601 |
| Ceuta, Melilla | EA | ES | yes, ES 51000-52999 | not probed | 202, 233, 601; 51080 and 52080 from 109 and 112 |

The Customs column applies the [EU VAT area](#the-eu-vat-area) check to the parent country and postal code, and the Excluded from column applies the [excluded postal codes](#excluded-postal-codes) after the mapping; the Faroe Islands' three-digit codes fall under the DK 3800-3999 entry for 109 and 112 and under the catalog's `???` for the others.
The sandbox booked 109 from SE to FI 22100 (Åland) to the Posti ParcelShop 8011-221003201 with payer code 022 and no customs data (2026-10-06: [booking-2906761917-109-se-fi-aland.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761917-109-se-fi-aland.json)), and 202 from SE to GB BT1 1AA (Northern Ireland) with payer code DAP and no customs data (2026-10-06: [booking-2906761925-202-se-gb-northern-ireland.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761925-202-se-gb-northern-ireland.json)).
It rejected 112 from SE to FI 22100 with customs information and `customsHandlingFullService` with 24003 "customsHandlingFullService is not available for this country combination", after product matches had offered 112 for the lane (2026-10-06: [rejection-24003-112-se-fi-aland.json](../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland.json)).
It rejected 112 to FI 22100 with `customsHandlingStandard` and an EORI number the same way, 24003 "customsHandlingStandard is not available for this country combination" (2026-10-06: [rejection-24003-112-se-fi-aland-standard.json](../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland-standard.json)), although the manual lists "NO and Åland Islands (FI 22)" as the valid countries of Customs handling - Standard (§6.6 p94).
The connector therefore refuses `dhl_freight_sweden_customs_handling_standard` and `dhl_freight_sweden_customs_handling_full_service` before the booking request when the shipper or the recipient lies in FI 22000-22999, also under AX or written `FI-22100` or `AX-22100`, with a `SHIPPING_SDK_FIELD_ERROR` keyed by the option.
Because the manual treats Åland as outside the tax area (§7.4 p162), a booking to or from Åland needs customs data like any lane crossing the EU VAT area border, and the connector now refuses the customs-free 109 booking that the sandbox accepted.
The one remaining way to book Åland sends the customs information without either customs handling service.
The sandbox accepted such a booking, 109 from SE to FI 22100 to the same ParcelShop with payer code 022, a `CommercialInvoice` of 200 SEK, and one commodity, as 2906762592 with routing code 2LFI22100+70530000, echoed the customs document and commodity, and printed one PDF label (2026-10-06: [booking-2906762592-109-se-fi-aland-customs.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762592-109-se-fi-aland-customs.json)).
The evidence shows that DHL stored the customs information, not how DHL clears customs for Åland after booking.
Rating is unchanged.
202 to GB JE2 3AB was not sent: the connector refuses it before the booking request under the catalog's `JE*` exclude, and product matches did not offer 202 for that postcode ([lookup-product-matches-se-gb-je23ab.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb-je23ab.json)).
The Caribbean Netherlands codes BQ, CW, AW, and SX are sent as given, excluded from 109, 112, and 107, and passed through on the other products.

## Excluded postal codes

The "Excluded regions/areas" of the manual's product sections list postal codes the product does not serve.
The connector checks them before the booking request and in rating, where an excluded product is not offered and an explicitly requested one adds a `destination_not_supported` message instead of a rate.
A booking fails with `details` keyed by `recipient.postal_code` or `shipper.postal_code`.

| Product | Country | Excluded postal codes | Region | Manual |
|---------|---------|-----------------------|--------|--------|
| 112 | DK | 3800-3999 | Greenland and the Faroe Islands | §5.3 p18 |
| 112 | ES | 35000-35999, 38000-38999, 51080, 52080 | Canary Islands, Ceuta, Melilla | §5.3 p18 |
| 112 | FR | 97100-99999 | outside mainland France and Corsica | §5.3 p18 |
| 112 | IT | 04020, 04027, 22061, 23030, 23041, 25080, 28838, 47890-47899, 58012 | Ventotene, Ponza, Campione d'Italia, Trepalle, Livigno, Serle, Isola Bella, San Marino, Giglio | §5.3 p18 |
| 112 | NO | 8099, 9170-9179 | Jan Mayen and Svalbard | §5.3 p18 |
| 112 | PT | 9000-9999 (first four digits) | the Azores, Madeira, and other islands | §5.3 p18 |
| 109 | DK | 3800-3999 | Greenland and the Faroe Islands | §5.14 p63 |
| 109 | ES | 35000-35999, 38000-38999, 51080, 52080 | Canary Islands, Ceuta, Melilla | §5.14 p63 |
| 109 | FR | 97100-99999 | outside mainland France and Corsica | §5.14 p63 |
| 109 | IT | 00120, 22061, 23041, 47890-47899 | Vatican, Campione d'Italia, Livigno-Trepalle, San Marino | §5.14 p63 |
| 109 | NO | 8099, 9170-9179 | Jan Mayen and Svalbard | §5.14 p63 |
| 109 | PT | 9000-9999 (first four digits) | the Azores, Madeira, and other islands | §5.14 p63 |
| 107 (shipper) | DK | 3800-3999 | Greenland and the Faroe Islands | §5.15 p66 |
| 107 (shipper) | ES | 35000-35999, 38000-38999, 51080, 52080 | Canary Islands, Ceuta, Melilla | §5.15 p66 |
| 107 (shipper) | IT | 00120, 22061, 23041, 47890-47899 | Vatican, Campione d'Italia, Livigno-Trepalle, San Marino | §5.15 p66 |
| 107 (shipper) | NO | 8099, 9170-9179 | Jan Mayen and Svalbard | §5.15 p66 |
| 107 (shipper) | PT | 9000-9999 (first four digits) | the Azores, Madeira, and other islands | §5.15 p66 |
| 202, 205, SPI (shipper and recipient) | UA | 95000-99999 | Crimea/Sebastopol region | §5.4 p23, §5.9 p43, §5.11 p52 |

Each country's codes are compared in its own format once [normalised](#the-eu-vat-area): four digits for DK and NO, five digits for ES, FR, IT, and UA (leading zeros kept, so `04020` and not `4020`), and `NNNN-NNN` for PT, whose ranges cover the first four digits and which is also accepted without the hyphen or as the four-digit prefix alone.
A code of another shape cannot be shown to lie outside the excluded ranges, so it counts as excluded in rating and booking.
The DK ranges of 112, 109, and 107, "Greenland & The Faroe Islands (3800-3999)", also exclude a code led by FO or GL and a three-digit Faroese code, which are reported as excluded rather than malformed.
A missing or blank code is not checked in rating, so the product is still offered, while booking rejects it with `details` keyed by the party's `postal_code`.
The ranges apply to the recipient, except for the UA range of 202, 205, and SPI, products used to and from SE, which applies to both parties, and for 107, a return sent from the listed countries to the original sender, whose ranges apply to the shipper, as the manual's 107 entry for FR reads "Delivery only from France mainland and Corsica" (§5.15 p66).
The manual's areas without postal-code ranges are checked as patterns, `*` standing for any characters and `?` for one, matched against the whole normalised code.
For 202, 233, and 601, for which the manual lists no excluded areas other than 202's UA range, the connector applies the Product API catalog's `postalCodeExcludes`, quoted verbatim from the product matches answers of 2026-10-06 ([lookup-product-matches-se-fi-00100.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-fi-00100.json)).

| Product | Country | Excluded patterns | Region | Source |
|---------|---------|-------------------|--------|--------|
| 112, 109 | GB | `JE*`, `GY*`, `BT*` | Jersey, Guernsey, Northern Ireland | §5.3 p18, §5.14 p63 |
| 112, 109 | AW, BQ, CW, SX | `*` | Aruba, Bonaire, Curaçao, Saba, Sint Maarten, Sint Eustatius | §5.3 p18, §5.14 p63 |
| 107 (shipper) | AW, BQ, CW, SX | `*` | Aruba, Bonaire, Curaçao, Saba, Sint Maarten, Sint Eustatius | §5.15 p66 |
| 202, 233, 601 | DK | `39*`, `???`, `2412` | catalog | catalog |
| 202, 233, 601 | ES | `35*`, `38*`, `51*`, `52*` | catalog | catalog |
| 202, 601 | FR | `97*` | catalog | catalog |
| 202, 601 | GB | `GY*`, `JE*` | catalog | catalog |
| 202, 233, 601 | NO | `917*`, `8099` | catalog | catalog |
| 202, 233, 601 | PT | `9*` | catalog | catalog |

The manual names the NL Caribbean islands without postal codes, so they are excluded under their own country codes AW, BQ, CW, and SX, which are sent to DHL unchanged, whatever the postal code; an address on the islands under NL is not recognised.
A pattern list excludes a matching code; a missing code that no pattern matches is not checked in rating and rejected at booking, like a missing code under a range.
601's DK list reads `2142` where the other products read `2412`, Christiansø; the connector treats it as a typo and excludes 2412 for 601 as well.
The catalog lists different excludes for 109 and 112, which the connector does not apply because the manual covers both products; the [findings note](../notes/sandbox/sandbox-findings.md#special-territories-in-product-matches) compares them, including 109 to DK 3900, which product matches offered while the manual excludes DK 3800-3999 ([lookup-product-matches-se-dk-3900.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-dk-3900.json)).
205 and SPI were not matched by any probe, so no catalog excludes are applied to them.
The manual's 107 entry for FR outside mainland France and Corsica gives no postal codes and is not checked (§5.15 p66).
The manual also points to the DHL Freight website for the present list of postal codes, which the connector does not consult.
