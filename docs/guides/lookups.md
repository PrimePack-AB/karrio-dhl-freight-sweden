---
title: "Service-point lookups"
---

The product matches and service points lookups are connector-local: karrio has no unified service-points or product-match interface, so the methods are called directly on the proxy and register no connection capability.
They also bypass the SDK origin check, so EU-origin return lanes can be looked up even though the unified rating and shipping entry points reject a shipper country other than the account country (`SHIPPING_SDK_ORIGIN_NOT_SERVICED_ERROR`).
The README's service-point section walks through the booking flow; this page documents each lookup's inputs and outputs and a driver that uses REST only.
`gateway` below is a gateway created as in the README's connection section.

## Product matches

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

| Key | Required | `MatchCriteria` field | Unit or values |
|-----|----------|-----------------------|----------------|
| `shipper` | yes, with `postal_code` and `country_code` | Consignor party address | |
| `recipient` | yes, with `postal_code` and `country_code` | Consignee party address | |
| `parcels` | no | `pieces`, one per parcel | see [Parcel input](#parcel-input) |
| `total_weight` | no | `totalWeight` | kg |
| `total_volume` | no | `totalVolume` | m³ |
| `total_loading_meters` | no | `totalLoadingMeters` | loading metres |
| `total_pallet_places` | no | `totalPalletPlaces` | pallet places |
| `total_number_of_pieces` | no | `totalNumberOfPieces` | count |
| `import_export` | no | `importExport` | `E` or `I` |

A missing `shipper` or `recipient`, or one without its postal code or country, raises a field error before any carrier call.
The `total_*` and `import_export` keys are shipment totals and the trade direction, passed through to the DHL `MatchCriteria` fields as given, in DHL's metric units, with no conversion.
Any other top-level key raises a field error naming it before any carrier call, so a misspelled or unsupported key (for example `piece` or `services`) is never silently dropped.
Each product carries `code`, `name`, `from_countries`, `to_countries`, `to_country_postal_excludes`, and `rules_for_country_delivery_types`; the delivery-type rules signal whether a product delivers to a service point.

## Service points

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

`parcel` is one karrio parcel dict, the parcel the point must fit (see [Parcel input](#parcel-input)); the caller chooses which parcel of the shipment to pass, and the connector sends it as the request's `piece` capacity filter.
DHL applied the filter for PL but not for SE: in Stockholm a 2.5 kg piece of 40 × 30 × 15 cm and a 500 kg piece of 300 × 200 × 200 cm returned the same ten service points in the same order ([lookup-service-points-se-capacity-not-applied.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-se-capacity-not-applied.json)), while in Warszawa the 500 kg piece was answered with HTTP 400 "The dimensions are too large for servicepoint", and with `locationTypes` `["locker"]` "The dimensions are too large for locationtype locker" ([lookup-service-points-pl-capacity-too-large.json](../../tests/dhl_freight_sweden/fixtures/sandbox/lookup-service-points-pl-capacity-too-large.json)).
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

## Parcel input

Both lookups take karrio parcel dicts, the same shape as `ShipmentRequest.parcels`: product matches a list under `parcels`, each becoming one piece criterion, and service points one parcel under `parcel`.
Parcel fields the lookups do not use (`description`, `items`, `options`, `reference_number`, ...) are ignored.
A parcel without `weight_unit` or `dimension_unit` is read as KG or CM, and an LB/IN parcel is converted, so pieces always go out in KG and CM.
Product matches pieces also carry a volume in m³ when all three dimensions are set, and no `packageType`, because the connector has no mapping from karrio packaging types to DHL package type codes.

## Lookups and booking over REST

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
The README's errors reference and fallback loop apply unchanged.
