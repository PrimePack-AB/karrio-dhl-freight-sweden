---
title: "The rate sheet is load-bearing for one-call purchases"
created: 2026-10-12
---

## Status

Verified on 2026-10-12 by reading the karrio monorepo checkout this connector develops against as an editable install (requirements-dev.txt), then at a fork commit dated 2026-10-09.
The five files cited below are identical at fork commit a7355a5c8 (tag `snapshot-2026.10.19.1`).
No karrio server was run; the findings come from code.

## Findings

The SDK facade buys in one call with no rate involved: `Shipment.create` in `karrio/api/interface.py` goes straight to `gateway.proxy.create_shipment`, and `ShipmentRequest` in `karrio/core/models.py` carries `service` and `options` and no rate field.

The karrio server works the sheet behind the scenes.
POST /v1/shipments with `service` set auto-buys through `buy_shipment_label` in `modules/manager/karrio/server/manager/serializers/shipment.py`, and `apply_rate_selection` in `modules/core/karrio/server/core/utils.py` matches the requested service against the shipment's stored rates.
When no stored rate matches the service, the purchase fails with 400, "The service you selected is not available for this shipment."

The dashboard wizard keeps its "Buy shipping label" button disabled until the user fetches rates and selects one (`create_label.tsx` in `packages/core/modules/Shipments`), and the buy call then carries the chosen rate's service or id, so a dashboard purchase always passes through the rate sheet.

## Consequence

The connector's static rate sheet is load-bearing for the one-call purchase path, not cosmetic.
A merchant who replaces the placeholder prices must keep every bookable service listed in the sheet, or one-call purchases of a dropped service fail with the 400 above.
Product matches, not the sheet, still decide which products DHL offers for a lane.
