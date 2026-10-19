---
title: "Pickups"
---

`karrio.Pickup.schedule` books a pickup through the DHL PickupRequest API, `POST /pickuprequestapi/v1/pickuprequest/pickuprequest` with the same `client-key` header as the other APIs.
The manual offers the API for products 102, 112, 209, 210, 211, 212, 103, 109, 118, and 401 (§10.14.12 p236), and a pickup is needed where no regular pickup is agreed (§5.2 p16).
The connector follows §10.14.12 for 209 as well, although 209's own "APIs" table does not list the PickupRequest API.

The connector creates pickups only.
The API has no update or cancel endpoint and the manual says a booking cannot be cancelled electronically (§5.2 p14), so the proxy defines neither `modify_pickup` nor `cancel_pickup`.
Cancel a pickup with DHL Customer Service.
The karrio server cancels a pickup of a carrier without a cancel endpoint in its own records only, so DHL still sees the pickup as booked.

## Request

The product and the payer code come from the pickup's options, and the connector refuses the request when either is missing; no connection setting supplies them, because one karrio instance may serve several DHL accounts.
The only value taken from the connection is the customer number, chosen per product as for bookings: every product on the §10.14.12 list is booked in DHL's domestic system, so it is `account_number`.

| Option | Type | Meaning |
| ------ | ---- | ------- |
| `dhl_freight_sweden_service` | string | the product, as a code on the §10.14.12 list or its service name, such as `102` or `dhl_freight_sweden_paket` |
| `dhl_freight_sweden_payer_code` | string | the payer code, one of the product's payer codes (for 102: 1, 3, or 4, §5.2 p15) |
| `dhl_freight_sweden_delivery_address` | object | for 212 only, the delivery place as a karrio address object (or its JSON text) with at least `address_line1`, `postal_code`, `city`, and `country_code`; other products ignore it |

The request maps onto the PickupRequest body as follows.

| karrio | PickupRequest |
| ------ | ------------- |
| option `dhl_freight_sweden_service` | `productCode` |
| option `dhl_freight_sweden_payer_code` | `payerCode.code` |
| `pickup_date` and `ready_time` | `pickupDate`, as Swedish local time without an offset, such as `2026-10-20T10:00:00` |
| `instruction` and `package_location` | `pickupInstruction`, joined by `; ` |
| `address` | a `Consignor` party and a `Pickup` party, the latter with the customer number as `id` |
| option `dhl_freight_sweden_delivery_address` (212) | a `Consignee` party, and a `FreightPayer` party at the pickup address with the customer number as `id` |
| each parcel | a `pieces` row with `numberOfPieces` 1, the weight in kg, the volume in m³, and the dimensions in cm at the product's decimals (no volume for 109 and 210, see [Products](../concepts/products.md#piece-measurement-decimals)), and the parcel reference as `marksAndNumbers` |
| all parcels | `totalNumberOfPieces`, `totalWeight` as the sum of the piece weights, and `totalVolume`, the last only when every parcel has a volume |
| `closing_time` | not sent |

A karrio pickup carries one address, so the request for every product but 212 sends no `Consignee` party.
The sandbox accepted a 102 pickup within SE with only the Consignor and the Pickup party, the customer number on the Pickup party ([pickup-421-2026-10-19-12.19.04.489334](../../tests/dhl_freight_sweden/fixtures/sandbox/pickup-421-2026-10-19-12.19.04.489334-102-se-se-no-consignee.json)).
It rejected the customer number on the Consignor party as unknown ([pickup-102-se-se-customer-number-unknown](../../tests/dhl_freight_sweden/fixtures/sandbox/pickup-102-se-se-customer-number-unknown.json)) and accepted it on the Pickup party ([pickup-421-2026-10-19-12.16.37.636333](../../tests/dhl_freight_sweden/fixtures/sandbox/pickup-421-2026-10-19-12.16.37.636333-102-se-se-pickup-party-id.json)).
The sandbox answered the offset-less `pickupDate` `2026-10-20T10:00:00` with `pickupDateTime` `2026-10-20T10:00:00+02:00` in both accepted requests.

