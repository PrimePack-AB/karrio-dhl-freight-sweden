"""Shared payload handling for the connector-local lookups.

The product matches and service points lookups take raw dict payloads
rather than generated karrio models, so these helpers give them a strict
top-level key contract and a karrio ``Parcel``-shaped measurement input
normalized to the KG/CM units the SE API Farm expects.
"""

import typing
import karrio.lib as lib
import karrio.core.models as models
import karrio.core.errors as errors


class UnexpectedPayloadKeysError(errors.ShippingSDKDetailedError):
    """Raised when a lookup payload carries keys its builder does not read."""

    code = "SHIPPING_SDK_FIELD_ERROR"


def guard_payload_keys(
    payload: dict,
    accepted: typing.AbstractSet[str],
    lookup: str,
) -> None:
    """Reject top-level payload keys outside ``accepted`` before any carrier call."""
    unexpected = sorted(set(payload) - set(accepted))

    if any(unexpected):
        raise UnexpectedPayloadKeysError(
            f"The {lookup} lookup does not accept "
            f"{', '.join(unexpected)}; "
            f"accepted keys are {', '.join(sorted(accepted))}",
            details={
                key: dict(code="unexpected", message="unexpected payload key")
                for key in unexpected
            },
        )


def to_metric_measurements(parcel: dict) -> dict:
    """Convert a karrio ``Parcel``-shaped dict into KG/CM wire measurements.

    Missing ``weight_unit``/``dimension_unit`` default to KG/CM instead of
    karrio's LB/IN fallback. Each parcel is converted on its own so mixed
    units across parcels never round-trip through another parcel's units.
    ``volume`` is in m³ and is omitted unless all three dimensions are set.
    """
    package = lib.to_packages(
        [
            typing.cast(
                models.Parcel,
                lib.to_object(
                    models.Parcel,
                    {
                        **parcel,
                        "weight_unit": parcel.get("weight_unit") or "KG",
                        "dimension_unit": parcel.get("dimension_unit") or "CM",
                    },
                ),
            )
        ]
    ).single
    length, width, height = (
        package.length.CM,
        package.width.CM,
        package.height.CM,
    )

    return dict(
        weight=package.weight.KG,
        length=length,
        width=width,
        height=height,
        volume=lib.identity(
            lib.to_decimal(length * width * height / 1_000_000, quant=0.000001)
            if length and width and height
            else None
        ),
    )
