---
title: "Booking rules"
---

The connector checks these rules before it sends the booking request, and a violation fails with a `SHIPPING_SDK_FIELD_ERROR` whose `details` are keyed by the option or field to fix.
The README's errors reference lists every such error.
The rules follow the DHL Freight (Sweden) product manual, version 5.26, updated 2026-10-01 and valid from 2026-11-01, which is cited here rather than vendored.
DHL lists the current manual at <https://dhlpaket.se/dashboard/specifications/products/>, and the cited copy of version 5.26 has sha256 `050660c37ba93d1ae9514c50dfa42c2010bc87763ccaff51a740b2526af11b73`.
Section and page references below are to that version, written `§x.y pN`.
Customs rules are in the README's exporting section, and destination rules (the EU VAT area, special territories, and excluded postal codes) are in [Destinations](destinations.md).

## Payer codes

`payerCode` carries the product's terms-of-delivery code, validated against the product's "Payer codes" table.

| Product | Valid codes | Default | Manual |
|---------|-------------|---------|--------|
| 102, 210, 211, 212 | 1, 3, 4 | 1 | §5.2 p15, §5.6 p30, §5.7 p35, §5.8 p39 |
| 209 | 1, 3, 4, 8 (manual invoicing, separate agreement needed) | 1 | §5.5 p27 |
| 103, 118, 401 | 1, 4 | 1 | §5.12 p57, §5.16 p69, §5.17 p73 |
| 104 | 3 | 3 | §5.13 p60 |
| 402, 502 | 3, 4 | none | §5.18 p77 |
| 107 | 001 | 001 | §5.15 p66 |
| 109 | 022, 023 (023 only with customs joint declaration) | 022 | §5.14 p63 |
| 112 | 022, 023 | 023 | §5.3 p19 lists 023 only; 022 per the sandbox, see below |
| 202, 233, SPI, 601 | export EXW, FCA, CPT, CIP, DAP, DPU, DDP; import EXW, FCA | none | §5.4 p24, §5.10 p48, §5.11 p53, §5.19 p83 |
| 205 | export CPT, CIP, DAP, DPU, DDP; import EXW, FCA | none | §5.9 p43 |

A lane is an import when the recipient is in SE and the shipper is not; the import column applies only to the products that list one.
The code resolves in this order:

1. The `dhl_freight_sweden_payer_code` option, which must be a valid code.
2. `customs.incoterm` when it is a valid code. For 109 and 112, which accept only Combiterms, the Incoterm is translated per §7.6 p163 (CPT, CIP, DAP, DPU to 022; DDP to 023) and the result must be valid. For other products an Incoterm outside the product's codes is not used.
3. The product default from the table. A product without a default needs an explicit payer code.

Payer code 023 on 109 additionally requires the `dhl_freight_sweden_customs_joint_declaration` option.
The manual conflicts with itself here: the 109 section requires the joint declaration for 023 (§5.14 p63), while the joint declaration section says such bookings must not be sent for 109 and 112 (§6.8 p98).
The connector follows §5.14, and the question is open with DHL.
Product codes the connector does not define keep the previous fallback of option, then Incoterm, then `1`.

For 112 the sources disagree.
The DHL Product API catalog (`GET /productapi/v1/products/112`, test host, 2026-10-05: [lookup-products-109-112-payer-codes.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-products-109-112-payer-codes.json)) lists CPT, CIP, DAP, DPU, DDP, 022, and 023, while the manual (§5.3 p19) lists only 023.
The sandbox rejected payer code 1 for 112 (22020 "Payercode 1 is not valid for product": [rejection-22020-112-se-pl-payer-code-1.json](../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22020-112-se-pl-payer-code-1.json)) and accepted both 023 ([booking-2906761131-112-se-pl.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761131-112-se-pl.json)) and 022 (booking 2906761149: [booking-2906761149-112-se-pl-payer-022.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761149-112-se-pl-payer-022.json)), 2026-10-05.
The connector therefore accepts 022 and 023 for 112 and keeps the manual's 023 as the default; the catalog's Incoterm codes are untested and reach 112 only through the Combiterm translation.

## Access points

