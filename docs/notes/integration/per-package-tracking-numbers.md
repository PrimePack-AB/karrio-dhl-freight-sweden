---
title: "Per-package tracking numbers in shipment meta"
created: 2026-10-13
---

## Status

Implemented on 2026-10-15.
Shipment meta `tracking_numbers` lists one tracking number per parcel: the transport instruction id alone for single-parcel bookings, exactly as before, and the flattened `transportInstruction.pieces[].id` values for multi-parcel bookings when the flattened count equals the parcel count.
Any count mismatch falls back to the transport instruction id, so a response shape without one piece id per parcel keeps the previous behavior.

## Resolved shapes

The two-parcel 102 booking 2906788993 was accepted on the first call, and `transportInstruction.pieces` answered one row per parcel in request order, each with a single-element id list, so the flattened id count equaled the parcel count ([booking fixture](../../../tests/dhl_freight_sweden/fixtures/sandbox/booking-2906788993-102-se-se-two-parcels.json)).
The print call returned one report bundling both parcel labels as a two-page PDF, one 105 × 210 mm page per parcel carrying its piece id as the (00) barcode text and an x/N counter ([label fixture](../../../tests/dhl_freight_sweden/fixtures/sandbox/label-2906788993-102-se-se-two-parcels.json)).

## Implemented rule

The karrio integration guide (`CARRIER_INTEGRATION_GUIDE.md`, "Step 4: Populate Meta Fields") asks for every package tracking number in `tracking_numbers`.
The karrio server writes `tracking_numbers[i]` into each parcel's `reference_number` (`modules/core/karrio/server/core/gateway.py:389` in the karrio fork), so with the single-element list only the first parcel receives a DHL id.

Each `pieces[]` row carries a list of ids and may stand for several identical parcels, so the connector flattens the piece ids in row order and uses them only when their count equals the response's `totalNumberOfPieces`; `tracking_number`, `shipment_identifier`, `shipment_identifiers`, and `docs.label` stay on the transport instruction id and the first print report.
The scope decision keeps single-parcel bookings on `[transport instruction id]` — zero behavior change — rather than promoting their piece id, because every existing single-parcel booking already works against the instruction id.
The offline tests run against `tests/dhl_freight_sweden/fixtures/sandbox/booking-2906788993-102-se-se-two-parcels.json` (two parcels, count match), a mutation of it (count mismatch, both directions), and `tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761222-102-se-se.json` (single parcel).
