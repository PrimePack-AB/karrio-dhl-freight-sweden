---
title: "Notification guard: warn and enforce for the booking notification flag"
created: 2026-10-23
---

## Status

Implemented on 2026-10-23.
This note records the observed rejection, the evidence behind the design, the decisions taken with the operator, and the design to implement.
The README settings row and the `docs/concepts/booking-rules.md` section accompany the implementation.

## Observed rejection

A booking on 118 (DHL Hemleverans Paket B2C) within Sweden with the notification flag set was rejected with http 400 and this validation error:

```json
{
  "errorCode": 24000,
  "field": "notification",
  "message": "notification is not available for this product."
}
```

The same body carried a second validation error (22028, `Pieces[0].Volume`), which the operator set aside as unrelated to this work.

Today `email_notification` is an alias of `dhl_freight_sweden_notification`, `shipping_options_initializer` reads it strictly, and `shipment_request` in `karrio/providers/dhl_freight_sweden/shipment/create.py` serializes it as `additionalServices.notification` on every booking with no product gating.
karrio's `sms_notification` has no alias in the connector and is silently dropped, so the rejection can only have come from `email_notification` or the native option name.
`email_notification_to` is likewise unmapped and stays so.

## Evidence

A live `productapi/v1/productmatches` answer for SE to SE, captured 2026-10-23, lists `additionalServices` per product.
`notification` (sv "Avisering", handling code AVI — the consignor assures that the consignee is present at delivery) appears only for 102 (DHL Paket) and 211 (DHL Stycke).
118 lists neither `notification` nor any `deliveryMonitoring*` service.
The "via SMS or e-mail" wording in the answer belongs to the `deliveryMonitoring*` family, whose booking wire (`DeliveryMonitoringOptions`) carries `email` and `smsPhoneNumber` fields; the `notification` boolean itself carries no channel distinction.
The reduced answer was committed as `tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-se-additional-services.json`; the existing `lookup-product-matches-se-se.json` keeps only code, isDomestic, name, and shortName per product.
The response body needs no redaction (catalog constants and catalog ids only) and the request postcodes stay per fixture convention.
The original capture moved to `~/.local/state/karrio-dhl-freight-sweden/productmatches.se_to_se.md`.
No committed fixture today records any product's notification presence: the plain matches fixtures keep only product codes and names, and the customs variant keeps only customs-filtered service codes.

## Decisions

Taken with the operator on 2026-10-23.

- Two-stage: guard the existing `notification` flag now, and treat remapping `sms_notification` and `email_notification` to the `deliveryMonitoring*` services as a separate follow-up decision.
  118 lists no monitoring services either, so the follow-up cannot rescue 118 — consumers there always land in the warn-and-drop path.
- The guard covers notifications only; `preAdvice` and `tailLiftUnloading` stay unguarded as today.
- Capability comes dynamically from the product-matches answer the connector already fetches, not from a static per-product table.
- The setting is tri-state off/warn/enforce, default enforce, matching `product_matches` and `address_validation`.
- The guard triggers on truthy state only; an explicit `false` passes through untouched, since only `true` is evidenced and DHL's behavior on `false` is unrecorded.

## Design

A new `notifications` member on `ConnectionConfig` (`lib.OptionEnum("notifications", ServabilityMode, default="enforce")`) publishes to the dashboard dropdown through the existing `connection_configs` registration, and `_preflight_mode` normalizes unrecognized values to off.
`sms_notification` joins `email_notification` as an alias of `dhl_freight_sweden_notification`.

- enforce: refuse before the booking POST with a new `NotificationNotOfferedError` (`SHIPPING_SDK_FIELD_ERROR`, details key `notification`, message code `notification_not_offered`) naming the product, the lane, the triggering option, and that the product's matches answer lists no notification service.
- warn: strip `additionalServices.notification` from the serialized request, book, and append a `notification_not_offered` warning message — the option is a preference, not a requirement.
- off: no check; the flag passes through verbatim, which is today's behavior.
- A product that offers notification: the flag is sent with no warning in every mode.
- No answer in hand, because the matches lookup did not run or failed: book, in warn and enforce alike, with a `notification_availability_unverified` warning, mirroring `product_availability_unverified`; enforce refuses only on positive evidence.
- Products in `PRODUCT_MATCH_UNGUARDED` skip the guard silently, mirroring the matches guard.

The guard lives in `create_shipment` on the proxy beside `_product_match_messages`, before the booking POST, because only the proxy performs the matches lookup.
The lookup is factored into a helper shared by both guards so a booking performs at most one matches HTTP call, exactly as today, and the notification guard consults the answer only when the option is truthy, its mode is not off, and the product is not unguarded.
The matches verdict runs first, so a matches refusal wins over a notification refusal.
`_normalize_product` in `karrio/providers/dhl_freight_sweden/product_matches.py` gains an `additional_services` key carrying the per-product service codes, which the reduced committed fixtures currently drop.

## Out of scope

The `deliveryMonitoring*` remap is the recorded follow-up decision, not implemented by this change.
The 22028 volume validation error from the same rejection body was set aside by the operator as unrelated and is recorded nowhere else.

## Test plan

`tests/dhl_freight_sweden/test_notification_guard.py` mirrors `test_product_match_guard.py`: the default mode is enforce; off performs no check; enforce refuses with the message and details above; warn strips the serialized flag and warns; a 102 booking sends the flag with no warning; `PRODUCT_MATCH_UNGUARDED` products skip; a starved or failed lookup warns `notification_availability_unverified`.
`test_option_flags.py` gains a strict-read test for the `sms_notification` alias, and `test_services.py`'s `unified_aliases` set gains `sms_notification`.
`tests/dhl_freight_sweden/fixture.py` keeps `product_matches` off, so no existing mocked answer shifts, and no committed fixture sets the notification flag today.