The `dhl_freight_sweden_service_point` options produce an AccessPoint party only where the manual lists an access-point delivery for the product and the recipient country.

| Product | Country | Sub types | Manual |
|---------|---------|-----------|--------|
| 103 | SE | ParcelShop, ParcelStation | §5.12 p55-56 |
| 109 | AT, BE, BG, CZ, DK, EE, FI, HU, IT, LT, LV, NL, PL, SK | ParcelShop, ParcelStation | Appendix C.3, §10.4.2 p192-194 |
| 109 | DE, ES, FR, GB, HR, NO, PT, RO, SI | ParcelShop | Appendix C.3, §10.4.2 p192-193 |

Every other product and country accepts no AccessPoint party, including 109 to IE and LU and all of 112 (§5.3 p19), for which DHL answers 22015 "AccessPoint Party is not allowed for this product" (sandbox, 2026-10-05: [rejection-22015-112-se-pl-access-point.json](../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22015-112-se-pl-access-point.json)).
A `dhl_freight_sweden_service_point` value that is a sub type or location type name (`ParcelShop`, `ParcelStation`, `servicepoint`, `locker`, `postoffice`, `postbank`, in any case) is rejected: the option takes the service point id, and the sub type goes in `dhl_freight_sweden_service_point_type`.

Appendix M (§10.14.2.2 p232) states that the AccessPoint `subtype` carries the location type (`servicepoint`, `locker`, `postoffice`), while the transport-instruction booking spec enumerates `ParcelShop` and `ParcelStation`.
The connector sends `ParcelShop` and `ParcelStation`.
The sandbox accepted 109 bookings with `ParcelShop` to PL, RO, NO, and DK and with `ParcelStation` to a HU locker (2026-10-05: [booking-2906761123-109-se-pl.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761123-109-se-pl.json), [booking-2906761263-109-se-ro.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761263-109-se-ro.json), [booking-2906761305-109-se-no.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761305-109-se-no.json), [booking-2906761354-109-se-dk.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761354-109-se-dk.json), [booking-2906761289-109-se-hu.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761289-109-se-hu.json)).

## SENT

Lanes with the shipper or the recipient in PL carry SENT entries under the shipment's `additionalInformation`.

| Option | Type | Sent as |
|--------|------|---------|
| `dhl_freight_sweden_sent_ref` | string, at most 20 characters | `SENT_REF` |
| `dhl_freight_sweden_sent_carkey` | string, at most 20 characters | `SENT_CARKEY` |
| `dhl_freight_sweden_sent_free` | boolean | `SENT_FREE` |

