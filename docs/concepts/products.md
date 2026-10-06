---
title: "Products: piece limits and destinations"
---

This page collects the product facts that the README's product catalogue summarises.
Manual references are to product manual v5.26 (sha256 `050660c37ba93d1ae9514c50dfa42c2010bc87763ccaff51a740b2526af11b73`), written `§x.y pN`.

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

For DHL Road Freight Direct (205) the server-side minimum is on chargeable weight: the sandbox rejected a booking of one 1 kg piece from SE to NO with 22020 "ChargeableWeight is lower than product min 2500.0" (2026-10-06: [rejection-22020-205-se-no.json](../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22020-205-se-no.json)).

## Home delivery with an access code

Home Delivery B2C (401) is delivered through the `doorstepDelivery` additional service rather than an access-point party: set the `dhl_freight_sweden_doorstep_access_code` option and the connector sends it as `additionalServices.doorstepDelivery.accessCode`.

## France

Product manual v5.26 lists FR among the valid countries of Parcel Connect Plus (112) (§5.3 p18, Appendix G p199) and requires the Print and TransportInstruction APIs for FR shipments, the two APIs the connector books and prints through, so the rate sheet includes FR for 112.
The manual limits 112 delivery in FR to mainland France and Corsica and excludes postal codes 97100-99999 (§5.3 p18), which the connector enforces with the other numeric excluded regions (see [Excluded postal codes](destinations.md#excluded-postal-codes)).
The sandbox accepted 112 from SE to FR 75004 with payer code 023 and printed its label, and the response added Chronopost `additionalInformation` entries the request did not send (2026-10-06: [booking-2906761867-112-se-fr.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761867-112-se-fr.json), [label-2906761867-112-se-fr.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761867-112-se-fr.json)).

## Great Britain

The manual lists GB for 112 only according to a separate agreement with DHL (§5.3 p18, Appendix G p200), so the rate sheet includes GB for 112 and the connector books it without checking the agreement, which the account must hold.
Parcel Connect B2C (109) likewise lists GB only according to a separate agreement (§5.14 p63, Appendix G p200), and the rate sheet includes GB for 109 on the same terms.
Appendix C.3 delivers 109 to GB at the doorstep with residential addressing or to a Parcelshop, with no Parcelstation (§10.4.2 p193), which the [access-point table](booking-rules.md#access-points) follows.
GB is outside the EU VAT area, so 109 and 112 to GB carry customs information as they do to NO.

Account 116768 holds no such agreement.
Product matches for SE 11143 to GB W1D 1AN returned HDI, 202, 601, and 233 ([lookup-product-matches-se-gb.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb.json)), and a 112 booking to GB sent regardless was rejected with 22005 "No valid product was found for given productcode and countries" and 22026 "Consignee CountryCode is not valid for this product" (2026-10-06: [rejection-22005-112-se-gb.json](../../tests/dhl_freight_sweden/fixtures/sandbox/rejection-22005-112-se-gb.json)).
A 109 booking to GB without the agreement is expected to fail the same way and has not been sent to the sandbox.

## Switzerland and Liechtenstein

On account 116768, product matches from SE 11143 to Zürich (CH 8001, with a 2 kg and a 20 kg piece), Geneva (CH 1201), Bern (CH 3011), and Lugano (CH 6900) returned HDI, 202, 601, and 233 and none of 109, 112, and 107, and Vaduz (LI 9490) matched 202 alone (2026-10-06: [lookup-product-matches-se-ch-8001.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-8001.json), [lookup-product-matches-se-li-9490.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-li-9490.json)).
The manual lists CH, but not LI, among the valid countries of 601 (§5.19 p82).
The PostalCode route for CH 8001 answered 16009, and the nearest-service-points request for Zürich 8001 found no point ([lookup-postal-code-ch-8001-16009.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-ch-8001-16009.json), [lookup-service-points-ch-8001-none.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-ch-8001-none.json)).
The sandbox accepted 601 to Zürich 8001 with one 2 kg 30 × 20 × 15 cm piece, payer code DAP, customs handling full service, and a `CommercialInvoice` whose amount came from `customs.duty.declared_value`, as 2906762477 with routing code 2LCH8001+00000001, and printed one PDF label (2026-10-06: [booking-2906762477-601-se-ch.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762477-601-se-ch.json)).
The [findings note](../notes/sandbox/sandbox-findings.md#switzerland-and-liechtenstein) lists the remaining CH lookups.
