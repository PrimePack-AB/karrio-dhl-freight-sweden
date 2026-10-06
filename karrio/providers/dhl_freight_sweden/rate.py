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
            addresses=dict(
                shipper=_address(payload.shipper),
                recipient=_address(payload.recipient),
            ),
            services=list(payload.services or []),
        ),
    )


def _address(address: models.Address) -> dict:
    return dict(country_code=address.country_code, postal_code=address.postal_code)


def parse_rate_response(
    _response: lib.Deserializable,
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.List[models.RateDetails], typing.List[models.Message]]:
    rates, messages = universal_parse_rate_response(_response, settings)
    ctx = _response.ctx or {}
    addresses = ctx.get("addresses") or {}
    excluded = {
        rate.service: hit
        for rate in rates
        for hit in [
            provider_units.excluded_party(
                provider_units.ShippingService.map(rate.service).value_or_key,
                addresses,
            )
        ]
        if hit is not None
    }

    return (
        [rate for rate in rates if rate.service not in excluded],
        [
            *messages,
            *(
                _excluded_destination_message(service, hit, settings)
                for service, hit in excluded.items()
                if service in (ctx.get("services") or [])
            ),
        ],
    )


def _excluded_destination_message(
    service: str,
    excluded: provider_units.ExcludedParty,
    settings: provider_utils.Settings,
) -> models.Message:
    return models.Message(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        code="destination_not_supported",
        message=provider_units.excluded_party_message(
            provider_units.ShippingService.map(service).value_or_key, excluded
        ),
        details=dict(
            service=service,
            party=excluded.party,
            country_code=excluded.exclusion.country,
            postal_code=excluded.postal_code,
        ),
    )
