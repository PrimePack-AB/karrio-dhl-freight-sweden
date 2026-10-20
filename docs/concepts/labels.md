---
title: "Labels"
---

The connector books the transport instruction and then prints its label by shipment id in the same `shipment/create` call, and it returns the first printed report as `docs.label`.
Manual references are to [product manual v5.26](../development/index.md#product-manual-citations), written `§x.y pN`.

## Format

Only PDF labels are supported.
The Print API 2.10.0 spec, cited in [API Farm specification citations](../development/index.md#api-farm-specification-citations), exposes no format parameter, and the sandbox returned a one-page PDF of 105 × 210 mm, 297.638 × 595.276 pt, for page type `Label` ([label-2906761354-109-se-dk-parcelshop.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761354-109-se-dk-parcelshop.json)).
The connector validates the `label_type` connection setting and the shipment request's `label_type` separately on every booking.
Either may be unset or `PDF` in any letter case, and any other value, such as `ZPL`, fails before the booking request with `LabelTypeError`, a `SHIPPING_SDK_FIELD_ERROR` keyed `config.label_type` for the setting or `label_type` for the request, even when the other one says `PDF`.
The returned shipment declares the format read from the decoded document's magic prefix (`%PDF-`, `^XA`), then the report `contentType`, and otherwise `PDF`.

## Page layout

The `label_page_type` connection setting selects the Print API page type, `Label` by default, and the `dhl_freight_sweden_label_page_type` option overrides it per shipment.
The page types of the Print API 2.10.0 spec are `Label`, `Label2xPortraitA4`, `Label3xLandscapeA4`, `LabelCompact`, and `LabelCompact2x2PortraitA4`.
The 112 label to FR is a 100 × 150 mm label in a different layout that carries the Chronopost reference from the booking response ([label-2906761867-112-se-fr.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761867-112-se-fr.json)).
A two-parcel 102 booking's print call returned one report bundling both parcel labels as a two-page PDF, one 105 × 210 mm page per parcel carrying its piece id as the (00) barcode text and an x/N counter ([label-2906788993-102-se-se-two-parcels.json](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906788993-102-se-se-two-parcels.json)).
The booking's `meta.tracking_numbers` carries those piece ids, one per parcel in parcel order ([booking-2906788993-102-se-se-two-parcels.json](../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906788993-102-se-se-two-parcels.json)).

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
| 103 | receiving service point's phone mandatory | `Phn.` line with no number | [103](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761230-103-se-se-service-point.json), [103 with a party phone](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906788324-103-se-se-service-point-phone.json) |

"Not allowed" for 109 and 112 names the manual's 23 countries AT, BE, BG, CZ, DE, DK, EE, ES, FI, FR, HR, HU, IE, IT, LT, LU, LV, NL, NO, PL, PT, RO, and SI, with SK the one mandatory country.
GB, which the manual lists as valid by separate agreement (§5.14 p63), is in neither list, so the generic conditional rule applies there.
The 103 label is the one deviation from the manual, its `Phn.` line empty with and without an AccessPoint party phone in the booking request, and is recorded under [Deviations from manual v5.26](../notes/sandbox/sandbox-findings.md#deviations-from-manual-v526); whether DHL fills the parcelshop phone at production print time is an open question for DHL API Farm.
The sender phone, field 6, is conditional, and printing it is not allowed for 104, for 402/502, or for 107 from every listed country except SK (§9.4.2 p168), so the labels without it do not contradict the manual.

The phone format follows product manual v5.26 Appendix E (§10.6 p197): exactly one prefix (foreign country prefixes are fine), then digits, dash, and space only; dots, letters, and slash are forbidden.
The connector transmits `phone_number` as given, so callers should pre-format numbers to those constraints.

## Customer information section

The manual's label anatomy places "Customer information" in section 16, a 33 mm zone (§9.4.1 p166), and makes it mandatory for 109 shipments addressed to a parcelshop or parcelstation: the consignee's residential name and address, right-aligned on one row, the ISO country code written before the postal code, and no country name in plain text (§9.4.2 p175).
The section is auto-composed from the Consignee party, so no connector input is needed.
The labels of 109 bookings to DK ParcelShop 8009-115191 and NO ParcelShop 8009-129635 print the Consignee name and address, the latter distinct from the shop's ([DK](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761354-109-se-dk-parcelshop.json), [NO](../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906761305-109-se-no-parcelshop.json)).

## References

The TransportInstruction 2.10.0 spec, cited in [API Farm specification citations](../development/index.md#api-farm-specification-citations), defines `parties[].references`, up to 99 entries of at most 35 characters each, and gives the field no description.
The manual's Appendix F scopes references to tracking, loading, delivery, and invoicing, with the qualifiers CU and AAO (§10.7 p198).
The label's "Senders ref:" and "Receivers ref:" lines are field 12 of the label field description (§9.4.2 p174), and no DHL document connects `parties[].references` to those lines.
The connector does not send references.
