---
title: "Per-package tracking numbers in shipment meta"
created: 2026-10-13
---

## Status

Deferred by user decision on 2026-10-13.
Shipment meta `tracking_numbers` holds the single transport instruction id, the same value as `tracking_number` and `shipment_identifier`.

## Open direction

The karrio integration guide (`CARRIER_INTEGRATION_GUIDE.md`, "Step 4: Populate Meta Fields") asks for every package tracking number in `tracking_numbers`.
The booking response lists piece ids under `transportInstruction.pieces[].id`, for example in `tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761073-109-se-pl.json`.
The karrio server writes `tracking_numbers[i]` into each parcel's `reference_number` (`modules/core/karrio/server/core/gateway.py:389` in the karrio fork), so with the single-element list only the first parcel receives a DHL id.

Each `pieces[]` row carries a list of ids and may stand for several identical parcels, so mapping piece ids to karrio parcels by position needs a rule.
A candidate rule uses the flattened piece ids only when their count equals the parcel count and otherwise falls back to the transport instruction id.
A change would need a test against a committed multi-parcel sandbox fixture.
