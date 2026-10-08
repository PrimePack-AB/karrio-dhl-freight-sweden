---
title: "Products"
---

This page collects the product facts that the README's product catalogue summarises.
Manual references are to [product manual v5.26](../development/index.md#product-manual-citations), written `§x.y pN`.

## Minimum piece dimensions

Parcel dimensions are sent in centimetres, and each product section of the manual states the minimum piece dimensions in its "Minimum and maximum weight and dimensions etc" table.
DHL validates these minimums server-side at booking; the connector does not check them and forwards the dimensions as given.

| Product | Minimum L × W × H | Manual |
|---------|-------------------|--------|
| 102 Paket | 15 × 11 × 2 cm | §5.2 p14 |
| 112 Parcel Connect Plus | 15 × 11 × 2 cm | §5.3 p17 |
| 103 Service Point B2C | 15 × 11 × 2 cm | §5.12 p55 |
| 104 Service Point C2B | 15 × 11 × 2 cm | §5.13 p59 |
| 118 Hemleverans Paket B2C | 15 × 11 × 2 cm | §5.16 p68 |
| 202 Road Freight Standard | 15 × 11 × 3 cm | §5.4 p21 |
| 233 Road Freight Priority | 15 × 11 × 3 cm | §5.10 p45 |
| 601 Home Delivery International B2C | 15 × 11 × 3 cm | §5.19 p80 |
| 211 Stycke | 15 × 11 × 3.5 cm | §5.7 p33 |
| 401 Home Delivery B2C | 15 × 11 × 3.5 cm | §5.17 p71 |
| 402, 502 Home Delivery Return C2B | 15 × 11 × 3.5 cm | §5.18 p75 |
| 210 Pall | 120 × 80 × 15 cm, or 60 × 80 × 15 cm for a half pallet | §5.6 p29 |
| 109 Parcel Connect B2C | varies by destination country | §5.14 p62 |

The 209 Special, 212 Parti, and SPI tables state no minimum (§5.5 p26, §5.8 p37, §5.11 p50).
The instructions of 202 (§5.4 p22), 205 (§5.9 p41), and 601 (§5.19 p81) add that the minimum and maximum weight and dimensions vary by destination country.

For DHL Road Freight Direct (205) the server-side minimum is on chargeable weight: the sandbox rejected a booking of one 1 kg piece from SE to NO with 22020 "ChargeableWeight is lower than product min 2500.0" ([rejection-22020-205-se-no.json](../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22020-205-se-no.json)).

## HDI in product matches

Product matches return HDI on every lane where they return 601, for example SE to PL ([lookup-product-matches-se-pl.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-pl.json)), and on some lanes without 601, such as ES 35001 ([lookup-product-matches-se-es-35001.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-es-35001.json)).
The manual names HDI as the invoice-file code for 601 (§5.19 p81), and the connector offers no HDI service.

## Home delivery with an access code

Home Delivery B2C (401) is delivered through the `doorstepDelivery` additional service rather than an access-point party: set the `dhl_freight_sweden_doorstep_access_code` option and the connector sends it as `additionalServices.doorstepDelivery.accessCode`.

## Lanes

The manual lists each product's valid countries and classifies the product as domestic or international (§5.1 p13).
Rating offers a product only on a lane from the shipper's country to the recipient's that the table allows, comparing territory codes as their parent country (see [Special territories](destinations.md#special-territories)).
An explicitly requested product on another lane adds a `destination_not_supported` message, such as "Product 107 does not ship from CH to SE (product manual v5.26 §5.15 p66)", instead of a rate.
Booking does not check the lane before the request.

| Product | Lanes | Manual |
|---------|-------|--------|
| 102, 103, 104, 118, 209, 210, 211, 212, 401, 402, 502 | within SE | §5.2 p15, §5.12 p56, §5.13 p59, §5.16 p68, §5.5 p27, §5.6 p30, §5.7 p34, §5.8 p38, §5.17 p72, §5.18 p76 |
| 109, 112 | from SE to AT, BE, BG, CZ, DE, DK, EE, ES, FI, FR, GB, HR, HU, IE, IT, LT, LU, LV, NL, NO, PL, PT, RO, SI, SK; GB only by separate agreement | §5.14 p63, §5.3 p18 |
| 107 | from AT, BE, BG, CZ, DE, DK, EE, ES, FI, FR, HR, HU, IE, IT, LT, LU, LV, NL, NO, PL, PT, RO, SI, SK to SE | §5.15 pp65-66 |
| 202, 205, SPI | from SE to AD, AL, AM, AT, AZ, BA, BE, BG, CH, CY, CZ, DE, DK, EE, ES, FI, FR, GB, GE, GI, GR, HR, HU, IE, IT, KG, KZ, LI, LT, LU, LV, MA, MC, MD, ME, MK, MT, NL, NO, PL, PT, RO, RS, SI, SK, SM, TJ, TR, UA, UZ, XK, and from them to SE | §5.4 pp22-23, §5.9 pp41-43, §5.11 pp51-52 |
| 233 | from SE to AT, BE, BG, CH, CZ, DE, DK, EE, ES, FI, FR, GB, HR, HU, IE, IT, LI, LT, LU, LV, NL, NO, PL, PT, RO, SI, SK, and from them to SE | §5.10 pp46-47 |
| 601 | from SE to AT, BE, BG, CH, CZ, DE, DK, EE, ES, FI, FR, GB, GR, HR, HU, IE, IT, LT, LU, LV, NL, NO, PL, PT, RO, SI, SK, and from them to SE | §5.19 pp81-82 |

202, 205, 233, SPI, and 601 list SE among their valid countries as the Swedish end of a lane, since each "can be used to and from Sweden" (§5.4 p22, §5.9 p41, §5.10 p46, §5.11 p51, §5.19 p81), so none of them, and none of 109, 112, and 107, serves a lane within SE.
107 returns a 109 shipment to its original sender in SE (§5.15 p65).
Karrio's rating classifies a delivery into the account country SE as domestic, so it offers no import lane into SE of 202, 205, 233, SPI, and 601.
Karrio's unified rating and shipping calls accept only shippers in SE, so they refuse a 107 shipment, whose shipper is abroad, before it reaches the connector.

## FR, GB, CH, and LI

The table compares the countries the manual lists for each product with what product matches offered account 116768 and what the sandbox booked.

| Country | Products per manual | Matched for account 116768 | Booked | Evidence |
|---------|---------------------|----------------------------|--------|----------|
| FR | 109 and 112 to mainland France and Corsica (§5.3 p18, §5.14 p63, Appendix G p199), 107 from them (§5.15 p66), and 202, 205, 233, SPI, and 601 (§5.4 p23, §5.9 p43, §5.10 p47, §5.11 p52, §5.19 p82) | not probed | 112 to FR 75004 with payer code 023, label printed | [booking](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761867-112-se-fr.json), [label](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761867-112-se-fr.json) |
| GB | 109 and 112, only according to a separate agreement (§5.3 p18, §5.14 p63, Appendix G p200), and 202, 205, 233, SPI, and 601 (§5.4 p23, §5.9 p43, §5.10 p47, §5.11 p52, §5.19 p82); not 107 (§5.15 p66) | HDI, 202, 601, 233 | 112 rejected with 22005 "No valid product was found for given productcode and countries" and 22026 "Consignee CountryCode is not valid for this product"; 109 not sent | [matches](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb.json), [rejection](../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22005-112-se-gb.json) |
| CH | 202, 205, 233, SPI, and 601 (§5.4 p23, §5.9 p43, §5.10 p47, §5.11 p52, §5.19 p82) | HDI, 202, 601, 233 to Zürich, Geneva, Bern, and Lugano; none of 109, 112, and 107 | 601 to CH 8001 with payer code DAP, customs handling full service, and a `CommercialInvoice`, label printed | [matches](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-8001.json), [booking](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762477-601-se-ch.json) |
| LI | 202, 205, 233, and SPI (§5.4 p23, §5.9 p43, §5.10 p47, §5.11 p52) | 202 | not sent | [matches](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-li-9490.json) |

The manual requires the Print and TransportInstruction APIs for FR shipments, the two APIs the connector books and prints through, so rating offers 112 to FR (§5.3 p18).
The connector enforces the FR exclusion of 112 from postal codes 97100-99999 with the other numeric excluded regions (see [Excluded postal codes](destinations.md#excluded-postal-codes)), and the 112 FR booking response adds Chronopost `additionalInformation` entries the request did not send.

Rating offers 109 and 112 to GB, and the connector books them without checking the separate agreement, which the account must hold; account 116768 holds none.
Appendix C.3 delivers 109 to GB at the doorstep with residential addressing or to a Parcelshop, with no Parcelstation (§10.4.2 p193), which the [access-point table](booking-rules.md#access-points) follows.
GB is outside the EU VAT area, so 109 and 112 to GB carry customs information as they do to NO.

The 601 CH booking took its `CommercialInvoice` amount from `customs.duty.declared_value`.
The PostalCode route for CH 8001 answered 16009, and the nearest-service-points request for Zürich 8001 found no point ([lookup-postal-code-ch-8001-16009.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-ch-8001-16009.json), [lookup-service-points-ch-8001-none.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-ch-8001-none.json)).
The [findings note](../notes/sandbox/sandbox-findings.md#product-matches) lists the remaining CH lookups.
