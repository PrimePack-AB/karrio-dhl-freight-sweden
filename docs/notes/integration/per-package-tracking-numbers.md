---
title: "Per-package tracking numbers in shipment meta"
created: 2026-10-13
---

## Status

Deferred by user decision on 2026-10-13; the connector still lists only the transport instruction id.
Shipment meta `tracking_numbers` holds the single transport instruction id, the same value as `tracking_number` and `shipment_identifier`.
The two-parcel probe of 2026-10-15 produced the committed multi-parcel fixture the change was waiting for, so the change is unblocked and its test can run against that fixture.

## Resolved shapes

The two-parcel 102 booking 2906788993 was accepted on the first call, and `transportInstruction.pieces` answered one row per parcel in request order, each with a single-element id list, so the flattened id count equaled the parcel count ([booking fixture](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906788993-102-se-se-two-parcels.json)).
The print call returned one report bundling both parcel labels as a two-page PDF, one 105 × 210 mm page per parcel carrying its piece id as the (00) barcode text and an x/N counter ([label fixture](../../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906788993-102-se-se-two-parcels.json)).

## Open direction

The karrio integration guide (`CARRIER_INTEGRATION_GUIDE.md`, "Step 4: Populate Meta Fields") asks for every package tracking number in `tracking_numbers`.
The booking response lists piece ids under `transportInstruction.pieces[].id`, for example in `tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761073-109-se-pl.json`.
The karrio server writes `tracking_numbers[i]` into each parcel's `reference_number` (`modules/core/karrio/server/core/gateway.py:389` in the karrio fork), so with the single-element list only the first parcel receives a DHL id.

Each `pieces[]` row carries a list of ids and may stand for several identical parcels, so mapping piece ids to karrio parcels by position needs a rule.
A candidate rule uses the flattened piece ids only when their count equals the parcel count, as the two-parcel booking answers, and otherwise falls back to the transport instruction id.
The test runs against `tests/dhl_freight_sweden/fixtures/sandbox/booking-2906788993-102-se-se-two-parcels.json`, whose request carries two parcels and whose response lists their two piece ids in request order.
