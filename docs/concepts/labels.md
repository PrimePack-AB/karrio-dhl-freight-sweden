---
title: "Labels"
---

The connector books the transport instruction and then prints its label by shipment id in the same `shipment/create` call, and it returns the first printed report as `docs.label`.
Manual references are to [product manual v5.26](../development/index.md#product-manual-citations), written `§x.y pN`.

## Format

Only PDF labels are supported.
The Print API exposes no format parameter, and the sandbox returned a one-page PDF of 105 × 210 mm, 297.638 × 595.276 pt, for page type `Label` ([label-2906761354-109-se-dk-parcelshop.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761354-109-se-dk-parcelshop.json)).
The connector validates the `label_type` connection setting and the shipment request's `label_type` separately on every booking.
Either may be unset or `PDF` in any letter case, and any other value, such as `ZPL`, fails before the booking request with `LabelTypeError`, a `SHIPPING_SDK_FIELD_ERROR` keyed `config.label_type` for the setting or `label_type` for the request, even when the other one says `PDF`.
The returned shipment declares the format read from the decoded document's magic prefix (`%PDF-`, `^XA`), then the report `contentType`, and otherwise `PDF`.

## Page layout

The `label_page_type` connection setting selects the Print API page type, `Label` by default, and the `dhl_freight_sweden_label_page_type` option overrides it per shipment.
The page types are `Label`, `Label2xPortraitA4`, `Label3xLandscapeA4`, `LabelCompact`, and `LabelCompact2x2PortraitA4`.
The 112 label to FR is a 100 × 150 mm label in a different layout that carries the Chronopost reference from the booking response ([label-2906761867-112-se-fr.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761867-112-se-fr.json)).

## Phone numbers

The connector always transmits the consignee `phone_number` on the booking, and no sandbox label printed it.
The table compares the labels with the receiver phone, field 9, of the manual's label field description (§9.4.2 p170).

| Product | Receiver phone per §9.4.2 | Sandbox label | Evidence |
|---------|---------------------------|---------------|----------|
| 109 to DK and NO | not allowed | shipper phone only on the `Phn.` line | [DK](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761354-109-se-dk-parcelshop.json), [NO](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761305-109-se-no-parcelshop.json) |
| 112 to HU | not allowed | `Phn.` line with no number | [HU](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761297-112-se-hu.json) |
| 112 to FR | not allowed | no `Phn.` line | [FR](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761867-112-se-fr.json) |
| 109 and 112 to SK | mandatory | not booked | |
| 118 | not allowed | `Phn.` line with no number | [118](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761255-118-se-se.json) |
| 401 | not allowed | no label evidence | |
| 102 | conditional | `Phn.` line with no number | [102](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761222-102-se-se.json) |
| 601 to DK | conditional | `Phn.` line with no number | [601](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761248-601-se-dk.json) |
| 103 | receiving service point's phone mandatory | `Phn.` line with no number | [103](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761230-103-se-se-service-point.json) |

"Not allowed" for 109 and 112 covers every country the manual lists for them except SK.
The 103 label is the one deviation from the manual, recorded under [Phone numbers on labels](../notes/sandbox/sandbox-findings.md#phone-numbers-on-labels).
The sender phone, field 6, is conditional, and printing it is not allowed for 104, for 402/502, or for 107 from every listed country except SK (p168), so the labels without it do not contradict the manual.

The phone format follows product manual v5.26 Appendix E (§10.6 p197): exactly one prefix (foreign country prefixes are fine), then digits, dash, and space only; dots, letters, and slash are forbidden.
The connector transmits `phone_number` as given, so callers should pre-format numbers to those constraints.

## Customer information section

For parcelshop/parcelstation-addressed 109 shipments the mandatory "Customer information" label section is auto-composed from the Consignee party, so no connector input is needed.
The labels of 109 bookings to DK ParcelShop 8009-115191 and NO ParcelShop 8009-129635 print the Consignee name and address, the latter distinct from the shop's ([DK](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761354-109-se-dk-parcelshop.json), [NO](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761305-109-se-no-parcelshop.json)).

## Custom label text

The transport-instruction API offers `parties[].references` as an optional shipper-controlled free-text channel for custom label print text, and the connector does not send it.
