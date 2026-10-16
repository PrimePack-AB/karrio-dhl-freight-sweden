"""Karrio DHL Freight product matches (connector-local capability).

The SE API Farm Product API returns the products matching a consignor/
consignee address pair (plus optional piece criteria). Karrio has no unified
product-lookup contract, so this capability is connector-local: the lookup is
reached via ``gateway.proxy.find_product_matches`` and parsed into a stable
list of plain dicts (no generated schema), mirroring the postnord
``service_points`` precedent.
"""

import typing
import karrio.lib as lib
import karrio.core.models as models
import karrio.core.errors as errors
import karrio.providers.dhl_freight_sweden.error as error
import karrio.providers.dhl_freight_sweden.lookup as lookup
import karrio.providers.dhl_freight_sweden.units as provider_units
import karrio.providers.dhl_freight_sweden.utils as provider_utils


class ProductMatchPartiesError(errors.ShippingSDKDetailedError):
    """Raised when a product match query lacks the required address pair."""

    code = "SHIPPING_SDK_FIELD_ERROR"


class ProductNotOfferedError(errors.ShippingSDKDetailedError):
    """Raised before booking when product matches do not offer the product for the lane."""

    code = "SHIPPING_SDK_FIELD_ERROR"


MATCH_PIECE_FIELDS = ("weight", "length", "width", "height", "volume")

ACCEPTED_PAYLOAD_KEYS = frozenset(
    {
        "shipper",
        "recipient",
        "parcels",
        "total_volume",
        "total_number_of_pieces",
        "total_loading_meters",
        "total_pallet_places",
        "total_weight",
        "import_export",
    }
)