## DHL Parti (212)

The manual makes a 212 pickup request carry the complete name and address of the pickup place, at least the address, postal code, and city of the physical delivery place, and the freight payer party with the paying DHL account number (§5.8 p38).
The connector takes the delivery place from the `dhl_freight_sweden_delivery_address` option of each pickup, with no connection setting behind it, and refuses a 212 pickup without it.
It sends the delivery place as the `Consignee` party, since the manual's 212 party table names the receiver CN and adds a DP party only for a delivery address other than CN's (§5.8 p39).
It adds a `FreightPayer` party at the pickup address with the customer number as `id`, while the Consignor keeps no `id` and the Pickup party keeps the customer number.
A territory country code in the delivery place is sent as its parent country, as for the pickup address.

The sandbox accepted a 212 pickup in this shape within SE, with the Consignee at 11151 Stockholm and the FreightPayer party carrying 999999 ([pickup-421-2026-10-19-12.54.33.337335](../../tests/dhl_freight_sweden/fixtures/sandbox/pickup-421-2026-10-19-12.54.33.337335-212-se-se-delivery-place.json)).
It had also accepted a 212 pickup with neither party ([pickup-421-2026-10-19-12.49.01.654345](../../tests/dhl_freight_sweden/fixtures/sandbox/pickup-421-2026-10-19-12.49.01.654345-212-se-se-connector.json)), and the connector follows the manual there.
Neither accepted 212 response carried a `pickupDateTime`, so those pickups have no `pickup_date` or `ready_time`.

The PickupRequest body has no field for the end of the pickup window.
Its nearest field, the `timeDefiniteLoading` additional service, books loading at a set time rather than closing a window, so `closing_time` is not sent.

The connector sends no additional services with a pickup, and no karrio option selects one.
Shipments linked to a pickup in the karrio server do not pass their options to the pickup request.

## Refusals

Each refusal is a `SHIPPING_SDK_FIELD_ERROR` raised before the request is sent.

| Error | Raised when | `details` key |
| ----- | ----------- | ------------- |
| `PickupServiceError` | no `dhl_freight_sweden_service`, or a product outside the §10.14.12 list | `dhl_freight_sweden_service` |
| `PayerCodeError` | no `dhl_freight_sweden_payer_code`, or a code the product does not take | `dhl_freight_sweden_payer_code` |
| `PickupDeliveryAddressError` | a 212 pickup without `dhl_freight_sweden_delivery_address`, with a value that is not an address object or has fields karrio's address does not, or without its `address_line1`, `postal_code`, `city`, or `country_code` (§5.8 p38) | `dhl_freight_sweden_delivery_address` |
| `PickupDateError` | no `pickup_date` or `ready_time`, or one that does not read as YYYY-MM-DD and HH:MM | `pickup_date`, `ready_time` |
| `PickupParcelError` | no parcels, or a parcel without weight, such as the placeholders the karrio server makes from `parcels_count` | `parcels` or `parcels[i].weight` |

## Response

The spec types the response `status` as an integer enum named Accepted, Rejected, Moved, and InternalError, and the sandbox answered `0` for an accepted and `1` for a rejected request.
An accepted answer with a booking number becomes the pickup details, and every other answer becomes messages without details.

| PickupRequest response | karrio |
| ---------------------- | ------ |
| `bookingNumber` | `confirmation_number`, as the text DHL sends, such as `421-2026-10-19-12.19.04.489334` |
| `pickupDateTime` | `pickup_date` and `ready_time` |
| `message` | `meta.message` on an accepted pickup, the message text otherwise |
| `status` other than 0 | a message whose `code` is the status name, such as `Rejected`, with `details.status` holding DHL's value |

DHL's messages are in Swedish, such as "Ej accepterad! Din bokning '11151 Stockholm' har inte accepterats. Angivet kundnr 999999 är okänt." for the rejected request above.
An error body in the shape of the other APIs' error responses becomes one message per validation error.
