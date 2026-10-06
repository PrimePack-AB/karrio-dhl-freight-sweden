---
title: "Labels"
---

The connector books the transport instruction and then prints its label by shipment id in the same `shipment/create` call, and it returns the first printed report as `docs.label`.
Manual references are to product manual v5.26 (sha256 `050660c37ba93d1ae9514c50dfa42c2010bc87763ccaff51a740b2526af11b73`), written `§x.y pN`.

## Format

Only PDF labels are supported.
The Print API exposes no format parameter, and the sandbox returned a one-page PDF of 105 × 210 mm, 297.638 × 595.276 pt, for page type `Label` (2026-10-05: [label-2906761354-109-se-dk-parcelshop.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761354-109-se-dk-parcelshop.json)).
The connector validates the `label_type` connection setting and the shipment request's `label_type` separately on every booking.
Either may be unset or `PDF` in any letter case, and any other value, such as `ZPL`, fails before the booking request with `LabelTypeError`, a `SHIPPING_SDK_FIELD_ERROR` keyed `config.label_type` for the setting or `label_type` for the request, even when the other one says `PDF`.
The returned shipment declares the format read from the decoded document's magic prefix (`%PDF-`, `^XA`), then the report `contentType`, and otherwise `PDF`.

## Page layout

The `label_page_type` connection setting selects the Print API page type, `Label` by default, and the `dhl_freight_sweden_label_page_type` option overrides it per shipment.
The page types are `Label`, `Label2xPortraitA4`, `Label3xLandscapeA4`, `LabelCompact`, and `LabelCompact2x2PortraitA4`.
The 112 label to FR is a 100 × 150 mm label in a different layout that carries the Chronopost reference from the booking response ([label-2906761867-112-se-fr.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761867-112-se-fr.json)).

## Phone numbers

The connector always transmits the consignee `phone_number` on the booking, and no sandbox label printed it (2026-10-05 and 2026-10-06, bookings with account 116768): 109 ParcelShop labels print only the shipper phone on the `Phn.` line ([label-2906761354-109-se-dk-parcelshop.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761354-109-se-dk-parcelshop.json), [label-2906761305-109-se-no-parcelshop.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761305-109-se-no-parcelshop.json)), the home-delivery labels of 102, 118, and 601, the 112 label to HU, and the 103 service-point label print a `Phn.` line with no number ([label-2906761222-102-se-se.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761222-102-se-se.json), [label-2906761297-112-se-hu.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761297-112-se-hu.json), [label-2906761255-118-se-se.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761255-118-se-se.json), [label-2906761248-601-se-dk.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761248-601-se-dk.json), [label-2906761230-103-se-se-service-point.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761230-103-se-se-service-point.json)), and the 112 label to FR, a 100 × 150 mm label in a different layout that carries the Chronopost reference from the booking response, has no `Phn.` line ([label-2906761867-112-se-fr.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761867-112-se-fr.json)).
The 109 labels to DK and NO, the 112 labels to HU and FR, and the 118 label match product manual v5.26 §9.4.2, which does not allow printing the receiver phone (field 9) for 109 and 112 to every listed country except SK, where it is mandatory, nor for 118 and 401 (p170).
The same section marks the sender phone (field 6) conditional and does not allow printing it for 104, for 402/502, or for 107 from every listed country except SK (p168), and it marks the receiver phone conditional for the other products, so the blank `Phn.` lines of the 102 and 601 labels do not contradict it.
The 103 label's blank `Phn.` line remains a deviation, because the manual makes the receiving service point's phone number mandatory on 103 labels (p170) ([Phone numbers on labels](../notes/sandbox/sandbox-findings.md#phone-numbers-on-labels)).

The phone format follows product manual v5.26 Appendix E (§10.6 p197): exactly one prefix (foreign country prefixes are fine), then digits, dash, and space only; dots, letters, and slash are forbidden.
The connector transmits `phone_number` as given, so callers should pre-format numbers to those constraints.

## Customer information section

For parcelshop/parcelstation-addressed 109 shipments the mandatory "Customer information" label section is auto-composed from the Consignee party, so no connector input is needed (sandbox 2026-10-05: the labels of 109 bookings to DK ParcelShop 8009-115191 and NO ParcelShop 8009-129635 print the Consignee name and address, the latter distinct from the shop's; [label-2906761354-109-se-dk-parcelshop.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761354-109-se-dk-parcelshop.json), [label-2906761305-109-se-no-parcelshop.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761305-109-se-no-parcelshop.json)).

## Custom label text

The transport-instruction API offers `parties[].references` as an optional shipper-controlled free-text channel for custom label print text, and the connector does not send it.
