"""Karrio DHL Freight rate API implementation.

The SE API Farm pricequote API is not integrated, so price resolution
is served from Karrio's static-rate mechanism: per-merchant contract prices
live in the server-side RateSheet and are resolved against the connection's
service levels by the universal rating mixin. No carrier call is made.

Rate-sheet zones match whole countries, so rates of products that exclude
the recipient's postal code (``units.POSTAL_CODE_EXCLUSIONS``) are removed
after the universal resolution.
"""

import typing
import karrio.lib as lib
import karrio.core.models as models
import karrio.providers.dhl_freight_sweden.units as provider_units
import karrio.providers.dhl_freight_sweden.utils as provider_utils
from karrio.universal.providers.rating import (
    parse_rate_response as universal_parse_rate_response,
)

__all__ = ["parse_rate_response", "rate_request"]


def rate_request(
    payload: models.RateRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    return lib.Serializable(
        payload,
        lib.identity,
        dict(
            recipient=dict(
                country_code=payload.recipient.country_code,
                postal_code=payload.recipient.postal_code,
            ),
            services=list(payload.services or []),
        ),
    )


def parse_rate_response(
    _response: lib.Deserializable,
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.List[models.RateDetails], typing.List[models.Message]]:
    rates, messages = universal_parse_rate_response(_response, settings)
    ctx = _response.ctx or {}
    recipient = ctx.get("recipient") or {}
    exclusions = {
        rate.service: exclusion
        for rate in rates
        for exclusion in [
            provider_units.excluded_destination(
                provider_units.ShippingService.map(rate.service).value_or_key,
                recipient.get("country_code"),
                recipient.get("postal_code"),
            )
        ]
        if exclusion is not None
    }

    return (
        [rate for rate in rates if rate.service not in exclusions],
        [
            *messages,
            *(
                _excluded_destination_message(service, exclusion, recipient, settings)
                for service, exclusion in exclusions.items()
                if service in (ctx.get("services") or [])
            ),
        ],
    )


def _excluded_destination_message(
    service: str,
    exclusion: provider_units.PostalCodeExclusion,
    recipient: dict,
    settings: provider_utils.Settings,
) -> models.Message:
    return models.Message(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        code="destination_not_supported",
        message=(
            f"the service {service} does not deliver to {exclusion.country} "
            f"postal codes {exclusion.low}-{exclusion.high} ({exclusion.region}) "
            f"and needs a {exclusion.digits}-digit postal code to rule them out"
        ),
        details=dict(
            service=service,
            country_code=recipient.get("country_code"),
            postal_code=recipient.get("postal_code"),
        ),
    )
