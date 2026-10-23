---
title: "Piece volume rounds up to DHL's calculated volume"
created: 2026-10-23
---

## Status

Implemented on 2026-10-23.
This note records the observed rejection, the analysis behind rounding the piece volume up, and the decisions taken.
The `docs/concepts/products.md` measure-decimals section accompanies the implementation.

## Observed rejection

A live 118 SE to SE booking through the karrio server in test mode, with a 10 x 20 x 11 cm piece, was rejected with http 400 and this body, committed as [rejection-22028-118-se-se.json](../../../tests/dhl_freight_sweden/fixtures/live/rejection-22028-118-se-se.json) (operator-captured, the request was not retained):

```json
{
  "http_message": "Bad Request",
  "http_status": 400,
  "status": "Error",
  "validationErrors": [
    {
      "errorCode": 24000,
      "field": "notification",
      "message": "notification is not available for this product."
    },
    {
      "errorCode": 22028,
      "field": "Pieces[0].Volume",
      "message": "Calculated volume 0.003 is larger than given volume 0.002 "
    }
  ]
}
```

The 24000 notification error is the rejection behind the notification guard ([notification-guard.md](notification-guard.md)); the 22028 volume error was set aside there as unrelated and is taken up here.
After the guard landed, a retry of the same booking surfaced the 22028 alone: the connector had sent volume 0.002 for the piece's exact 0.0022 m³, and DHL rejected it because its own calculated volume, 0.003, is larger.

## Analysis

10 x 20 x 11 cm is 2200 cm³, exactly 0.0022 m³.
Half-up rounding at the table's three volume decimals sent 0.002 (the fourth decimal is a 2), while DHL's message reports 0.003: the same value rounded up at three decimals, a step of 0.001 m³ (one liter).
DHL recomputes the volume from the sent dimensions and rejects a given volume below its calculated one.

The understatement was general: any piece whose exact volume is not representable at three decimals with a low fourth decimal left the connector below DHL's calculation, for example the measure-decimals test's 30.5 x 20.0 x 10.6 cm case (0.006466 m³), which sent 0.006 against a calculated 0.007.

## Decisions

- `utils.volume_m3` takes the exact decimal product of the sent dimensions, one `Decimal(str(side))` per side so the arithmetic matches the decimals DHL parses from the request, and quantizes it with `ROUND_CEILING` at the product's volume decimals.
  The sent volume then equals DHL's calculated volume for every input, which passes under every reading of the check (equality, the exact product, or the ceiling), and a positive volume below one liter still goes out as 0.001.
- Weight and dimensions keep half-up rounding: DHL cannot derive weight from the pieces, and the dimensions are the input to its calculation, which the connector already mirrors by computing the volume from the sent dimensions.
- The pickup `totalVolume` follows as the sum of the rounded piece volumes, a sum of ceilings, never below a total DHL could calculate the same way.
- The fixture is operator-captured, not produced by the sandbox_tests evidence tooling, so it lives in `tests/dhl_freight_sweden/fixtures/live/` rather than the suite-produced `fixtures/sandbox/` set, whose schema expects a retained request and tooling source captures; sandbox-outcome claims in README and mounted docs pages keep citing suite-produced fixtures only.

## Test plan

`tests/dhl_freight_sweden/test_measure_decimals.py` gains `test_volume_rounds_up_to_dhls_calculated_volume`: the utils-level volume of a 10 x 20 x 11 cm piece on 118, the booking piece volume, and the pickup `totalVolume` all assert 0.003.
The dimension-decimals case's expected volume for a 30.5 x 20.0 x 10.6 cm piece on 102 changes from 0.006 to 0.007.