def product_matches_request(
    payload: dict,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    """Build a ``MatchCriteria`` body from a lookup payload.

    The endpoint's 200 description requires at least one Consignor and one
    Consignee party (a prose-only rule the API does not validate client-side),
    so incomplete parties fail here with the missing payload keys instead of
    as a carrier error. Top-level keys outside ``ACCEPTED_PAYLOAD_KEYS`` fail
    the same way rather than being silently dropped.

    ``parcels`` are karrio ``Parcel``-shaped dicts sent as KG/CM pieces with
    an m³ volume. No ``packageType`` is sent: the connector has no mapping
    from karrio packaging types to DHL package type codes.
    """
    lookup.guard_payload_keys(payload, ACCEPTED_PAYLOAD_KEYS, "product matches")
    shipper = payload.get("shipper") or {}
    recipient = payload.get("recipient") or {}
    missing = [
        name
        for name, party in (("shipper", shipper), ("recipient", recipient))
        if not (party.get("postal_code") and party.get("country_code"))
    ]

    if any(missing):
        raise ProductMatchPartiesError(
            "The product matches lookup requires a Consignor and a Consignee "
            "party with postal code and country code; "
            f"missing {', '.join(missing)}",
            details={
                name: dict(
                    code="required",
                    message="postal code and country code are required",
                )
                for name in missing
            },
        )

    request = dict(
        parties=[
            dict(
                type="Consignor",
                address=_address_match_criteria(shipper),
            ),
            dict(
                type="Consignee",
                address=_address_match_criteria(recipient),
            ),
        ],
        pieces=[
            lookup.to_metric_measurements(parcel)
            for parcel in payload.get("parcels") or []
        ],
        totalVolume=payload.get("total_volume"),
        totalNumberOfPieces=payload.get("total_number_of_pieces"),
        totalLoadingMeters=payload.get("total_loading_meters"),
        totalPalletPlaces=payload.get("total_pallet_places"),
        totalWeight=payload.get("total_weight"),
        importExport=payload.get("import_export"),
    )

    return lib.Serializable(request, provider_utils.to_dict)


def parse_product_matches_response(
    _response: lib.Deserializable[typing.Union[dict, list]],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.List[dict], typing.List[models.Message]]:
    """Parse a product matches response into normalized product dicts + Messages.

    A successful body is a list of ``ProductMatchResult``; any dict body is
    routed through the shared error parser so the productapi's defensive
    ``BadRequestError`` shape and in-band ``errorMessage`` strings both
    surface as Messages. Any body that is not a list yields at least one
    Message, so a failed lookup never reads as an empty match list.
    """
    response = _response.deserialize()
    matches = response if isinstance(response, list) else []

    products = [
        _normalize_product(match.get("product") or {})
        for match in matches
        if isinstance(match, dict)
    ]
    messages = lib.identity(
        []
        if isinstance(response, list)
        else error.parse_error_response(
            response if isinstance(response, dict) else {}, settings
        )
        or [_unexpected_response(response, settings)]
    )

    return products, messages


def _unexpected_response(
    response: typing.Any, settings: provider_utils.Settings
) -> models.Message:
    return models.Message(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        code="SHIPPING_SDK_INTERNAL_ERROR",
        message=(
            "Unexpected product matches response: expected a JSON array, "
            f"got {lib.to_json(response)[:200]}"
        ),
    )


def _address_match_criteria(party: dict) -> dict:
    return dict(
        countryCode=provider_units.parent_country(party.get("country_code")),
        postalCode=party.get("postal_code"),
    )


def _normalize_product(product: dict) -> dict:
    """Normalize one ``Product`` into the connector dict shape.

    ``shipment``/``piece`` rule summaries pass through with their wire keys
    (``actualWeightMin``, ``lengthMax``, ...) so callers see the API's
    min/max bounds verbatim.
    """
    transportation_mode = product.get("transportationMode") or {}

    return provider_utils.to_dict(
        {
            "code": product.get("code"),
            "name": product.get("name"),
            "short_name": product.get("shortName"),
            "is_domestic": product.get("isDomestic"),
            "active": product.get("active"),
            "is_default": product.get("isDefault"),
            "hidden": product.get("hidden"),
            "from_countries": [
                (item.get("country") or {}).get("countryCode")
                for item in product.get("fromCountries") or []
            ],
            "to_countries": [
                (item.get("country") or {}).get("countryCode")
                for item in product.get("toCountries") or []
            ],
            "to_country_postal_excludes": [
                dict(
                    country_code=(item.get("country") or {}).get("countryCode"),
                    postal_code_excludes=item.get("postalCodeExcludes"),
                )
                for item in product.get("toCountries") or []
                if item.get("postalCodeExcludes")
            ],
            "payer_codes": [
                item.get("code") for item in product.get("payerCodes") or []
            ],
            "transportation_mode": provider_utils.to_dict(
                dict(
                    code=transportation_mode.get("code"),
                    name=transportation_mode.get("name"),
                )
            )
            or None,
            "sub_categories": [
                provider_utils.to_dict(
                    dict(
                        code=item.get("code"),
                        name=item.get("name"),
                    )
                )
                for item in product.get("subCategories") or []
            ],
            "rules_for_country_delivery_types": [
                _normalize_rule(item)
                for item in product.get("rulesForCountryAndDeliveryTypes") or []
            ],
        }
    )


def _normalize_rule(rule: dict) -> dict:
    """Normalize one ``RulesPerDeliveryType`` into a min/max summary entry."""
    return provider_utils.to_dict(
        {
            "country_code": (rule.get("country") or {}).get("countryCode"),
            "delivery_type": (rule.get("deliveryType") or {}).get("code"),
            "shipment": rule.get("shipment"),
            "piece": rule.get("piece"),
        }
    )


class CriteriaUnavailable(typing.NamedTuple):
    """A guarded booking whose parties do not yield product matches criteria."""

    reason: str


def booking_match_criteria(
    request: dict,
) -> typing.Union[dict, CriteriaUnavailable, None]:
    """The ``MatchCriteria`` for a serialized transport instruction.

    The Consignor and Consignee addresses and the piece measurements are
    taken from the transport instruction itself, so territory country codes
    are already their parent country and pieces are in KG/CM/m³. A
    Consignee without country or postal code is matched by the AccessPoint
    party's address, the DP delivery address. Returns None for
    ``PRODUCT_MATCH_UNGUARDED`` products and ``CriteriaUnavailable`` naming
    the missing postal or country code otherwise.
    """
    product = str(request.get("productCode") or "")
    if not product or product in provider_units.PRODUCT_MATCH_UNGUARDED:
        return None

    parties = {
        party.get("type"): (party.get("address") or {})
        for party in request.get("parties") or []
        if party.get("type") in ("Consignor", "Consignee", "AccessPoint")
    }
    consignor = parties.get("Consignor") or {}
    consignee: dict = next(
        (
            address
            for address in (parties.get("Consignee"), parties.get("AccessPoint"))
            if address and _is_matchable(address)
        ),
        parties.get("Consignee") or {},
    )
    consignee_name = lib.identity(
        "consignee or access point" if "AccessPoint" in parties else "consignee"
    )
    missing = next(
        (
            f"no {name} {field}"
            for name, address in (("consignor", consignor), (consignee_name, consignee))
            for key, field in (("countryCode", "country code"), ("postalCode", "postal code"))
            if not address.get(key)
        ),
        None,
    )
    if missing:
        return CriteriaUnavailable(missing)

    return dict(
        parties=[
            dict(
                type=party_type,
                address=dict(
                    countryCode=address["countryCode"],
                    postalCode=address["postalCode"],
                ),
            )
            for party_type, address in (("Consignor", consignor), ("Consignee", consignee))
        ],
        pieces=[
            {
                field: piece[field]
                for field in MATCH_PIECE_FIELDS
                if piece.get(field) is not None
            }
            for piece in request.get("pieces") or []
        ],
    )


def _is_matchable(address: dict) -> bool:
    return bool(address.get("countryCode") and address.get("postalCode"))


def criteria_unavailable_warning(
    unavailable: CriteriaUnavailable, settings: provider_utils.Settings
) -> models.Message:
    """The warning for a guarded booking that proceeds without a lookup."""
    return models.Message(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        code="product_availability_unverified",
        level="warning",
        message=(
            f"Product availability was not verified ({unavailable.reason} for "
            "product matches); the booking proceeded without the check"
        ),
        details=dict(reason=unavailable.reason),
    )


def check_booking_product(
    criteria: dict,
    product: str,
    products: typing.List[dict],
    messages: typing.List[models.Message],
    settings: provider_utils.Settings,
    mode: str,
    separate_agreement: typing.Optional[dict] = None,
) -> typing.List[models.Message]:
    """Apply the booking guard to a product matches answer.

    A lookup that produced messages leaves availability unverified and
    yields a warning in every mode. A product missing from the matched
    codes raises ``ProductNotOfferedError`` in ``enforce`` and yields a
    warning in ``warn``.
    """
    if any(messages):
        return [_unverified_warning(messages, settings)]

    offered = [str(item.get("code")) for item in products if item.get("code")]
    if product in offered:
        return []

    message = _not_offered_message(
        criteria, product, offered, separate_agreement, bool(settings.test_mode)
    )
    if mode == provider_units.ServabilityMode.enforce:
        raise ProductNotOfferedError(
            message,
            details={"service": dict(code="product_not_offered", message=message)},
        )

    return [
        models.Message(
            carrier_name=settings.carrier_name,
            carrier_id=settings.carrier_id,
            code="product_not_offered",
            level="warning",
            message=message,
            details=dict(product=product, offered=offered),
        )
    ]


def lookup_failure(
    exception: Exception, settings: provider_utils.Settings
) -> models.Message:
    """A Message for a product matches lookup that raised instead of answering."""
    return models.Message(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        code="SHIPPING_SDK_INTERNAL_ERROR",
        message=str(exception),
    )


def _not_offered_message(
    criteria: dict,
    product: str,
    offered: typing.List[str],
    separate_agreement: typing.Optional[dict],
    test_mode: bool,
) -> str:
    names = {
        service.value: service.name
        for service in provider_units.ShippingService.__members__.values()
    }
    origin, destination = (
        f"{party['address']['countryCode']} {party['address']['postalCode']}"
        for party in criteria["parties"]
    )
    supported = [f"{code} ({names[code]})" for code in offered if code in names]
    unsupported = [code for code in offered if code not in names]
    listing = ", ".join(
        [
            *supported,
            *lib.identity(
                [
                    f"and {', '.join(unsupported)}, which the connector does not support"
                ]
                if unsupported
                else []
            ),
        ]
    )
    agreement = lib.identity(
        " "
        + provider_units.separate_agreement_message(
            separate_agreement["product"], separate_agreement["country"], test_mode
        )
        if separate_agreement
        else ""
    )

    return (
        f"Product {product} ({names.get(product, product)}) is not offered from "
        f"{origin} to {destination} by DHL product matches; "
        + lib.identity(
            f"offered for this lane: {listing}."
            if offered
            else "no product is offered for this lane."
        )
        + agreement
    )


def _unverified_warning(
    messages: typing.List[models.Message], settings: provider_utils.Settings
) -> models.Message:
    return models.Message(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        code="product_availability_unverified",
        level="warning",
        message=(
            "Product availability was not verified (product matches lookup "
            f"failed: {'; '.join(str(m.message) for m in messages)}); the booking "
            "proceeded without the check"
        ),
        details=dict(errors=[dict(code=m.code, message=m.message) for m in messages]),
    )
