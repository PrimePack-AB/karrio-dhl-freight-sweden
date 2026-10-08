# karrio.dhl_freight_sweden

This package is a [karrio](https://pypi.org/project/karrio) carrier plugin for DHL Freight Sweden.
It books shipments through the DHL Freight (Sweden) API Farm, which authenticates with a single `client-key` header, and returns each shipment with its printed label.
This guide is for a developer or operator integrating Karrio for a Swedish shipper, and its worked examples follow a B2C e-commerce shop that sends single parcels within Sweden, to the EU, and to Norway and Switzerland.

## What it does and does not do

| Capability | How |
| ------------ | ----- |
| Shipping | `karrio.Shipment.create` books a transport instruction and prints its label by id in one call. |
| Rating | A static rate sheet through karrio's universal rating; no carrier call is made. |
| Address validation | `karrio.Address.validate` over the DHL PostalCodes route lookup. |
| Product matches | A connector-local lookup of the products DHL offers for an address pair. |
| Service points | A connector-local lookup of the service points nearest an address. |

The plugin has these limits.
The API Farm has no tracking endpoint, so karrio advertises no tracking capability; `meta.carrier_tracking_link` is a link to DHL's public tracking web page.
You cannot cancel transports via API or EDI. Cancel in your system and contact DHL Customer Service with your shipment number.
The connector sends customs data inside the booking and nothing else: it uploads no documents and sends no email, and the Print call returns only the label.
Labels are PDF only.
The rate sheet's prices are placeholders at 0.0 that a merchant's own prices replace, and product matches, not the rate sheet, tell which products DHL offers for a lane.
Karrio's unified rating and shipping calls accept only shippers in Sweden, the account country.

## Install and register

The plugin needs Python 3.11 or later.

```bash
pip install git+https://github.com/PrimePack-AB/karrio-dhl-freight-sweden.git
```

The package registers through the `karrio.plugins` entry point group under the id `dhl_freight_sweden`, so installing it makes the carrier available to every karrio SDK runtime, and uninstalling it removes the carrier.
A Karrio server builds its reference models at boot, so restart the API after installing or upgrading the plugin.
`GET /v1/references` then lists the connection settings under `connection_configs.dhl_freight_sweden`.

## Connect

A connection needs the client key of a DHL Freight Sweden API Farm account and the DHL customer number, which the connector sends as the consignor's party id.

```python
import karrio.sdk as karrio

gateway = karrio.gateway["dhl_freight_sweden"].create(
    dict(
        client_key="...",
        account_number="...",
        test_mode=True,
        config={"address_validation": "warn"},
    )
)
```

The `config` dict holds these settings.

| Setting | Default | Effect |
| --------- | --------- | -------- |
| `label_type` | `PDF` | Only `PDF` is accepted, in any letter case; any other value fails every booking with `LabelTypeError`. |
| `label_page_type` | `Label` | The Print API page layout: `Label`, `Label2xPortraitA4`, `Label3xLandscapeA4`, `LabelCompact`, or `LabelCompact2x2PortraitA4`. |
| `address_validation` | `off` | `off`, `warn`, or `enforce` the PostalCodes check for 118 bookings, as described under home delivery below. |
| `server_url` | | Overrides the host that `test_mode` selects. |
| `shipping_services` | all | A list of karrio service codes; karrio returns only rates for these services. |
| `shipping_options` | all | A list of option codes that the Karrio server offers on the connection; neither the connector nor the SDK reads it. |

With `test_mode` true the connector calls `https://test-api.freight-logistics.dhl.com`, and otherwise `https://api.freight-logistics.dhl.com`.

## Your first domestic shipment

This request books a DHL Paket (102) parcel from a shop in Stockholm to a home address in Stockholm.

<!-- quoted from examples/domestic_parcel.py -->
```python
def shipment_request() -> models.ShipmentRequest:
    return models.ShipmentRequest(
        service="dhl_freight_sweden_paket",
        shipper=models.Address(
            company_name="Example Shop AB",
            person_name="Sven Svensson",
            address_line1="Kungsgatan 1",
            city="Stockholm",
            postal_code="11143",
            country_code="SE",
            phone_number="+46 8 123 456",
            email="orders@example.se",
        ),
        recipient=models.Address(
            person_name="Anna Andersson",
            address_line1="Drottninggatan 10",
            city="Stockholm",
            postal_code="11151",
            country_code="SE",
            phone_number="+46 70 123 45 67",
            email="anna.andersson@example.se",
            residential=True,
        ),
        parcels=[
            models.Parcel(
                weight=1.0,
                length=30.0,
                width=20.0,
                height=10.0,
                weight_unit="KG",
                dimension_unit="CM",
            )
        ],
        reference="ORDER-1001",
    )
```

Book it with `details, messages = karrio.Shipment.create(shipment_request()).from_(gateway).parse()`.
`details.tracking_number` is the DHL transport instruction id, `details.docs.label` is the base64 PDF label, and `details.meta["carrier_tracking_link"]` is the public tracking page.
`python -m examples.domestic_parcel` prints the TransportInstruction body the connector builds for this request without contacting DHL, and the [service-point](examples/service_point_parcel.py) and [Switzerland](examples/export_to_switzerland.py) examples work the same way.
The Karrio server accepts the same fields at `POST /api/v1/shipments`.

### Labels

The connector prints the label right after booking and returns the first printed report.
The `dhl_freight_sweden_label_page_type` option overrides the `label_page_type` setting for one shipment.
The connector sends `phone_number` as given, and the manual allows exactly one prefix followed by digits, dashes, and spaces only (Appendix E §10.6 p197).
Most labels do not print the receiver's phone number, which the manual forbids for 118 and 401 and for 109 and 112 except to SK (§9.4.2 p170); [Labels](docs/concepts/labels.md) has the evidence per product.

### Home delivery with address validation

Hemleverans Paket B2C (118) delivers only to postal codes with home-delivery coverage, and the booking API does not fully validate postal codes.
The PostalCodes route's `homeDeliveryParcel` flag answers the question for 118 (§10.14.7 p235).

```python
details, messages = karrio.Address.validate(
    {
        "address": {"postal_code": "11120", "country_code": "SE"},
        "options": {"service": "dhl_freight_sweden_hemleverans_paket_b2c"},
    }
).from_(gateway).parse()
```

Scoped to 118 through `options.service`, `details.success` reports `homeDeliveryParcel`; unscoped, it reports the route's `bookable` flag, and `details.complete_address` carries DHL's city for the code.
An unknown code returns DHL's error as a message, such as 16010 "post code not found" ([lookup-postal-code-se-99999-16010.json](tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-se-99999-16010.json)), and a country the route does not cover returns 16009 ([lookup-postal-code-ch-8001-16009.json](tests/dhl_freight_sweden/fixtures/sandbox/lookup-postal-code-ch-8001-16009.json)).

The `address_validation` setting runs the same check before a 118 booking to a Swedish recipient.
With `warn` an unservable route or a DHL error adds a message and the shipment is booked, and with `enforce` it blocks the booking with `PostalCodeNotServableError`.
A lookup with no verdict, such as a timeout or a 5xx answer, adds a warning and books in both modes, so a PostalCodes outage cannot block bookings.
Values are read case-insensitively, a value that names no mode means `off`, and a connection can move from `off` to `warn` to `enforce`.

## Service-point (PUDO) delivery

A service-point booking picks a product that delivers to service points, picks a point near the recipient, and books the shipment to it.
Service Point B2C (103) serves Sweden and Parcel Connect B2C (109) serves the countries in the [access-point table](docs/concepts/booking-rules.md#access-points); Service Point C2B (104) takes no service-point options.

```
  1. gateway.proxy.find_product_matches()   eligible products for the address pair
  2. gateway.proxy.find_service_points()    points near the recipient
  3. karrio.Shipment.create(...)            book to the chosen point
  on a DHL AccessPoint validation error, take the next candidate
```

The two lookups are called on the proxy, because karrio has no unified interface for them, and [Service-point lookups](docs/guides/lookups.md) documents their inputs and outputs and a REST-only variant.

### Find eligible products

```python
from karrio.providers.dhl_freight_sweden import product_matches

request = product_matches.product_matches_request(
    {
        "shipper": {"postal_code": "11143", "country_code": "SE"},
        "recipient": {"postal_code": "00-251", "country_code": "PL"},
        "parcels": [{"weight": 2.5, "length": 40, "width": 30, "height": 15}],
    },
    gateway.settings,
)
products, messages = product_matches.parse_product_matches_response(
    gateway.proxy.find_product_matches(request), gateway.settings
)
```

### Choose a service point

```python
from karrio.providers.dhl_freight_sweden import service_points

request = service_points.service_points_request(
    {
        "address": {"street": "Nowogrodzka 31", "city": "Warszawa",
                    "postal_code": "00-251", "country_code": "PL"},
        "max_items": 5,
        "parcel": {"weight": 2.5, "length": 40, "width": 30, "height": 15},
    },
    gateway.settings,
)
points, messages = service_points.parse_service_points_response(
    gateway.proxy.find_service_points(request), gateway.settings
)
```

Filter and rank the candidates in this order, so that the fallback loop works through a fixed list.

1. Keep points with a `service_point_id` and all four address fields, because DHL does not check ids or names against its registry at booking, so an incomplete or invented point misroutes rather than fails.
2. Pass the parcel the point must fit as `parcel`, and keep a local margin for lockers.
3. Apply your distance limit with `distance` and `distance_unit`.
4. Keep only the sub types the destination accepts, for example ParcelShop only for 109 to DE.
5. Do not promise opening hours, which the Servicepoint API does not return.

### Book to the point

Map the chosen point to the booking options and add them to an ordinary shipment request, as `examples/service_point_parcel.py` does for 103 to point SE-982000.

<!-- quoted from examples/service_point_parcel.py -->
```python
address = point["address"]
return {
    "dhl_freight_sweden_service_point": point["service_point_id"],
    "dhl_freight_sweden_service_point_type": (
        "ParcelStation" if point["type"] == "locker" else "ParcelShop"
    ),
    "dhl_freight_sweden_service_point_name": point["name"],
    "dhl_freight_sweden_service_point_street": address["street"],
    "dhl_freight_sweden_service_point_city": address["city"],
    "dhl_freight_sweden_service_point_postal_code": address["postal_code"],
    "dhl_freight_sweden_service_point_country_code": address["country_code"],
}
```

The recipient address stays on the request beside the AccessPoint party.
When DHL rejects the AccessPoint party, take the next candidate, but only when the response carries no booking id, because booking is not idempotent.

## Choosing a product

Product matches decide what DHL offers on a lane; this catalogue maps karrio service codes to DHL products.

| Karrio service code | DHL code | Product | Lane | Default payer code |
| --------------------- | ---------- | --------- | ------ | -------------------- |
| `dhl_freight_sweden_paket` | 102 | DHL Paket | SE | 1 |
| `dhl_freight_sweden_service_point_b2c` | 103 | Service Point B2C | SE | 1 |
| `dhl_freight_sweden_service_point_c2b` | 104 | Service Point C2B | SE | 3 |
| `dhl_freight_sweden_hemleverans_paket_b2c` | 118 | Hemleverans Paket B2C | SE | 1 |
| `dhl_freight_sweden_home_delivery_b2c` | 401 | Home Delivery B2C | SE | 1 |
| `dhl_freight_sweden_home_delivery_c2b`, `..._c2b_502` | 402, 502 | Home Delivery Return C2B | SE | none |
| `dhl_freight_sweden_special`, `_pall`, `_stycke`, `_parti` | 209, 210, 211, 212 | Special, Pall, Stycke, Parti | SE | 1 |
| `dhl_freight_sweden_parcel_connect_b2c` | 109 | Parcel Connect B2C | international | 022 |
| `dhl_freight_sweden_parcel_connect_plus` | 112 | Parcel Connect Plus | international | 023 |
| `dhl_freight_sweden_home_delivery_international_b2c` | 601 | Home Delivery International B2C | international | none |
| `dhl_freight_sweden_parcel_return_connect_c2b` | 107 | Parcel Return Connect C2B | returns to SE | 001 |
| `dhl_freight_sweden_road_freight_standard`, `_direct`, `_priority` | 202, 205, 233 | Road Freight Standard, Direct, Priority | international | none |
| `dhl_freight_sweden_standard_pallet_international` | SPI | Standard Pallet International | international | none |

Each product section of the manual states minimum piece dimensions, for example 15 × 11 × 2 cm for 102 and 112 and 15 × 11 × 3 cm for 601, and DHL checks them at booking; [Products](docs/concepts/products.md) lists them all.
Home Delivery B2C (401) takes its door access code through `dhl_freight_sweden_doorstep_access_code`.

### Payer codes and Incoterms

The payer code is DHL's terms-of-delivery code.
The connector takes `dhl_freight_sweden_payer_code` when set, else `customs.incoterm` when it is valid for the product, else the product default.
109 and 112 accept only Combiterms, so an Incoterm is translated for them, CPT, CIP, DAP, and DPU to 022 and DDP to 023 (§7.6 p163).
A product without a default, such as 601, needs an explicit payer code or a valid Incoterm, and [Booking rules](docs/concepts/booking-rules.md#payer-codes) has every product's valid codes.

## Exporting

Whether a shipment carries customs data depends on the EU VAT area for goods, not on the EU itself.
Åland, the Canary Islands, Ceuta and Melilla, and the other territories in [Destinations](docs/concepts/destinations.md#the-eu-vat-area) lie outside it, and Northern Ireland lies inside it for goods.

### Inside the EU VAT area

Within the area the connector drops customs data and customs services and adds a `customs_omitted_intra_eu` warning, so a shop can send the same customs data on every order.
Three lanes need an explicit transport declaration that the connector never makes on the shipper's behalf: SENT to or from PL, and EKAER and UIT to or from HU and RO on the products that require them.
Products 202, SPI, and 601 to or from GR need a VAT number or TIN for both parties.
[Booking rules](docs/concepts/booking-rules.md) describes the options for each.

### Outside the EU VAT area

A shipment that crosses the EU VAT area border needs customs data, meaning `customs.commodities`, `customs.invoice`, or `customs.invoice_date`, and the connector refuses one without any of them with `CustomsInformationRequiredError`.
This refusal is the connector's own rule: DHL booked a 109 parcel to Åland without customs data before the rule existed ([booking-2906761917-109-se-fi-aland.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761917-109-se-fi-aland.json)).
A `documents` shipment without commodities needs at least `customs.invoice`.

The customs document needs an invoice number, `customs.invoice` or else the shipment reference, and its date falls back to the shipping date.
Its amount is `customs.duty.declared_value`, or else the sum of the commodity lines (value times quantity) when every line has a value; otherwise no amount is sent.
Commodity currencies must match `customs.duty.currency` or one another, and the procedure code defaults to 1042 unless `dhl_freight_sweden_customs_procedure_code` sets another.

This part of `examples/export_to_switzerland.py` sends a 601 parcel to Zürich with the options and customs data of sandbox booking 2906762477.

<!-- quoted from examples/export_to_switzerland.py -->
```python
options={
    "dhl_freight_sweden_payer_code": "DAP",
    "dhl_freight_sweden_customs_handling_full_service": True,
},
customs=models.Customs(
    incoterm="DAP",
    invoice="INV-1003",
    invoice_date="2026-10-06",
    content_type="merchandise",
    commercial_invoice=True,
    duty=models.Duty(paid_by="recipient", currency="SEK", declared_value=200),
    commodities=[
        models.Commodity(
            title="Cotton T-shirt",
            description="Cotton T-shirt",
            quantity=1,
            weight=0.5,
            weight_unit="KG",
            value_amount=200,
            value_currency="SEK",
            origin_country="SE",
            hs_code="610910",
        )
    ],
),
```

### Customs services

The manual offers four customs services, and the connector sends none unless an option selects it; each carries a DHL fee, and the manual allows only one per shipment.

| Service | Option | Requires | Manual | Sandbox bookings |
| --------- | -------- | ---------- | -------- | ------------------ |
| Customs handling - Full service | `dhl_freight_sweden_customs_handling_full_service` | nothing further | §6.5 p92 | NO with 109, 112, 202, 233, and 601; CH with 601 |
| Customs handling - Standard | `dhl_freight_sweden_customs_handling_standard` | `customs.options.eori_number`; valid to NO and Åland only | §6.6 p94 | NO with 109 and 112 |
| Customs, customers own declaration | `dhl_freight_sweden_customs_own_declaration` | the MRN in `..._own_declaration_id`; a separate agreement | §6.7 p96 | none |
| Customs, joint declaration | `dhl_freight_sweden_customs_joint_declaration` | the SFID in `..._joint_declaration_id`; a separate agreement; NO only | §6.8 p98 | none |

The NO bookings are [109](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761305-109-se-no.json), [112](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761313-112-se-no.json), [202](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762139-202-se-no.json), [233](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762154-233-se-no.json), and [601](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762162-601-se-no.json) with full service, and [109](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762105-109-se-no-standard-customs.json) and [112](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762113-112-se-no-standard-customs.json) with Standard; the CH booking is [601](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762477-601-se-ch.json).
The manual lists each service as one that cannot be combined with the other three (§6.5 p92, §6.6 p94, §6.7 p96, §6.8 p98), and the connector enforces this before booking: across the EU VAT area border, more than one selected service fails with `CustomsServiceCombinationError` keyed by every selected option.
A selected service's missing identifier fails with `CustomsServiceIdentifierError`, and payer code 023 on 109 requires the joint declaration.
VOEC (VAT on e-commerce, NO) is sent from `customs.options.voec_number` and has not been booked in the sandbox.

To or from Åland the connector refuses full service and Standard with `AlandCustomsServiceError`, because DHL rejected both with 24003 ([full service](tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland.json), [Standard](tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland-standard.json)) although the manual lists Åland for Standard.
An Åland shipment therefore sends its customs data without a customs service, which DHL accepted for 109 as booking 2906762592 ([booking-2906762592-109-se-fi-aland-customs.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762592-109-se-fi-aland-customs.json)); the evidence shows that DHL stored the customs data, not how DHL clears it.

### Commercial or proforma invoice

`customs.commercial_invoice` is a field of the Karrio customs model, not a shipping option.
True sends a `CommercialInvoice` document, and false or unset sends a `ProformaInvoice`.
Outside the EU VAT area, content counts as a sale unless `customs.content_type` is `documents`, `gift`, `return_merchandise`, or `sample`, and a sale without `customs.commercial_invoice` true fails with `CommercialInvoiceRequiredError`.
This is the connector's rule, not DHL's, because DHL accepted a proforma invoice on 109 to NO ([booking-2906761305-109-se-no.json](tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761305-109-se-no.json)).

### Sending the invoice copy to DHL

The manual asks for more than the booking carries.
For 109, 112, 202, and 601 it says that customs documents and invoices must be sent by email to <dhlfreight.int.se@dhl.com> (§5.14 p62, §5.3 p18, §5.4 p22, §5.19 p81), and for 109 it asks for two copies of the customs documents on the outside of the package (§5.14 p62).
Each customs handling service also says that the commercial invoice must be sent to DHL (§6.5 p92, §6.6 p94, §6.7 p96).
DHL has not said whether this still applies to API bookings that carry full customs data, and the connector neither emails nor uploads anything, so the shipper must arrange these steps.

### Norway, Switzerland, and Great Britain

The sandbox booked 109 and 112 to NO, with the customs services listed above.
On account 116768 product matches offered HDI, 202, 601, and 233 to CH and none of 109, 112, and 107 ([lookup-product-matches-se-ch-8001.json](tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-8001.json)), and 601 to Zürich was booked as shown above.
The manual lists GB for 109 and 112 only under a separate agreement with DHL (§5.3 p18, §5.14 p63), and DHL rejected 112 to GB for account 116768, which holds none, with 22005 and 22026 ([rejection-22005-112-se-gb.json](tests/dhl_freight_sweden/fixtures/sandbox/rejection-22005-112-se-gb.json)).
[Products](docs/concepts/products.md) has the details for each destination.

## Special territories and excluded postal codes

DHL product matches answered nothing for the territory codes AX, JE, GG, and FO ([AX 22100](tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ax-22100.json)), so the connector sends a territory under its parent country with the postal code as given.

| Territory | Code | Sent as | Outside the EU VAT area | Excluded from |
| ----------- | ------ | --------- | ------------------------- | --------------- |
| Åland | AX | FI | yes | none |
| Jersey, Guernsey | JE, GG | GB | yes | 109, 112, 202, 601 |
| Isle of Man | IM | GB | yes | none |
| Northern Ireland | XI | GB | no | 109, 112 |
| Faroe Islands, Greenland | FO, GL | DK | yes | 109, 112, 202, 233, 601 |
| Canary Islands | IC | ES | yes | 109, 112, 202, 233, 601 |
| Ceuta, Melilla | EA | ES | yes | 202, 233, 601; postal codes 51080 and 52080 from 109 and 112 |

Each product also excludes the postal codes the manual's "Excluded regions/areas" list, such as Svalbard from 109 and 112 and FR 97100-99999 from 112.
An excluded booking fails with `ExcludedDestinationError` keyed by the party's `postal_code`, and rating leaves the product out.
[Destinations](docs/concepts/destinations.md) has the full tables, the postal-code normalisation, and the evidence.

## Options reference

| Option | Type | Purpose |
| -------- | ------ | --------- |
| `dhl_freight_sweden_payer_code` | string | The terms-of-delivery code, see payer codes above |
| `dhl_freight_sweden_service_point`, `..._type`, `..._name`, `..._street`, `..._city`, `..._postal_code`, `..._country_code` | string | The AccessPoint party, see service-point delivery |
| `dhl_freight_sweden_customs_handling_full_service`, `..._standard` | boolean | Customs services, see customs services |
| `dhl_freight_sweden_customs_own_declaration`, `..._joint_declaration` | boolean | Customs services, with the identifier in `..._id` |
| `dhl_freight_sweden_customs_procedure_code` | string, 4 characters | The commodity procedure code, 1042 by default |
| `dhl_freight_sweden_sent_free`, `..._sent_ref`, `..._sent_carkey` | boolean, string | SENT for PL |
| `dhl_freight_sweden_ekaer_free`, `..._ekaer_number`, `..._uit_free`, `..._uit_number` | boolean, string | EKAER for HU and UIT for RO |
| `dhl_freight_sweden_additional_information` | list | Further `additionalInformation` entries |
| `dhl_freight_sweden_qr_code` | boolean | A print QR code for 107 returns from BE, BG, CZ, DE, ES, LU, and PT |
| `dhl_freight_sweden_label_page_type` | string | The page layout for one shipment |
| `dhl_freight_sweden_doorstep_access_code` | integer | The door access code for 401 |
| `dhl_freight_sweden_pickup_instruction`, `..._delivery_instruction` | string, 140 characters | Driver instructions; karrio's `shipper_instructions` and `recipient_instructions` map to them |
| `dhl_freight_sweden_notification`, `..._pre_advice`, `..._tail_lift_unloading` | boolean | DHL additional services; karrio's `email_notification` maps to the first |
| `dhl_freight_sweden_insurance` | number | Insurance value in the `currency` option; karrio's `insurance` maps to it |
| `shipment_date` | date | The shipping date, also the invoice date fallback |

A boolean option accepts true, `"true"`, `"1"`, 1, or `"yes"` and false, `"false"`, `"0"`, 0, or `"no"` (strings in any case), treats null or an empty string as unset, and fails with `OptionValueError` on any other value.
`customs.options` takes `eori_number` for Standard and `voec_number` for VOEC.
No additional service other than the customs services has been sent to the sandbox ([findings](docs/notes/sandbox/sandbox-findings.md#untested)).

## Errors reference

The connector checks these rules before it sends a booking, and each fails with a `SHIPPING_SDK_FIELD_ERROR` whose `details` name the field to fix.

| Error | Raised when | `details` key |
| ------- | ------------- | --------------- |
| `LabelTypeError` | a label type other than PDF | `label_type` or `config.label_type` |
| `OptionValueError` | a boolean option that spells neither true nor false | each such option |
| `CustomsInformationRequiredError` | no customs data across the EU VAT area border | `customs` |
| `CommercialInvoiceRequiredError` | a sale without `customs.commercial_invoice` | `customs.commercial_invoice` |
| `CustomsInvoiceNumberError` | neither `customs.invoice` nor a reference | `customs.invoice` |
| `DeclarationCurrencyError` | commodity currencies that conflict | `customs.commodities.value_currency` |
| `CustomsServiceCombinationError` | more than one customs service across the EU VAT area border | each selected option |
| `CustomsServiceIdentifierError` | a customs service without its EORI, MRN, or SFID | the missing field |
| `AlandCustomsServiceError` | full service or Standard to or from Åland | the option |
| `PayerCodeError` | no valid payer code, or 023 on 109 without the joint declaration | the option, `customs.incoterm`, or `dhl_freight_sweden_customs_joint_declaration` |
| `ServicePointDetailsError` | an incomplete AccessPoint party | the missing service-point option |
| `ServicePointEligibilityError` | a sub type or product without that access point, or a type name as id | the service-point option |
| `ExcludedDestinationError` | an excluded postal code | `shipper.postal_code` or `recipient.postal_code` |
| `SentInformationError`, `TransportDeclarationError` | a missing or contradictory SENT, EKAER, or UIT declaration | the option |
| `PartyTaxIdError` | 202, SPI, or 601 to or from GR without both VAT numbers or TINs | `shipper.federal_tax_id` or `recipient.federal_tax_id` |
| `QrCodeEligibilityError` | a QR code outside 107 from the listed countries | `dhl_freight_sweden_qr_code` |
| `AdditionalInformationError` | an entry without a code, or a SENT, EKAER, or UIT code where its option applies | `dhl_freight_sweden_additional_information` |
| `PostalCodeNotServableError` | `enforce` validation of an unservable 118 postal code | `recipient.postal_code` |
| `ProductMatchPartiesError`, `UnexpectedPayloadKeysError` | a lookup without both parties, or with an unknown key | the party or key |

DHL's own validation errors seen in the sandbox are these.

| Code | Meaning | Evidence |
| ------ | --------- | ---------- |
| 22001 | a mandatory field is missing, such as the AccessPoint name and address or the SENT identifiers | [103](tests/dhl_freight_sweden/fixtures/sandbox/rejection-22001-103-se-access-point-id-only.json), [109 PL](tests/dhl_freight_sweden/fixtures/sandbox/rejection-22001-109-se-pl-without-sent.json) |
| 22005, 22026 | no valid product for the countries | [112 GB](tests/dhl_freight_sweden/fixtures/sandbox/rejection-22005-112-se-gb.json) |
| 22006 | no linehaul for the AccessPoint postal code | [103](tests/dhl_freight_sweden/fixtures/sandbox/rejection-22001-103-se-access-point-id-only.json) |
| 22015 | an AccessPoint party on a product without one | [112 PL](tests/dhl_freight_sweden/fixtures/sandbox/rejection-22015-112-se-pl-access-point.json) |
| 22020 | an invalid payer code, or a chargeable weight under the product minimum | [112 PL](tests/dhl_freight_sweden/fixtures/sandbox/rejection-22020-112-se-pl-payer-code-1.json), [205 NO](tests/dhl_freight_sweden/fixtures/sandbox/rejection-22020-205-se-no.json) |
| 24003 | a customs service not available for the lane | [112 Åland](tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland.json) |

## Operational notes

The lookups are live carrier calls, so cache them per address pair when volume justifies it.
Product eligibility is decided by DHL, while the static rate sheet can drift, so query product matches before offering a service.
A booking that DHL accepted stays booked, so never retry a request that returned a booking id.
Duplicating a shipment in the Karrio dashboard is reported to copy hidden service-point and SENT options that can make a changed service fail; the [working note](docs/notes/ux/duplicate-shipment-carries-connector-options.md) records the report, which is unverified and has no fix yet.
A driver that cannot import the connector can call the lookups over REST and book through the Karrio REST API, as [Service-point lookups](docs/guides/lookups.md#lookups-and-booking-over-rest) describes.

## Optional: nordic_conventions advisories

The separate [nordic_conventions](https://github.com/PrimePack-AB/karrio-advisor-nordic-conventions) plugin adds non-blocking advisories, warnings only, to DHL Freight Sweden and PostNord shipments that leave the EU VAT area.
It needs the shipment advisors hook, which only the karrio fork branch `feat-shipment-advisors` provides; with released karrio it loads but registers no advisors.
Its advice for Åland and its handling of territory codes are known gaps.
Its territory tables match this connector's, and a test in that repository checks the parity.

## Further documentation

The rules cite the DHL Freight (Sweden) product manual, version 5.26, updated 2026-10-01 and valid from 2026-11-01, as `§x.y pN`.
DHL lists the current manual at <https://dhlpaket.se/dashboard/specifications/products/>, and the cited copy of version 5.26 has sha256 `050660c37ba93d1ae9514c50dfa42c2010bc87763ccaff51a740b2526af11b73`.
[Booking rules](docs/concepts/booking-rules.md), [Destinations](docs/concepts/destinations.md), [Products](docs/concepts/products.md), and [Labels](docs/concepts/labels.md) explain each rule with its citation and evidence, and [Service-point lookups](docs/guides/lookups.md) documents the lookups.
Every sandbox claim cites a redacted evidence file in [tests/dhl_freight_sweden/fixtures/sandbox/](tests/dhl_freight_sweden/fixtures/sandbox/), and the [sandbox findings](docs/notes/sandbox/sandbox-findings.md) record every booking, rejection, and deviation from the manual.
[Development](docs/development/index.md) covers setup and tests, and [Sandbox suite and evidence](docs/development/traceability/sandbox-suite.md) covers the opt-in suite that books against the DHL sandbox.
