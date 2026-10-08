"""Karrio DHL Freight rate API implementation.

The SE API Farm pricequote API is not integrated, so price resolution
is served from Karrio's static-rate mechanism: per-merchant contract prices
live in the server-side RateSheet and are resolved against the connection's
service levels by the universal rating mixin. No carrier call is made.

Territory country codes are rated as their parent country
(``units.TERRITORY_PARENTS``). Rate-sheet zones match only the recipient
country, so after the universal resolution the rates of products that do
not serve the shipper-to-recipient lane (``units.PRODUCT_LANES``) or that
exclude a party's postal code (``units.POSTAL_CODE_EXCLUSIONS``) are
removed. A party without a postal code is not checked in rating; booking
requires one.
"""

import typing

import attr
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
    shipper = provider_units.with_parent_country(payload.shipper)
    recipient = provider_units.with_parent_country(payload.recipient)

    return lib.Serializable(
        attr.evolve(payload, shipper=shipper, recipient=recipient),
        lib.identity,
        dict(
            addresses=dict(
                shipper=_address(shipper),
                recipient=_address(recipient),
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
    universal_rates, messages = universal_parse_rate_response(_response, settings)
    ctx = _response.ctx or {}
    addresses = ctx.get("addresses") or {}
    requested = ctx.get("services") or []
    origin = (addresses.get("shipper") or {}).get("country_code")
    destination = (addresses.get("recipient") or {}).get("country_code")
    unserved = [
        service
        for service in requested
        if not provider_units.lane_served(_product_code(service), origin, destination)
    ]
    rates = [
        rate
        for rate in universal_rates
        if provider_units.lane_served(_product_code(rate.service), origin, destination)
    ]
    excluded = {
        rate.service: hit
        for rate in rates
        for hit in [
            provider_units.excluded_party(
                _product_code(rate.service),
                addresses,
                skip_missing=True,
            )
        ]
        if hit is not None
    }

    return (
        [rate for rate in rates if rate.service not in excluded],
        [
            *(
                message
                for message in messages
                if message.message not in _universal_destination_messages(unserved)
            ),
            *(
                _unserved_lane_message(service, origin, destination, settings)
                for service in unserved
            ),
            *(
                _excluded_destination_message(service, hit, settings)
                for service, hit in excluded.items()
                if service in requested
            ),
        ],
    )


def _universal_destination_messages(services: typing.List[str]) -> typing.Set[str]:
    """The rating mixin's messages superseded by an unserved-lane message."""
    return {
        f"the service {service} does not cover the requested destination"
        for service in services
    }


def _product_code(service: str) -> str:
    return provider_units.ShippingService.map(service).value_or_key


def _unserved_lane_message(
    service: str,
    origin: typing.Optional[str],
    destination: typing.Optional[str],
    settings: provider_utils.Settings,
) -> models.Message:
    return models.Message(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        code="destination_not_supported",
        message=provider_units.unserved_lane_message(
            _product_code(service), origin, destination
        ),
        details=dict(service=service, origin=origin, destination=destination),
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
