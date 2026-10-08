"""Karrio DHL Freight address validation (PostalCodes API).

The SE API Farm PostalCodes API resolves a postal code to its delivery
route; the product manual (§10.14.7) ties the route's ``homeDeliveryParcel``
flag to product 118 availability. The unified ``validate_address`` protocol
method and the booking pre-flight share this evaluation.
"""

import attr
import enum
import typing
import karrio.lib as lib
import karrio.core.models as models
import karrio.core.errors as errors
import karrio.providers.dhl_freight_sweden.error as error
import karrio.providers.dhl_freight_sweden.utils as provider_utils
import karrio.providers.dhl_freight_sweden.units as provider_units


# Per-product servability flags on the route response; products without a
# documented flag fall back to the general ``bookable`` flag.
PRODUCT_SERVICABILITY_FLAGS = {"118": "homeDeliveryParcel"}

# PostalCode ErrorResult codes that answer for the postal code itself:
# 16009 country not supported, 16010 not found, 16011 rural (Landsbygd) and
# 16012 not supported. Any other failure leaves the location unverified.
REFUSAL_ERROR_CODES = {16009, 16010, 16011, 16012}

# The API Farm answers 401 for a missing or unknown client key; the answer
# for a key whose application lacks the PostalCode API is not captured, so
# 403 is treated alike.
ACCESS_DENIED_STATUSES = {401, 403}


class RouteOutcome(enum.Enum):
    """What a route lookup establishes about a postal code."""

    servable = "servable"
    refused = "refused"
    access_unavailable = "access_unavailable"
    unverified = "unverified"


class PostalCodeNotServableError(errors.ShippingSDKDetailedError):
    """Raised when the destination postal code is not servable for the product."""

    code = "SHIPPING_SDK_FIELD_ERROR"


class PostalCodeApiUnavailableError(errors.ShippingSDKDetailedError):
    """Raised when the client key's application has no PostalCode API access."""

    code = "SHIPPING_SDK_FIELD_ERROR"


def evaluate_route(route: dict, product: typing.Optional[str] = None) -> bool:
    """Return the servability of a product on a postal-code route response."""
    flag = PRODUCT_SERVICABILITY_FLAGS.get(product or "")
    return bool(route.get(flag or "bookable"))


def to_route_body(value: typing.Any) -> dict:
    """Decode a route-lookup body, mapping a missing or non-object body to {}."""
    body = lib.failsafe(lambda: lib.to_dict(value)) if value else None
    return body if isinstance(body, dict) else {}


def classify_route(route: dict, product: typing.Optional[str] = None) -> RouteOutcome:
    """Classify a decoded route-lookup body for a product."""
    if _is_route(route):
        return lib.identity(
            RouteOutcome.servable
            if evaluate_route(route, product)
            else RouteOutcome.refused
        )
    if _error_code(route) in REFUSAL_ERROR_CODES:
        return RouteOutcome.refused
    if route.get("http_status") in ACCESS_DENIED_STATUSES:
        return RouteOutcome.access_unavailable
    return RouteOutcome.unverified


def check_booking_route(
    response: typing.Optional[lib.Deserializable[dict]],
    settings: provider_utils.Settings,
    mode: str,
) -> typing.List[models.Message]:
    """Apply the booking pre-flight verdict to a route lookup.

    ``warn`` returns the verdict as shipment warnings. ``enforce`` raises
    ``PostalCodeNotServableError`` on a refusal (an unservable product flag
    or a ``REFUSAL_ERROR_CODES`` error) and ``PostalCodeApiUnavailableError``
    when the client key's application has no PostalCode API access, so the
    transport instruction is never sent. A lookup that could not produce a
    verdict — no response, a network error, any other 4xx, a 5xx, or an
    unrecognized body — yields a warning in both modes, so an API outage
    cannot block bookable shipments.
    """
    route = lib.identity(response.deserialize() if response else {})
    product = str((response.ctx.get("service") if response else None) or "")
    outcome = classify_route(route, product)
    enforce = mode == provider_units.ServabilityMode.enforce

    if outcome == RouteOutcome.servable:
        return []
    if outcome == RouteOutcome.unverified:
        return [_unverified_warning(settings)]
    if outcome == RouteOutcome.access_unavailable:
        if enforce:
            message = (
                "PostalCode API not available for this application; "
                "destination servability could not be verified"
            )
            raise PostalCodeApiUnavailableError(
                message,
                details={
                    "recipient.postal_code": dict(
                        code="postal_code_api_unavailable", message=message
                    )
                },
            )
        return [_access_unavailable_warning(route, settings)]

    messages = lib.identity(
        [_servability_warning(route, product, settings)]
        if _is_route(route)
        else error.parse_error_response(route, settings)
    )
    if enforce:
        raise PostalCodeNotServableError(
            messages[0].message,
            details={
                "recipient.postal_code": dict(
                    code="not_servable", message=messages[0].message
                )
            },
        )

    return [attr.evolve(message, level="warning") for message in messages]


