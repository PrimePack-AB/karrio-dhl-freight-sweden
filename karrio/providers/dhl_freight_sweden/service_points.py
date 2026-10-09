"""Karrio DHL Freight service points (connector-local capability).

The SE API Farm Servicepoint API returns the service points nearest an
address, with optional location-type, distance, and piece-capacity filters.
Karrio has no unified service-point contract, so this capability is
connector-local: the lookup is reached via ``gateway.proxy.find_service_points``
and parsed into a stable list of plain dicts (no generated schema), mirroring
the postnord ``service_points`` precedent.
"""

import typing
import karrio.lib as lib
import karrio.core.errors as errors
import karrio.core.models as models
import karrio.providers.dhl_freight_sweden.error as error
import karrio.providers.dhl_freight_sweden.lookup as lookup
import karrio.providers.dhl_freight_sweden.units as provider_units
import karrio.providers.dhl_freight_sweden.utils as provider_utils


ACCEPTED_PAYLOAD_KEYS = frozenset(
    {"address", "location_types", "max_items", "distance", "parcel", "service"}
)
# Product manual v5.26 §5.12 p57: "Always search for ten closest service
# points to get the most accurat reply."
DEFAULT_MAX_ITEMS = 10
# Product manual v5.26 §10.14.2.2 p232: for 109 only shops and stations with
# service type "parcel:pick-up" can be selected.
REQUIRED_SERVICE_TYPES: typing.Dict[str, str] = {
    provider_units.ShippingService.dhl_freight_sweden_parcel_connect_b2c.name: "parcel:pick-up",
}


class ServicePointServiceError(errors.ShippingSDKDetailedError):
    """Raised when a lookup's ``service`` is not a DHL Freight service name."""

    code = "SHIPPING_SDK_FIELD_ERROR"


def service_points_request(
    payload: dict,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    """Build a ``NearestServicePointRequest`` body from a lookup payload.

    Top-level keys outside ``ACCEPTED_PAYLOAD_KEYS`` raise a field error
    rather than being silently dropped. ``parcel`` is one karrio
    ``Parcel``-shaped dict, chosen by the caller, that the point must fit;
    it is sent in KG/CM as the request ``piece``. ``max_items`` defaults to
    ``DEFAULT_MAX_ITEMS`` when omitted. ``service`` is a karrio service name
    that is not sent to DHL; it rides in the request context so that the
    parser can apply the service's ``REQUIRED_SERVICE_TYPES``.
    """
    lookup.guard_payload_keys(payload, ACCEPTED_PAYLOAD_KEYS, "service points")
    service = payload.get("service")
    if service is not None and service not in provider_units.ShippingService.__members__:
        raise ServicePointServiceError(
            f"The service points lookup does not know the service {service!r}; "
            "pass a DHL Freight service name such as "
            f"{provider_units.ShippingService.dhl_freight_sweden_parcel_connect_b2c.name}",
            details={"service": dict(code="invalid", message="unknown service name")},
        )
    address = payload.get("address") or {}
    distance = payload.get("distance") or {}
    parcel = payload.get("parcel")
    piece = lookup.to_metric_measurements(parcel) if parcel else None

    request = dict(
        address=dict(
            street=address.get("street"),
            streetNumber=address.get("street_number"),
            additionalAddressInfo=address.get("additional_address_info"),
            cityName=address.get("city"),
            postalCode=address.get("postal_code"),
            countryCode=provider_units.parent_country(address.get("country_code")),
        ),
        locationTypes=payload.get("location_types"),
        maxNumberOfItems=lib.identity(
            DEFAULT_MAX_ITEMS
            if payload.get("max_items") is None
            else payload.get("max_items")
        ),
        distance=distance.get("value"),
        distanceUnit=distance.get("unit"),
        piece=(
            dict(
                width=piece["width"],
                height=piece["height"],
                length=piece["length"],
                weight=piece["weight"],
            )
            if piece
            else None
        ),
    )

    return lib.Serializable(request, provider_utils.to_dict, dict(service=service))


def parse_service_points_response(
    _response: lib.Deserializable[typing.Union[dict, list]],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.List[dict], typing.List[models.Message]]:
    """Parse a nearest-service-points response into point dicts + Messages.

    The endpoint signals failures in-band: the 200 body carries ``status`` and
    ``errorMessage``, which the shared error parser turns into Messages (an
    ``errorMessage``-free body parses to no Messages). A body that is not a
    JSON object yields no points and, unless it carries known error shapes,
    an internal-error Message. When the request named a service with a
    required service type, points whose ``serviceTypes`` lack it are dropped.
    """
    response = _response.deserialize()
    body = response if isinstance(response, dict) else {}
    required_service_type = REQUIRED_SERVICE_TYPES.get(
        (_response.ctx or {}).get("service") or ""
    )

    points = [
        _normalize_service_point(point)
        for point in body.get("servicePoints") or []
        if isinstance(point, dict)
        and (
            required_service_type is None
            or required_service_type in (point.get("serviceTypes") or [])
        )
    ]
    messages = error.parse_error_response(response, settings) or lib.identity(
        [] if isinstance(response, dict) else [_unexpected_response(settings)]
    )

    return points, messages


def _unexpected_response(settings: provider_utils.Settings) -> models.Message:
    return models.Message(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        code="SHIPPING_SDK_INTERNAL_ERROR",
        message="Unexpected service point locator response: expected a JSON object",
    )


def _normalize_service_point(point: dict) -> dict:
    """Normalize one ``ServicePointReference`` into the connector dict shape.

    The point carries its location flat (``street``, ``cityName`` and sibling
    address fields, plus ``latitude``/``longitude``); the dict groups them into
    ``address`` and ``coordinates`` so they map one-to-one onto the PUDO
    options. Both identifiers are kept: the sandbox accepts either at booking,
    and which one DHL consumes downstream is unresolved.
    """
    return provider_utils.to_dict(
        {
            "id": point.get("id"),
            "service_point_id": point.get("servicePointId"),
            "name": point.get("name"),
            "shop_name": point.get("shopName"),
            "type": point.get("locationType"),
            "address": provider_utils.to_dict(
                {
                    "street": point.get("street"),
                    "city": point.get("cityName"),
                    "postal_code": point.get("postalCode"),
                    "country_code": point.get("countryCode"),
                }
            )
            or None,
            "coordinates": provider_utils.to_dict(
                {
                    "latitude": point.get("latitude"),
                    "longitude": point.get("longitude"),
                }
            )
            or None,
            "distance": point.get("distance"),
            "distance_unit": point.get("distanceUnit"),
            "service_types": point.get("serviceTypes"),
        }
    )