Both identifiers send `SENT_FREE` `"false"` followed by `SENT_REF` and `SENT_CARKEY`, as in the manual's API example (§5.4 p23); one identifier without the other fails, and `dhl_freight_sweden_sent_free` `true` together with either identifier fails as contradictory.
`dhl_freight_sweden_sent_free` `true` without identifiers sends `SENT_FREE` `"true"`, and `false` without identifiers fails.
A shipment with neither the free flag nor the identifiers sends `SENT_FREE` `"true"`, whatever its weight.
Like EKAER and UIT, SENT free is a legal declaration made on the shipper's or the consignee's behalf, and the connector makes it by default only because it suits typical e-commerce shipments.
DHL describes SENT from 17 March 2026 as covering B2B shipments of clothing (CN 61, 62, and 6309) over 10 kg gross per shipment and of footwear (CN 64) over 20 items, declared by the receiver in PL, and states "B2C = no SENT ever" ([DHL Global Forwarding Poland](https://www.dhl.com/pl-en/home/global-forwarding/latest-news-and-webinars/poland_sent_2026.html), [DHL Express Poland](https://dhlexpress.pl/en/sent-2/)).
Those sources do not cover the older SENT goods categories, such as fuels; a shipment of such goods, or a B2B shipment above those thresholds, needs `dhl_freight_sweden_sent_ref` and `dhl_freight_sweden_sent_carkey`, and identifying it is the consumer's responsibility.
The opt-in sandbox suite declares its 109 and 112 bookings to PL SENT free with `dhl_freight_sweden_sent_free`.
The related-fields tables of 202 (§5.4 p23), 205 (§5.9 p42), 233 (§5.10 p47), SPI (§5.11 p52), and 601 (§5.19 p82) make the question "Is shipment SENT free?" (`SENT_FREE`) mandatory for shipments to or from PL, and the SENT reference and carrier key mandatory when the answer is no; the sections of 109 and 112 do not mention SENT.
The sandbox rejected a 109 booking to PL without either identifier and without `SENT_FREE` `"true"` on 2026-10-05 (22001 "SENT_REF and SENT_CARKEY are mandatory unless SENT_FREE is true.", sandbox 2026-10-05: [rejection-22001-109-se-pl-without-sent.json](../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22001-109-se-pl-without-sent.json)).
It accepted the same request on 2026-10-08 as 2906769613 (sandbox 2026-10-08: [booking-2906769613-109-se-pl-without-sent.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769613-109-se-pl-without-sent.json)); whether that change is lasting is unknown, and the connector still sends `SENT_FREE` `"true"` when neither identifier is given.
The sandbox accepted 109 and 112 bookings to PL with `SENT_FREE` `"true"` at shipment level ([booking-2906761123-109-se-pl.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761123-109-se-pl.json), [booking-2906761131-112-se-pl.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761131-112-se-pl.json)).
The vendored transport-instruction spec 2.10.0 defines the `AdditionalInformation` schema but does not reference it from the shipment; the live API accepts it at shipment level.

## EKAER and UIT

Lanes with the shipper or the recipient in HU carry EKAER entries, and lanes with the shipper or the recipient in RO carry UIT entries, under the shipment's `additionalInformation`.
EKAER is the Hungarian electronic road trade and transport control system, governed by decree 13/2020 (XII.23.) PM.
UIT is the transport identification code of the Romanian RO e-Transport system, governed by OUG 41/2022, art. 8^1.

| Option | Type | Sent as |
|--------|------|---------|
| `dhl_freight_sweden_ekaer_free` | boolean | `EKAER_FREE` |
| `dhl_freight_sweden_ekaer_number` | string, at most 20 characters | `EKAER_NUMBER` |
| `dhl_freight_sweden_uit_free` | boolean | `UIT_FREE` |
| `dhl_freight_sweden_uit_number` | string, at most 19 characters, e.g. `1234-5678-9012-3456` | `UIT_NUMBER` |

The "Related fields" tables of products 202 (§5.4 p23), 205 (§5.9 p42), 233 (§5.10 p47), SPI (§5.11 p52), and 601 (§5.19 p82) list these entries for shipments to or from HU and RO.
A free flag `true` sends `EKAER_FREE` or `UIT_FREE` `"true"`.
A number sends the free code `"false"` followed by `EKAER_NUMBER` or `UIT_NUMBER`.
A free flag `true` together with a number fails as contradictory, and a number over its length limit fails.
`dhl_freight_sweden_ekaer_free` `false` without a number fails, because the manual marks the EKAER number mandatory for a shipment that is not EKAER free.
The sandbox accepted 601 to HU with `EKAER_FREE` `"false"` and the made-up `EKAER_NUMBER` `E0000SANDBOX0001` (2026-10-05: [booking-2906761339-601-se-hu.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761339-601-se-hu.json)).
`dhl_freight_sweden_uit_free` `false` without a number sends `UIT_FREE` `"false"` alone, because the same tables mark the UIT code conditional for a shipment that is not UIT free, with "Code should be provided if possible" (e.g. §5.4 p23).
The sandbox accepted 601 to RO with `UIT_FREE` `"false"` and no `UIT_NUMBER` (2026-10-05: [booking-2906761347-601-se-ro.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761347-601-se-ro.json)).

On products 202, 205, 233, SPI, and 601, a shipment with the shipper or the recipient in HU or RO without the free flag or the number is declared free, following the manual's "to/from" wording in the same tables: it sends `EKAER_FREE` or `UIT_FREE` `"true"` when its total gross weight, the sum of its parcel weights in kilograms, is below 500 kg.
The sandbox accepted 601 booked this way with `EKAER_FREE` `"true"` to HU and `UIT_FREE` `"true"` to RO (2026-10-08: [booking-2906769555-601-se-hu-default-ekaer-free.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769555-601-se-hu-default-ekaer-free.json), [booking-2906769563-601-se-ro-default-uit-free.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906769563-601-se-ro-default-uit-free.json)).
At or above 500 kg such a shipment fails with `TransportDeclarationError` and asks for `dhl_freight_sweden_ekaer_number` or `dhl_freight_sweden_uit_number`, or an explicit `dhl_freight_sweden_ekaer_free` or `dhl_freight_sweden_uit_free`.
An explicit free flag `true` is sent at any weight.
EKAER and UIT free are legal declarations made on the shipper's or the consignee's behalf, and the connector makes them by default only because they suit typical e-commerce shipments.
The UIT exception covers goods with a value less than 10,000 RON and a weight less than 500 kg ([DHL Denmark](https://www.dhl.com/dk-en/home/about-us/local-news/071024.html)); the connector checks the weight only, not the value.
The EKAER thresholds for risky products, a fiscal-risk product list that is distinct from ADR dangerous goods, are 500 kg and HUF 1,000,000 ([RSM Hungary](https://www.rsm.hu/tax-to-know/ekaer-obligation)); the connector checks the weight only and cannot detect whether goods are risky products.
On other products the options are optional and sent when given.
The sandbox accepted 109 and 112 bookings to HU and RO without these entries (2026-10-05: [booking-2906761263-109-se-ro.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761263-109-se-ro.json), [booking-2906761271-112-se-ro.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761271-112-se-ro.json), [booking-2906761289-109-se-hu.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761289-109-se-hu.json), [booking-2906761297-112-se-hu.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761297-112-se-hu.json)).
601 to HU or RO without these entries has not been sent to the sandbox.

## Transport declaration defaults

The SENT, EKAER, and UIT defaults are not customs or tax advice.
They suit typical e-commerce shipments, and the consumer of the connector, the integrator or the shipper, is responsible for every declaration sent, including the defaults, and for the consequences of misconfigured usage.
DHL charges fines and missing-information fees to the booking party.

## VAT number/TIN for GR

Products 202 (§5.4 p22), SPI (§5.11 p51), and 601 (§5.19 p81) make a VAT number/TIN mandatory for all parties in the shipment information of shipments to or from Greece (GR).
The connector transmits two parties, the shipper as Consignor and the recipient as Consignee, each with its `federal_tax_id`, else its `state_tax_id`, as `vatEoriSocialSecurityNumber`.
On these products, a shipment with the shipper or the recipient in GR fails when either party has neither identifier, with `details` keyed by `shipper.federal_tax_id` or `recipient.federal_tax_id`.
Other products and lanes send the identifiers when given and do not require them.
No GR booking has been sent to the sandbox.

## QR code for 107

Product manual v5.26 offers a QR code for Parcel Return Connect (107), shown by the consumer when handing over the return parcel, through the print API selection `"qrCode": true`, valid for BE, BG, CZ, DE, ES, LU, and PT (§5.15 p65), the countries a 107 return is sent from.
The `dhl_freight_sweden_qr_code` option `true` adds `qrCode` `true` to the print-by-id options of 107 shipments whose shipper is in one of these countries.
On other products or from other countries the option fails with `details` keyed by `dhl_freight_sweden_qr_code`, as access points do where the manual lists none, and `false` or no option requests no QR code.
The vendored print spec 2.10.0 defines `qrCode` as a print option, but its `PrintResult` is a list of reports with `name`, `content`, `contentType`, and `type`, and it does not say how a QR code report is named, typed, or ordered.
The connector returns the first report as the label and does not surface a QR code document; no 107 booking with `qrCode` has been sent to the sandbox.

## Additional information pass-through

The `dhl_freight_sweden_additional_information` option passes further entries through, as a list of `{"code": ..., "stringValue": ...}` objects (`dateValue` and `numericValue` are also accepted).
Entries follow the SENT, EKAER, and UIT entries.
An entry without a code fails, and so does an entry with a SENT, EKAER, or UIT code on a lane where the typed options of that family apply (PL, HU, or RO respectively); on other lanes these codes pass through.