def _error_code(route: dict) -> typing.Optional[int]:
    code = error.error_result_fields(route)["error_code"]
    return lib.failsafe(lambda: int(code)) if code is not None else None


def _servability_warning(
    route: dict, product: str, settings: provider_utils.Settings
) -> models.Message:
    flag = PRODUCT_SERVICABILITY_FLAGS.get(product) or "bookable"

    return models.Message(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        code="postal_code_not_servable",
        message=(
            f"Destination postal code {route.get('postalCode')} is not "
            f"servable for product {product} ({flag} is false)"
        ),
        details=dict(postal_code=route.get("postalCode"), product=product),
    )


def _unverified_warning(settings: provider_utils.Settings) -> models.Message:
    return models.Message(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        code="address_validation_unavailable",
        level="warning",
        message=(
            "Destination servability could not be verified (address "
            "validation API error); the booking proceeded without the check"
        ),
    )


def _access_unavailable_warning(
    route: dict, settings: provider_utils.Settings
) -> models.Message:
    return models.Message(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        code="postal_code_api_unavailable",
        level="warning",
        message=(
            "Destination servability could not be verified: the PostalCode "
            "API is not available for this application; the booking "
            "proceeded without the check"
        ),
        details=dict(http_status=route.get("http_status")),
    )


def _access_unavailable_message(
    route: dict, settings: provider_utils.Settings
) -> models.Message:
    return models.Message(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        code="postal_code_api_unavailable",
        level="warning",
        message=(
            "Postal code location could not be verified: the PostalCode API "
            "is not available for this application"
        ),
        details=dict(http_status=route.get("http_status")),
    )


def _unverified_message(settings: provider_utils.Settings) -> models.Message:
    return models.Message(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        code="address_validation_unavailable",
        level="warning",
        message=(
            "Postal code location could not be verified (address validation "
            "API error)"
        ),
    )


def address_validation_request(
    payload: models.AddressValidationRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    """Build a route-lookup params payload from the unified request.

    ``options.service`` scopes the lookup to a product (karrio service code
    or carrier product code, resolved like ``shipment_request`` does) and is
    carried in the context for the response parser.
    """
    address = lib.to_address(payload.address)
    service = payload.options.get("service")
    product = lib.identity(
        provider_units.ShippingService.map(service).value_or_key if service else None
    )

    return lib.Serializable(
        dict(
            country_code=address.country_code,
            postal_code=address.postal_code,
            service=product,
        ),
        provider_utils.to_dict,
        dict(service=product),
    )


def parse_address_validation_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[models.AddressValidationDetails, typing.List[models.Message]]:
    """Parse a PostalCodeRouteInfo into unified address validation details.

    An unscoped lookup reports the general ``bookable`` flag; a lookup scoped
    through ``options.service`` reports the product's flag. A body without
    route fields yields no details and a message: DHL's own error for a
    postal code it refuses, ``postal_code_api_unavailable`` when the client
    key's application has no PostalCode API access, and
    ``address_validation_unavailable`` for any other failure.
    """
    response = _response.deserialize()
    route = response if _is_route(response) else {}
    messages = _lookup_messages(
        classify_route(response, _response.ctx.get("service")), response, settings
    )

    details = lib.identity(
        models.AddressValidationDetails(
            carrier_id=settings.carrier_id,
            carrier_name=settings.carrier_name,
            success=evaluate_route(route, _response.ctx.get("service")),
            # The SDK declares Address fields as `str = None`, an implicit
            # Optional that pyright does not accept for None arguments.
            complete_address=models.Address(
                city=route.get("city"),  # pyright: ignore[reportArgumentType]
                postal_code=(  # pyright: ignore[reportArgumentType]
                    str(route["postalCode"]) if route.get("postalCode") else None
                ),
                country_code=route.get("countryCode"),  # pyright: ignore[reportArgumentType]
            ),
        )
        if route
        else None
    )

    return details, messages


def _lookup_messages(
    outcome: RouteOutcome, response: dict, settings: provider_utils.Settings
) -> typing.List[models.Message]:
    if outcome == RouteOutcome.access_unavailable:
        return [_access_unavailable_message(response, settings)]
    if outcome == RouteOutcome.unverified:
        return [_unverified_message(settings)]
    if outcome == RouteOutcome.refused:
        return error.parse_error_response(response, settings)
    return []


def _is_route(response: typing.Any) -> bool:
    return isinstance(response, dict) and any(
        key in response for key in ("bookable", "homeDeliveryParcel")
    )
