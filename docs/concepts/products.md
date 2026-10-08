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

## Home delivery with an access code

Home Delivery B2C (401) is delivered through the `doorstepDelivery` additional service rather than an access-point party: set the `dhl_freight_sweden_doorstep_access_code` option and the connector sends it as `additionalServices.doorstepDelivery.accessCode`.

## FR, GB, CH, and LI

The table compares the countries the manual lists for each product with what product matches offered account 116768 and what the sandbox booked.

| Country | Products per manual | Matched for account 116768 | Booked | Evidence |
|---------|---------------------|----------------------------|--------|----------|
| FR | 112, mainland France and Corsica (§5.3 p18, Appendix G p199) | not probed | 112 to FR 75004 with payer code 023, label printed | [booking](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761867-112-se-fr.json), [label](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761867-112-se-fr.json) |
| GB | 109 and 112, only according to a separate agreement (§5.3 p18, §5.14 p63, Appendix G p200) | HDI, 202, 601, 233 | 112 rejected with 22005 "No valid product was found for given productcode and countries" and 22026 "Consignee CountryCode is not valid for this product"; 109 not sent | [matches](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb.json), [rejection](../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22005-112-se-gb.json) |
| CH | 601 (§5.19 p82) | HDI, 202, 601, 233 to Zürich, Geneva, Bern, and Lugano; none of 109, 112, and 107 | 601 to CH 8001 with payer code DAP, customs handling full service, and a `CommercialInvoice`, label printed | [matches](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-8001.json), [booking](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762477-601-se-ch.json) |
| LI | none | 202 | not sent | [matches](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-li-9490.json) |

The manual requires the Print and TransportInstruction APIs for FR shipments, the two APIs the connector books and prints through, so the rate sheet includes FR for 112 (§5.3 p18).
The connector enforces the FR exclusion of 112 from postal codes 97100-99999 with the other numeric excluded regions (see [Excluded postal codes](destinations.md#excluded-postal-codes)), and the 112 FR booking response adds Chronopost `additionalInformation` entries the request did not send.

The rate sheet includes GB for 109 and 112, and the connector books them without checking the separate agreement, which the account must hold; account 116768 holds none.
Appendix C.3 delivers 109 to GB at the doorstep with residential addressing or to a Parcelshop, with no Parcelstation (§10.4.2 p193), which the [access-point table](booking-rules.md#access-points) follows.
GB is outside the EU VAT area, so 109 and 112 to GB carry customs information as they do to NO.

The 601 CH booking took its `CommercialInvoice` amount from `customs.duty.declared_value`.
The PostalCode route for CH 8001 answered 16009, and the nearest-service-points request for Zürich 8001 found no point ([lookup-postal-code-ch-8001-16009.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-ch-8001-16009.json), [lookup-service-points-ch-8001-none.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-ch-8001-none.json)).
The [findings note](../notes/sandbox/sandbox-findings.md#switzerland-and-liechtenstein) lists the remaining CH lookups.
