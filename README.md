# karrio.dhl_freight_sweden

This package is a DHL Freight Sweden extension of the [karrio](https://pypi.org/project/karrio) multi carrier shipping SDK.

It targets the DHL Freight Sweden API Farm and authenticates with a single `client-key` header (no token exchange).
It covers shipment booking with a printed label and a URL-only tracking link surfaced through the shipment `meta`, static rate-sheet rating, service-point (PUDO) booking with connector-local lookups, and postal-code address validation.

## Requirements

`Python 3.11+`

## Installation

```bash
pip install git+https://github.com/PrimePack-AB/karrio-dhl-freight-sweden.git
```

The connector registers through the `karrio.plugins` entry point group under the id `dhl_freight_sweden`, so installing the package makes the carrier available to every karrio SDK runtime and uninstalling it removes the carrier.
The `METADATA` object in `karrio/plugins/dhl_freight_sweden/__init__.py` binds the mapper, proxy, settings, service and option units, and connection configs that the entry point exposes.

## Usage

```python
import karrio.sdk as karrio
from karrio.mappers.dhl_freight_sweden.settings import Settings


# Initialize a carrier gateway
dhl_freight_sweden = karrio.gateway["dhl_freight_sweden"].create(
    Settings(
        client_key="...",       # DHL Freight Sweden API Farm client key (sent as the client-key header)
        account_number="...",    # customer/agreement number, sent as the consignor party id
        test_mode=True,          # sandbox (test-api.freight-logistics.dhl.com) vs production
    )
)
```

Check the [Karrio Mutli-carrier SDK docs](https://docs.karrio.io) for Shipping API requests

## Connection settings

Connection settings are passed through the gateway's `config` dict (e.g. `config={"label_type": "ZPL"}`).

| Setting | Default | Notes |
|---------|---------|-------|
| `label_type` | `PDF` | Tags the returned document format when the carrier response does not identify it. The Print API exposes no format parameter, so the emitted format is governed by the DHL account (the sandbox returned a one-page PDF of 105 × 210 mm, 297.638 × 595.276 pt, for page type `Label`, 2026-10-05: [label-2906761354-109-se-dk-parcelshop.json](tests/dhl_freight_sweden/fixtures/sandbox/label-2906761354-109-se-dk-parcelshop.json)); the connector derives the tag from the decoded document's magic prefix (`%PDF-`, `^XA`) first, then the report `contentType`, and uses this setting as the last resort. |
| `label_page_type` | `Label` | Print page layout (`Label`, `Label2xPortraitA4`, `Label3xLandscapeA4`, `LabelCompact`, `LabelCompact2x2PortraitA4`); the `dhl_freight_sweden_label_page_type` option overrides it per shipment. |
| `address_validation` | `off` | Booking pre-flight against the postal-code route: `off`, `warn`, or `enforce` (see [Address validation](#address-validation)). |
| `server_url` | | Overrides the API Farm host selected by `test_mode`. |

## Label printing behavior

The connector always transmits the consignee `phone_number` on the booking, and no sandbox label printed it (2026-10-05 and 2026-10-06, bookings with account 116768): 109 ParcelShop labels print only the shipper phone on the `Phn.` line ([label-2906761354-109-se-dk-parcelshop.json](tests/dhl_freight_sweden/fixtures/sandbox/label-2906761354-109-se-dk-parcelshop.json), [label-2906761305-109-se-no-parcelshop.json](tests/dhl_freight_sweden/fixtures/sandbox/label-2906761305-109-se-no-parcelshop.json)), the home-delivery labels of 102, 118, and 601, the 112 label to HU, and the 103 service-point label print a `Phn.` line with no number ([label-2906761222-102-se-se.json](tests/dhl_freight_sweden/fixtures/sandbox/label-2906761222-102-se-se.json), [label-2906761297-112-se-hu.json](tests/dhl_freight_sweden/fixtures/sandbox/label-2906761297-112-se-hu.json), [label-2906761255-118-se-se.json](tests/dhl_freight_sweden/fixtures/sandbox/label-2906761255-118-se-se.json), [label-2906761248-601-se-dk.json](tests/dhl_freight_sweden/fixtures/sandbox/label-2906761248-601-se-dk.json), [label-2906761230-103-se-se-service-point.json](tests/dhl_freight_sweden/fixtures/sandbox/label-2906761230-103-se-se-service-point.json)), and the 112 label to FR, a 100 × 150 mm label in a different layout that carries the Chronopost reference from the booking response, has no `Phn.` line ([label-2906761867-112-se-fr.json](tests/dhl_freight_sweden/fixtures/sandbox/label-2906761867-112-se-fr.json)).
The 109 labels to DK and NO, the 112 labels to HU and FR, and the 118 label match product manual v5.26 §9.4.2, which does not allow printing the receiver phone (field 9) for 109 and 112 to every listed country except SK, where it is mandatory, nor for 118 and 401 (p170).
The same section marks the sender phone (field 6) conditional and does not allow printing it for 104, for 402/502, or for 107 from every listed country except SK (p168), and it marks the receiver phone conditional for the other products, so the blank `Phn.` lines of the 102 and 601 labels do not contradict it.
The 103 label's blank `Phn.` line remains a deviation, because the manual makes the receiving service point's phone number mandatory on 103 labels (p170) ([Phone numbers on labels](docs/notes/sandbox/sandbox-findings.md#phone-numbers-on-labels)).
For parcelshop/parcelstation-addressed 109 shipments the mandatory "Customer information" label section is auto-composed from the Consignee party, so no connector input is needed (sandbox 2026-10-05: the labels of 109 bookings to DK ParcelShop 8009-115191 and NO ParcelShop 8009-129635 print the Consignee name and address, the latter distinct from the shop's; [label-2906761354-109-se-dk-parcelshop.json](tests/dhl_freight_sweden/fixtures/sandbox/label-2906761354-109-se-dk-parcelshop.json), [label-2906761305-109-se-no-parcelshop.json](tests/dhl_freight_sweden/fixtures/sandbox/label-2906761305-109-se-no-parcelshop.json)).
`parties[].references` exists as the optional shipper-controlled free-text channel for custom label print text.
Phone format per product manual v5.26 Appendix E (§10.6 p197): exactly one prefix (foreign country prefixes are fine), then digits, dash, and space only — dots, letters, and slash are forbidden.
The connector transmits `phone_number` as given, so callers should pre-format numbers to those constraints.

## Per-product requirements

Parcel dimensions are sent in centimetres, and some products enforce minimum piece dimensions.

| Product | Minimum length | Minimum width | Minimum height |
|---------|----------------|---------------|----------------|
| 102 Paket | 15 cm | 11 cm | 2 cm |
| 601 Home Delivery International B2C | 15 cm | 11 cm | 3 cm |

DHL validates these minimums server-side at booking; the connector does not check them and forwards the dimensions as given.
Home Delivery B2C (401) is delivered through the `doorstepDelivery` additional service rather than an access-point party: set the `dhl_freight_sweden_doorstep_access_code` option and the connector sends it as `additionalServices.doorstepDelivery.accessCode`.
Product manual v5.26 lists FR among the valid countries of Parcel Connect Plus (112) (§5.3 p18, Appendix G p199) and requires the Print and TransportInstruction APIs for FR shipments, the two APIs the connector books and prints through, so the rate sheet includes FR for 112.
The manual also lists GB for 112, only according to a separate agreement with DHL (§5.3 p18, Appendix G p200), so the rate sheet includes GB for 112 and the connector books it without checking the agreement, which the account must hold.
GB is outside the EU VAT area, so 112 to GB carries customs information as 112 to NO does.
The sandbox account was not offered 112 to GB: product matches for SE 11143 to GB W1D 1AN returned HDI, 202, 601, and 233, so the suite's 112 GB case skipped without booking (2026-10-06: [lookup-product-matches-se-gb.json](tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-gb.json)), and 112 to GB has not been booked.
The manual limits 112 delivery in FR to mainland France and Corsica and excludes postal codes 97100-99999 (§5.3 p18).
Rating does not offer 112 to a FR recipient whose postal code lies in that range or is not exactly five digits once spaces are removed, including a missing postal code, because such a code cannot be shown to lie outside the range; an explicitly requested 112 adds a `destination_not_supported` message instead of a rate.
Booking 112 to such a FR postal code fails before the booking request with `details` keyed by `recipient.postal_code`.
The other excluded regions the manual lists for 112 (§5.3 p18), 109 (§5.14 p63), 107 (§5.15 p66), and 202, 205, and SPI (§5.4 p23, §5.9 p43, §5.11 p52) are not checked, and the connector forwards those addresses as given.
The sandbox accepted 112 from SE to FR 75004 with payer code 023 and printed its label, and the response added Chronopost `additionalInformation` entries the request did not send (2026-10-06: [booking-2906761867-112-se-fr.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761867-112-se-fr.json), [label-2906761867-112-se-fr.json](tests/dhl_freight_sweden/fixtures/sandbox/label-2906761867-112-se-fr.json)).

## Booking rules

The connector checks payer codes, access points, SENT, EKAER, and UIT entries, the VAT numbers/TINs of lanes to or from GR, excluded postal codes, and the QR code option before the booking request, and fails fast with a `SHIPPING_SDK_FIELD_ERROR` whose `details` are keyed by the option to fix.
The rules follow the DHL Freight (Sweden) product manual, version 5.26, updated 2026-10-01 and valid from 2026-11-01, which is cited here rather than vendored.
DHL lists the current manual at <https://dhlpaket.se/dashboard/specifications/products/>, and the cited copy of version 5.26 has sha256 `050660c37ba93d1ae9514c50dfa42c2010bc87763ccaff51a740b2526af11b73`.
Section and page references below are to that version.

### Payer codes

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
| 112 | 022, 023 | 023 | §5.3 p19 (023 only); 022 per sandbox booking 2906761149 ([booking-2906761149-112-se-pl-payer-022.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761149-112-se-pl-payer-022.json)) |
| 202, 233, SPI, 601 | export EXW, FCA, CPT, CIP, DAP, DPU, DDP; import EXW, FCA | none | §5.4 p24, §5.10 p48, §5.11 p53, §5.19 p83 |
| 205 | export CPT, CIP, DAP, DPU, DDP; import EXW, FCA | none | §5.9 p43 |

A lane is an import when the recipient is in SE and the shipper is not; the import column applies only to the products that list one.
The code resolves in this order:

1. The `dhl_freight_sweden_payer_code` option, which must be a valid code.
2. `customs.incoterm` when it is a valid code. For 109 and 112, which accept only Combiterms, the Incoterm is translated per §7.6 p163 (CPT, CIP, DAP, DPU to 022; DDP to 023) and the result must be valid. For other products an Incoterm outside the product's codes is not used.
3. The product default from the table. A product without a default needs an explicit payer code.

Payer code 023 on 109 additionally requires the `dhl_freight_sweden_customs_joint_declaration` option.
Product codes the connector does not define keep the previous fallback of option, then Incoterm, then `1`.

### Access points

The `dhl_freight_sweden_service_point` options produce an AccessPoint party only where the manual lists an access-point delivery for the product and the recipient country.

| Product | Country | Sub types | Manual |
|---------|---------|-----------|--------|
| 103 | SE | ParcelShop, ParcelStation | §5.12 p55-56 |
| 109 | AT, BE, BG, CZ, DK, EE, FI, HU, IT, LT, LV, NL, PL, SK | ParcelShop, ParcelStation | Appendix C.3, §10.4.2 p192-194 |
| 109 | DE, ES, FR, GB, HR, NO, PT, RO, SI | ParcelShop | Appendix C.3, §10.4.2 p192-193 |

Every other product and country accepts no AccessPoint party, including 109 to IE and LU and all of 112 (§5.3 p19), for which DHL answers 22015 "AccessPoint Party is not allowed for this product" (sandbox, 2026-10-05: [rejection-22015-112-se-pl-access-point.json](tests/dhl_freight_sweden/fixtures/sandbox/rejection-22015-112-se-pl-access-point.json)).
A `dhl_freight_sweden_service_point` value that is a sub type or location type name (`ParcelShop`, `ParcelStation`, `servicepoint`, `locker`, `postoffice`, `postbank`, in any case) is rejected: the option takes the service point id, and the sub type goes in `dhl_freight_sweden_service_point_type`.

Appendix M (§10.14.2.2 p232) states that the AccessPoint `subtype` carries the location type (`servicepoint`, `locker`, `postoffice`), while the transport-instruction booking spec enumerates `ParcelShop` and `ParcelStation`.
The connector sends `ParcelShop` and `ParcelStation`.
The sandbox accepted 109 bookings with `ParcelShop` to PL, RO, NO, and DK and with `ParcelStation` to a HU locker (2026-10-05: [booking-2906761123-109-se-pl.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761123-109-se-pl.json), [booking-2906761263-109-se-ro.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761263-109-se-ro.json), [booking-2906761305-109-se-no.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761305-109-se-no.json), [booking-2906761354-109-se-dk.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761354-109-se-dk.json), [booking-2906761289-109-se-hu.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761289-109-se-hu.json)).

### SENT

Lanes with the shipper or the recipient in PL carry SENT entries under the shipment's `additionalInformation`.

| Option | Type | Sent as |
|--------|------|---------|
| `dhl_freight_sweden_sent_ref` | string, at most 20 characters | `SENT_REF` |
| `dhl_freight_sweden_sent_carkey` | string, at most 20 characters | `SENT_CARKEY` |
| `dhl_freight_sweden_sent_free` | boolean | `SENT_FREE` |

Both identifiers send `SENT_FREE` `"false"` followed by `SENT_REF` and `SENT_CARKEY`, as in the manual's API example (§5.4 p23); one identifier without the other fails, and `dhl_freight_sweden_sent_free` `true` together with either identifier fails as contradictory.
`dhl_freight_sweden_sent_free` `true` without identifiers sends `SENT_FREE` `"true"`, and `false` without identifiers fails.
A shipment with neither the free flag nor the identifiers fails and asks for an explicit SENT declaration.
The connector does not declare a shipment SENT free by itself: like EKAER and UIT, SENT free is a legal declaration made on the shipper's or the consignee's behalf, and the connector cannot verify the facts it rests on, such as the risk class of the goods or the aggregation of goods per vehicle.
The opt-in sandbox suite declares its 109 and 112 bookings to PL SENT free with `dhl_freight_sweden_sent_free`.
The related-fields tables of 202 (§5.4 p23), 205 (§5.9 p42), 233 (§5.10 p47), SPI (§5.11 p52), and 601 (§5.19 p82) make the question "Is shipment SENT free?" (`SENT_FREE`) mandatory for shipments to or from PL, and the SENT reference and carrier key mandatory when the answer is no; the sections of 109 and 112 do not mention SENT.
The live API rejects a PL booking without either identifier unless `SENT_FREE` is `"true"` (22001 "SENT_REF and SENT_CARKEY are mandatory unless SENT_FREE is true.", sandbox 2026-10-05: [rejection-22001-109-se-pl-without-sent.json](tests/dhl_freight_sweden/fixtures/sandbox/rejection-22001-109-se-pl-without-sent.json)).
The sandbox accepted 109 and 112 bookings to PL with `SENT_FREE` `"true"` at shipment level ([booking-2906761123-109-se-pl.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761123-109-se-pl.json), [booking-2906761131-112-se-pl.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761131-112-se-pl.json)).
The vendored transport-instruction spec 2.10.0 defines the `AdditionalInformation` schema but does not reference it from the shipment; the live API accepts it at shipment level.

### EKAER and UIT

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
The sandbox accepted 601 to HU with `EKAER_FREE` `"false"` and the made-up `EKAER_NUMBER` `E0000SANDBOX0001` (2026-10-05: [booking-2906761339-601-se-hu.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761339-601-se-hu.json)).
`dhl_freight_sweden_uit_free` `false` without a number sends `UIT_FREE` `"false"` alone, because the same tables mark the UIT code conditional for a shipment that is not UIT free, with "Code should be provided if possible" (e.g. §5.4 p23).
The sandbox accepted 601 to RO with `UIT_FREE` `"false"` and no `UIT_NUMBER` (2026-10-05: [booking-2906761347-601-se-ro.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761347-601-se-ro.json)).

On products 202, 205, 233, SPI, and 601, a shipment with the shipper or the recipient in HU or RO without the free flag or the number fails and asks for an explicit declaration, following the manual's "to/from" wording in the same tables.
The connector does not declare a shipment EKAER or UIT free by itself: these are legal declarations made on the shipper's or the consignee's behalf, and the connector cannot verify the facts they rest on, such as the risk class of the goods or the aggregation of goods per vehicle.
On other products the options are optional and sent when given.
The sandbox accepted 109 and 112 bookings to HU and RO without these entries (2026-10-05: [booking-2906761263-109-se-ro.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761263-109-se-ro.json), [booking-2906761271-112-se-ro.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761271-112-se-ro.json), [booking-2906761289-109-se-hu.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761289-109-se-hu.json), [booking-2906761297-112-se-hu.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761297-112-se-hu.json)).
601 to HU or RO without these entries has not been sent to the sandbox.

### VAT number/TIN for GR

Products 202 (§5.4 p22), SPI (§5.11 p51), and 601 (§5.19 p81) make a VAT number/TIN mandatory for all parties in the shipment information of shipments to or from Greece (GR).
The connector transmits two parties, the shipper as Consignor and the recipient as Consignee, each with its `federal_tax_id`, else its `state_tax_id`, as `vatEoriSocialSecurityNumber`.
On these products, a shipment with the shipper or the recipient in GR fails when either party has neither identifier, with `details` keyed by `shipper.federal_tax_id` or `recipient.federal_tax_id`.
Other products and lanes send the identifiers when given and do not require them.
No GR booking has been sent to the sandbox.

### QR code for 107

Product manual v5.26 offers a QR code for Parcel Return Connect (107), shown by the consumer when handing over the return parcel, through the print API selection `"qrCode": true`, valid for BE, BG, CZ, DE, ES, LU, and PT (§5.15 p65), the countries a 107 return is sent from.
The `dhl_freight_sweden_qr_code` option `true` adds `qrCode` `true` to the print-by-id options of 107 shipments whose shipper is in one of these countries.
On other products or from other countries the option fails with `details` keyed by `dhl_freight_sweden_qr_code`, as access points do where the manual lists none, and `false` or no option requests no QR code.
The vendored print spec 2.10.0 defines `qrCode` as a print option, but its `PrintResult` is a list of reports with `name`, `content`, `contentType`, and `type`, and it does not say how a QR code report is named, typed, or ordered.
The connector returns the first report as the label and does not surface a QR code document; no 107 booking with `qrCode` has been sent to the sandbox.

### Additional information pass-through

The `dhl_freight_sweden_additional_information` option passes further entries through, as a list of `{"code": ..., "stringValue": ...}` objects (`dateValue` and `numericValue` are also accepted).
Entries follow the SENT, EKAER, and UIT entries.
An entry without a code fails, and so does an entry with a SENT, EKAER, or UIT code on a lane where the typed options of that family apply (PL, HU, or RO respectively); on other lanes these codes pass through.

### Discrepancies

For 112 the DHL Product API catalog (`GET /productapi/v1/products/112`, test host, 2026-10-05: [lookup-products-109-112-payer-codes.json](tests/dhl_freight_sweden/fixtures/sandbox/lookup-products-109-112-payer-codes.json)) lists CPT, CIP, DAP, DPU, DDP, 022, and 023, while the manual (§5.3 p19) lists only 023.
The sandbox rejected payer code 1 for 112 (22020 "Payercode 1 is not valid for product": [rejection-22020-112-se-pl-payer-code-1.json](tests/dhl_freight_sweden/fixtures/sandbox/rejection-22020-112-se-pl-payer-code-1.json)) and accepted both 023 ([booking-2906761131-112-se-pl.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761131-112-se-pl.json)) and 022 (booking 2906761149: [booking-2906761149-112-se-pl-payer-022.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761149-112-se-pl-payer-022.json)), 2026-10-05.
The connector therefore accepts 022 and 023 for 112 and keeps the manual's 023 as the default; the catalog's Incoterm codes are untested and reach 112 only through the Combiterm translation.

## Capabilities

| Capability | Notes |
|------------|-------|
| Shipping | Book then print by id in one `shipment/create` call. |
| Rating | Static rate sheet (universal rating mixin); no carrier call. |
| Address validation | `validate_address` over the PostalCodes API route lookup. |
| Product matches | Connector-local lookup (`gateway.proxy.find_product_matches`). |
| Service points | Connector-local lookup (`gateway.proxy.find_service_points`). |

The API Farm has no tracking or cancellation endpoint, so neither capability is advertised.

## PUDO one-click booking

A pickup-and-drop-off (PUDO) booking resolves an eligible service-point product, selects an acceptable service point near the recipient, and books the shipment with its label.
The two lookups are connector-local: karrio has no unified service-points or product-match interface, so the methods are called directly on the proxy and register no connection capability.
They also bypass the SDK origin check, so EU-origin return lanes can be looked up even though the unified rating and shipping entry points reject a shipper country other than the account country (`SHIPPING_SDK_ORIGIN_NOT_SERVICED_ERROR`).

```
  1. address pair (+ optional piece criteria)
     gateway.proxy.find_product_matches()   POST /productapi/v1/productmatches
     → eligible products; pick a service-point product (103/104/109)
  2. recipient address (+ radius, location types, capacity)
     gateway.proxy.find_service_points()    POST /servicepointlocatorapi/v1/servicepoint/findnearestservicepoints
     → normalized points; apply the acceptance policy; pick one
  3. unified ShipmentRequest with the service-point options
     karrio.Shipment.create(...).from_(gateway)   book + print by id
  on AccessPoint-related DHL validation errors, reject the point and retry with the next candidate
```

The service-point products are 103 (Service Point B2C, domestic), 104 (Service Point C2B, domestic), and 109 (Parcel Connect B2C, international).
Only 103 and 109 take an AccessPoint party (see [Access points](#access-points)); the 104 parties table (§5.13 p60) lists none, so 104 books without the service-point options.

### Step 1: eligible products

Product eligibility is authoritative at DHL, while the static rate sheet can drift, so query product matches for the address pair before offering a service choice.

```python
from karrio.providers.dhl_freight_sweden import product_matches

request = product_matches.product_matches_request(
    {
        "shipper": {"postal_code": "11120", "country_code": "SE"},
        "recipient": {"postal_code": "00-251", "country_code": "PL"},
        "parcels": [
            {
                "weight": 2.5,
                "weight_unit": "KG",
                "length": 40,
                "width": 30,
                "height": 15,
                "dimension_unit": "CM",
            }
        ],
    },
    gateway.settings,
)
products, messages = product_matches.parse_product_matches_response(
    gateway.proxy.find_product_matches(request), gateway.settings
)
```

Both `shipper` and `recipient` (postal code and country) are required; the connector raises a field error before any carrier call when one is missing.
`parcels` is optional and takes karrio parcel dicts, the same shape as `ShipmentRequest.parcels`; each becomes one piece criterion.
Parcel fields the lookup does not use (`description`, `items`, `options`, `reference_number`, ...) are ignored.
A parcel without `weight_unit` or `dimension_unit` is read as KG or CM, and LB/IN parcels are converted, so pieces always go out in KG and CM with a volume in m³ when all three dimensions are set.
No `packageType` is sent, because the connector has no mapping from karrio packaging types to DHL package type codes.
The optional scalar keys are shipment totals and the trade direction:

| Key | `MatchCriteria` field | Unit or values |
|-----|-----------------------|----------------|
| `total_weight` | `totalWeight` | kg |
| `total_volume` | `totalVolume` | m³ |
| `total_loading_meters` | `totalLoadingMeters` | loading metres |
| `total_pallet_places` | `totalPalletPlaces` | pallet places |
| `total_number_of_pieces` | `totalNumberOfPieces` | count |
| `import_export` | `importExport` | `E` or `I` |

These keys are passed through to the DHL `MatchCriteria` fields as given, in DHL's metric units, with no conversion.
Any other top-level key raises a field error naming it before any carrier call, so a misspelled or unsupported key (for example `piece` or `services`) is never silently dropped.
Each product carries `code`, `name`, `from_countries`, `to_countries`, `to_country_postal_excludes`, and `rules_for_country_delivery_types`; the delivery-type rules signal whether a product delivers to a service point.

### Step 2: service points

```python
from karrio.providers.dhl_freight_sweden import service_points

request = service_points.service_points_request(
    {
        "address": {
            "street": "Nowogrodzka 31",
            "city": "Warszawa",
            "postal_code": "00-251",
            "country_code": "PL",
        },
        "max_items": 5,
        "location_types": ["servicepoint", "locker"],   # optional
        "distance": {"value": 2, "unit": "km"},         # optional
        "parcel": {                                     # optional
            "weight": 2.5,
            "weight_unit": "KG",
            "length": 40,
            "width": 30,
            "height": 15,
            "dimension_unit": "CM",
        },
    },
    gateway.settings,
)
points, messages = service_points.parse_service_points_response(
    gateway.proxy.find_service_points(request), gateway.settings
)
```

`parcel` is one karrio parcel dict, the parcel the point must fit; the caller chooses which parcel of the shipment to pass, and the connector sends it as the request's `piece` capacity filter.
Parcel fields the lookup does not use (`description`, `items`, `options`, `reference_number`, ...) are ignored.
A parcel without `weight_unit` or `dimension_unit` is read as KG or CM, and an LB/IN parcel is converted, so the capacity filter always goes out in KG and CM.
The accepted top-level keys are `address`, `max_items`, `location_types`, `distance`, and `parcel`.
Any other key, including `parcels` and `piece`, raises a field error naming it before any carrier call.

| Key | Content | Booking use |
|-----|---------|-------------|
| `service_point_id` | unique identifier (e.g. `8005-PL-4516440`) | `dhl_freight_sweden_service_point` (preferred) |
| `id` | a point-type code in some countries (e.g. `101`) | fallback identifier only |
| `name`, `shop_name` | point name | `dhl_freight_sweden_service_point_name` |
| `type` | `servicepoint`, `locker`, `postoffice`, or `postbank` | `locker` books as `ParcelStation`, every other type as `ParcelShop` |
| `address` | `{street, city, postal_code, country_code}` | the four address options |
| `coordinates` | `{latitude, longitude}` | display and sorting |
| `distance`, `distance_unit` | distance from the queried address | ranking |
| `service_types` | carrier service codes | informational |

Filter and rank candidates in this order so the fallback loop has a deterministic list:

1. `service_point_id` is present and the address has all four fields. DHL requires a complete AccessPoint party and does not registry-validate ids or names at booking, so incomplete or invented values misroute rather than fail.
2. Capacity: pass the parcel the point must fit as `parcel`, and keep a local margin check for lockers.
3. Distance: apply a business threshold using `distance` and `distance_unit`.
4. Location type: the connector rejects sub types the destination does not accept (for 109 to DE, `ParcelShop` only), so filter candidates by the [Access points](#access-points) table before booking.
5. Opening hours are not available (Servicepoint API 2.10.0), so do not promise them to recipients.

### Step 3: booking

```python
import karrio.core.models as models

point = accepted_points[0]

payload = {
    "service": "109",                      # or "103" domestic; enum keys also work
    "shipper": SHIPPER_ADDRESS,
    "recipient": RECIPIENT_ADDRESS,        # stays alongside the AccessPoint party
    "parcels": [{"weight": 2.5, "length": 40, "width": 30, "height": 15}],
    "options": {
        "dhl_freight_sweden_service_point": point["service_point_id"],
        "dhl_freight_sweden_service_point_type": (
            "ParcelStation" if point["type"] == "locker" else "ParcelShop"
        ),
        "dhl_freight_sweden_service_point_name": point["name"],
        "dhl_freight_sweden_service_point_street": point["address"]["street"],
        "dhl_freight_sweden_service_point_city": point["address"]["city"],
        "dhl_freight_sweden_service_point_postal_code": point["address"]["postal_code"],
        "dhl_freight_sweden_service_point_country_code": point["address"]["country_code"],
        # optional driver instructions (max 140 characters each):
        # "shipper_instructions" -> pickupInstruction,
        # "recipient_instructions" -> deliveryInstruction
    },
    # lanes leaving the EU VAT area need customs (commodities, incoterm);
    # within it customs data is dropped with a customs_omitted_intra_eu
    # warning. The payer code resolves from dhl_freight_sweden_payer_code,
    # else customs.incoterm, else the product default (see Booking rules);
    # lanes to or from PL, HU, or RO also send SENT, EKAER, or UIT entries
}

details, messages = (
    karrio.Shipment.create(models.ShipmentRequest(**payload))
    .from_(gateway)
    .parse()
)
```

`details.tracking_number` is the transport instruction id, `details.docs.label` the base64 label, and `details.meta["carrier_tracking_link"]` the public tracking URL.
The same options book identically through the server (`POST /api/v1/shipments`).

### Errors and the fallback loop

| Failure | Origin | Action |
|---------|--------|--------|
| "The product matches lookup does not accept ..." / "The service points lookup does not accept ..." | connector field error | send only the lookup's accepted top-level keys (`parcels` for product matches, `parcel` for service points) |
| "requires the full service point details; missing ..." | connector field error | fix the option mapping |
| "accepts only ... access points" / "accepts no access point" | connector field error | pick another sub type or a non-PUDO product |
| "carries the type name ... instead of a service point id" | connector field error | send the id in `dhl_freight_sweden_service_point` |
| payer code, SENT, EKAER, UIT, or GR VAT number/TIN field errors | connector field error | fix the option per [Booking rules](#booking-rules) |
| "Address is mandatory for party AccessPoint" / "Name is mandatory ..." (22001) | DHL validation | reject the candidate, take the next |
| "Accesspoint party is required for product 103" | DHL validation | a service-point product was booked without the options; do not retry as-is |
| linehaul failure without postalCode (22006) | DHL validation | reject the candidate |
| product not offered or zone miss | rating or product matches | fall back to a non-PUDO service or re-quote |

Booking is not idempotent, so retry with the next candidate only when no booking id was returned.

### REST-only variant

A driver that cannot import the connector can split the flow: the lookups go directly to the API Farm, because karrio exposes no REST surface for them, and the booking goes through the karrio REST API.

The hosts are `https://test-api.freight-logistics.dhl.com` (test) and `https://api.freight-logistics.dhl.com` (production), and every call carries the `client-key` header.
Karrio never returns stored connection credentials over REST, so the driver needs the client key through its own secret channel.

The product matches body is the `MatchCriteria` shape that `product_matches_request` builds; both parties are required.
Piece weights are in kg, dimensions in cm, and `volume` in m³:

```json
{
  "parties": [
    {"type": "Consignor", "address": {"countryCode": "SE", "postalCode": "11120"}},
    {"type": "Consignee", "address": {"countryCode": "PL", "postalCode": "00-251"}}
  ],
  "pieces": [{"weight": 2.5, "length": 40, "width": 30, "height": 15, "volume": 0.018}]
}
```

The service points body is the `NearestServicePointRequest` shape, with the piece weight in kg and its dimensions in cm; the 200 body carries `servicePoints` plus in-band `status`/`errorMessage`:

```json
{
  "address": {
    "street": "Nowogrodzka", "cityName": "Warszawa",
    "postalCode": "00-251", "countryCode": "PL"
  },
  "maxNumberOfItems": 5,
  "locationTypes": ["servicepoint", "locker"],
  "distance": 2, "distanceUnit": "km",
  "piece": {"weight": 2.5, "length": 40, "width": 30, "height": 15}
}
```

The driver then does the normalization the connector would: prefer `servicePointId` over `id`, map `locationType` `locker` to `ParcelStation` and every other type to `ParcelShop`, and check the four address fields.

REST booking resolves the connection from the selected rate, so it is rate-first:

```bash
curl -X POST "$KARRIO/v1/proxy/rates" \
  -H "Authorization: Token $KARRIO_TOKEN" -H "Content-Type: application/json" \
  -d '{"shipper": {...}, "recipient": {...}, "parcels": [...],
       "services": ["dhl_freight_sweden_parcel_connect_b2c"]}'

curl -X POST "$KARRIO/v1/proxy/shipping" \
  -H "Authorization: Token $KARRIO_TOKEN" -H "Content-Type: application/json" \
  -d '{"shipper": {...}, "recipient": {...}, "parcels": [...],
       "selected_rate_id": "<id from the rates response>",
       "options": {"dhl_freight_sweden_service_point": "8005-PL-4516440", ...}}'
```

The `services` filter takes karrio service codes (`dhl_freight_sweden_parcel_connect_b2c`), not carrier codes.
The proxy endpoints require `person_name` and `address_line1` on both addresses.
The response carries `tracking_number`, `docs.label` (base64 PDF), and `meta.carrier_tracking_link`; `POST /api/v1/shipments` accepts the same payload when persistent shipment records are wanted.
The error table and fallback loop above apply unchanged.

## Address validation

Home-delivery shipments with product 118 (Hemleverans Paket B2C) are only servable to postal codes with home-delivery coverage, and the transport API does not fully validate postal codes at booking.
`GET /postalcodeapi/v1/postalcodes/{cc}/{pc}/route` resolves a postal code to its route, and the product manual v5.26 (§10.14.7 p235) ties the route's `homeDeliveryParcel` flag to product 118.

```python
details, messages = karrio.Address.validate(
    {
        "address": {"postal_code": "11120", "country_code": "SE"},
        "options": {"service": "dhl_freight_sweden_hemleverans_paket_b2c"},
    }
).from_(gateway).parse()
```

Scoped to product 118 through `options.service` (karrio service code or carrier product code `"118"`), `details.success` reports `homeDeliveryParcel`; unscoped, it reports the route's general `bookable` flag.
`details.complete_address` carries DHL's canonical city for the code.
A failed lookup returns the DHL `ErrorResult` as messages (the live API uses PascalCase `Status`, `ErrorCode`, `UserMessage`; 16010 is "post code not found", 16012 "not supported"; sandbox 16010 response: [lookup-postal-code-se-99999-16010.json](tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-99999-16010.json)).

The `address_validation` connection setting adds the same check to `create_shipment` for product 118 to Swedish consignees:

| Mode | Behavior |
|------|----------|
| `off` (default) | no route lookup |
| `warn` | an unservable route or a 4xx `ErrorResult` adds a message; the shipment is booked |
| `enforce` | an unservable route or a 4xx `ErrorResult` blocks the booking with a field error |

A lookup that produces no verdict (network error, timeout, 5xx) adds a warning and books in both modes, so a PostalCodes API outage cannot block bookings.
Mode values resolve case-insensitively, and a value that names no mode resolves to `off`.
Roll out per connection by moving from `off` to `warn` to `enforce`.

The server builds its reference models at boot, so after deploying a new connector version restart the API before the dashboard's connection dialog shows the option.
`GET /v1/references` must list `connection_configs.dhl_freight_sweden.address_validation` with `type: "string"` and `enum: ["off", "warn", "enforce"]`.

## Operational notes

- The lookups are live carrier calls; cache per address pair when volume justifies it.
- The static rate-sheet prices are placeholders (rate 0.0) overridden by merchant prices; product matches give the authoritative service list.
- Sandbox bookings create real transport instructions in the DHL test system, so keep probes bounded.

## Development

The connector consumes only upstream karrio SDK surface, so the published `karrio` package from PyPI satisfies the runtime dependency.
Its tests import SDK modules such as `karrio.sdk`, `karrio.references`, and `karrio.core.models`, and run from the repository root against an editable SDK checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -v -f tests
```

Create a virtual environment and install the SDK checkout and the connector with `pip install -r requirements-dev.txt -e .`.
`requirements-dev.txt` installs the SDK editable from `../karrio/modules/sdk`; that path is a local checkout of the karrio SDK, and any checkout works for this connector, upstream or fork, because it uses no fork-only SDK surface.
A `git+https` install of the SDK cannot replace the checkout, because pip recursively fetches the monorepo's private submodules that `modules/sdk` does not need.

Type-check the connector with pyright from the repository root:

```bash
pyright
```

`pyrightconfig.json` resolves the SDK from the same `../karrio/modules/sdk` checkout and the project venv from `.venv`, and checks `karrio/` and `sandbox_tests/`.
At runtime `karrio` is a `pkgutil.extend_path` namespace shared by the SDK and this repository, which pyright cannot follow: the SDK's regular `karrio`, `karrio.providers`, `karrio.mappers`, `karrio.schemas`, and `karrio.plugins` packages would shadow this repository's directories.
The empty `__init__.pyi` files in those five directories make them regular packages for pyright, so imports of both the SDK and the connector resolve.
They have no runtime effect and are excluded from the wheel by `[tool.setuptools.exclude-package-data]`, so an installed connector never shadows the SDK's `karrio/__init__.py`.

## Sandbox tests

`sandbox_tests/` holds an opt-in suite that calls the DHL Freight SE sandbox; it sits outside `tests/`, so the default offline run never discovers it, and the wheel does not ship it.
Credentials come from the environment only, so export them from a git-ignored `.env` before running:

```bash
set -a; . ./.env; set +a
DHL_FREIGHT_SWEDEN_SANDBOX=1 .venv/bin/python -m unittest discover -v -s sandbox_tests
```

Every test skips unless `DHL_FREIGHT_SWEDEN_SANDBOX=1` and `KARRIO_DHL_FREIGHT_SWEDEN_CLIENT_KEY` are set, and the booking segments also skip without `KARRIO_DHL_FREIGHT_SWEDEN_ACCOUNT_NUMBER`.
The gateway always runs in test mode on the connector's sandbox host `test-api.freight-logistics.dhl.com`, no variable can change the host, and the run fails if a carrier call targets any other host.

| Variable | Default | Effect |
|----------|---------|--------|
| `DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS` | `lookups` | comma-separated segments to run |
| `DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS` | all | comma-separated product codes the booking segments may book |
| `DHL_FREIGHT_SWEDEN_SANDBOX_COUNTRIES` | all | comma-separated ISO recipient country codes the booking segments may book to |
| `DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS` | `10` | booking attempts allowed in one process |
| `DHL_FREIGHT_SWEDEN_SANDBOX_CAPTURE_DIR` | `$XDG_STATE_HOME/karrio-dhl-freight-sweden/sandbox/<YYYYmmdd-HHMMSS>` | capture directory (`~/.local/state` when `XDG_STATE_HOME` is unset) |

The `lookups` segment books nothing: it checks PostalCodes routes (a valid SE code, the 118 home-delivery flag, and an unknown code), product matches for SE to SE and SE to PL, and the nearest service points for SE and PL, including the parcel capacity filter and `location_types`.
The `booking-approved` segment books 102 within SE, 601 to DK, and 118 within SE behind the `enforce` address validation pre-flight, and prints each label.
The `booking-pudo` segment looks up the service points nearest the recipient and books the first complete candidate as the AccessPoint party, for 103 within SE and 109 from SE to PL with payer code 022 and SENT free.
The `booking-export` segment books 109 to a service point and 112 to the home from SE to PL, RO, HU, and NO, 109 to a ParcelShop in DK, and 112 to the home in FR and GB, declaring the PL lanes SENT free.
Before each booking it checks for free that product matches offer the product for the lane and, for 109, that a nearby service point accepts the product, and it skips the lane otherwise.
NO and GB bookings leave the EU VAT area, so they carry one commodity, an invoice number, and the `dhl_freight_sweden_customs_handling_full_service` option, the customs service that needs no registration identifier; the Incoterm DAP gives payer code 022 on 109, avoiding the joint declaration that 023 requires, and DDP gives 023 on 112.
The `booking-declarations` segment books 601 from SE with payer code DAP and a transport declaration that is not free: to HU with a placeholder `dhl_freight_sweden_ekaer_number`, which sends `EKAER_FREE` `"false"` and `EKAER_NUMBER`, and to RO with `dhl_freight_sweden_uit_free` `false` and no number, which sends `UIT_FREE` `"false"` alone.
It checks product matches for the lane first and skips when 601 is not offered.
The `rejections` segment sends payloads the connector refuses locally and asserts the DHL error code, so the local rules stay anchored to live behaviour: 109 to PL without its SENT entries (22001), 112 to PL with an AccessPoint party (22015), 112 to PL with payer code 1 (22020), and 103 within SE with an AccessPoint party carrying only its id (22001 and 22006).
Each case builds a valid request through the connector and `harness.mutated_request` changes the serialized TransportInstruction just before the call, so connector validation stays intact.
Rejection attempts count against the booking budget, and a response carrying a shipment id fails the test and reports the id as a finding.
The sandbox enforced the capacity filter for PL but returned the same SE points for a 2.5 kg and a 500 kg parcel (2026-10-05: [lookup-service-points-pl-capacity-too-large.json](tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-pl-capacity-too-large.json), [lookup-service-points-se-capacity-not-applied.json](tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-se-capacity-not-applied.json)), so the capacity check runs against PL.

Each booking attempt is counted before the TransportInstruction call, and once the budget is spent the remaining booking tests skip.
To book a single product or lane, narrow the selectors, for example `DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS=booking-approved DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS=102 DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=1`.
Every live call writes its request and response as JSON to the capture directory, with the `client-key` header and the client key redacted.
The account number stays in the captures, because DHL API Farm support traces sandbox bookings by it.
Sandbox bookings cannot be cancelled through the API, so `bookings.jsonl` in the capture directory records the product, shipment id, and timestamp of every attempt.

Planned segments, not yet implemented: a wider customs matrix covering the other customs services and non-EU destinations, and the freight products.

The sandbox findings so far, with every booking, rejection, and deviation from the product manual, are in [docs/notes/sandbox/sandbox-findings.md](docs/notes/sandbox/sandbox-findings.md).
Each finding is backed by an evidence file in [`tests/dhl_freight_sweden/fixtures/sandbox/`](tests/dhl_freight_sweden/fixtures/sandbox/) holding the redacted request and response bodies, the source capture path, and the capture's sha256, and `tests/dhl_freight_sweden/test_sandbox_evidence.py` checks those files offline.
A new sandbox finding gets its own evidence file there before the README or the findings note cites it.
`sandbox_tests/dhl_freight_sweden/evidence.py` builds those files from the captures: its `CATALOG` names each evidence file and the capture files behind it, relative to the state directory.
Rebuilding over the same captures reproduces the committed files byte for byte, so `git diff` after a rebuild shows only new or changed findings:

```bash
.venv/bin/python -m sandbox_tests.dhl_freight_sweden.evidence [--state-root DIR] [--out DIR] [NAME ...]
```

`--state-root` defaults to `$XDG_STATE_HOME` (`~/.local/state` when unset), `--out` to `tests/dhl_freight_sweden/fixtures/sandbox/`, and without names it builds every catalog entry.
