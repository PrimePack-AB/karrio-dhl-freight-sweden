"""Karrio DHL Freight pickup create implementation (PickupRequest API).

The PickupRequest API books a pickup for the products of product manual
v5.26 §10.14.12 p236; a booked pickup cannot be cancelled electronically
(§5.2 p14), so the connector implements create only. A karrio pickup
carries one address, so the request sends it as both the Consignor and the
Pickup party and sends no Consignee; the sandbox accepted that shape with
the customer number on the Pickup party
(tests/dhl_freight_sweden/fixtures/sandbox/
pickup-421-2026-10-19-12.19.04.489334-102-se-se-no-consignee.json) and
rejected the number on the Consignor as unknown
(pickup-102-se-se-customer-number-unknown.json).
"""

import karrio.schemas.dhl_freight_sweden.pickup_request as dhl_freight_sweden_req
import karrio.schemas.dhl_freight_sweden.pickup_response as dhl_freight_sweden_res

import typing
import karrio.lib as lib
import karrio.core.models as models
import karrio.core.errors as errors
import karrio.providers.dhl_freight_sweden.error as error
import karrio.providers.dhl_freight_sweden.shipment.create as provider_create
import karrio.providers.dhl_freight_sweden.utils as provider_utils
import karrio.providers.dhl_freight_sweden.units as provider_units

# ResponseStatus is an integer enum (vendor/se-api-farm/
# pickup-request-api-2.10.0.json); the sandbox answers its position.
RESPONSE_STATUSES = ("Accepted", "Rejected", "Moved", "InternalError")
ACCEPTED = RESPONSE_STATUSES[0]


class PickupServiceError(errors.ShippingSDKDetailedError):
    """Raised when the pickup product is missing or not served by the PickupRequest API."""

    code = "SHIPPING_SDK_FIELD_ERROR"


class PickupParcelError(errors.ShippingSDKDetailedError):
    """Raised when the pickup has no parcels or a parcel without weight."""

    code = "SHIPPING_SDK_FIELD_ERROR"


class PickupDateError(errors.ShippingSDKDetailedError):
    """Raised when the pickup date or ready time is missing or unreadable."""

    code = "SHIPPING_SDK_FIELD_ERROR"


def pickup_request(
    payload: models.PickupRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    options = lib.units.Options(
        payload.options or {}, option_type=provider_units.PickupOption
    )
    service = _pickup_service(options.dhl_freight_sweden_service.state)
    payer_code = _pickup_payer_code(
        service, options.dhl_freight_sweden_payer_code.state
    )
    pickup_date = _pickup_date(payload.pickup_date, payload.ready_time)
    _check_parcels(payload.parcels)
    packages = lib.to_packages(payload.parcels)
    address = lib.to_address(provider_units.with_parent_country(payload.address))
    volumes = [_volume_m3(package) for package in packages]
    instruction = "; ".join(
        text for text in (payload.instruction, payload.package_location) if text
    )

    request = dhl_freight_sweden_req.PickupRequestType(
        productCode=service,
        pickupDate=pickup_date,
        pickupInstruction=instruction or None,
        totalNumberOfPieces=len(packages),
        totalWeight=packages.weight.KG,
        totalVolume=lib.identity(
            round(sum(typing.cast(typing.List[float], volumes)), 3)
            if all(volumes)
            else None
        ),
        payerCode=dhl_freight_sweden_req.PayerCodeType(code=payer_code),
        parties=[
            _party(provider_units.PartyType.Consignor, address),
            _party(
                provider_units.PartyType.Pickup,
                address,
                id=provider_utils.customer_number(service, settings),
            ),
        ],
        pieces=[
            dhl_freight_sweden_req.PieceType(
                marksAndNumbers=package.reference_number,
                numberOfPieces=1,
                weight=package.weight.KG,
                volume=volume,
                width=lib.identity(package.width.CM if package.width.value else None),
                height=lib.identity(
                    package.height.CM if package.height.value else None
                ),
                length=lib.identity(
                    package.length.CM if package.length.value else None
                ),
            )
            for package, volume in zip(packages, volumes)
        ],
    )

    return lib.Serializable(request, provider_utils.to_dict)


def parse_pickup_response(
    _response: lib.Deserializable[dict],
    settings: provider_utils.Settings,
) -> typing.Tuple[typing.Optional[models.PickupDetails], typing.List[models.Message]]:
    response = _response.deserialize()
    body = response if isinstance(response, dict) else {}
    status = _status_name(body.get("status"))

    if status == ACCEPTED and body.get("bookingNumber"):
        return _extract_details(body, settings), []

    messages = error.parse_error_response(body, settings)
    if any(messages):
        return None, messages

    return None, [
        models.Message(
            carrier_id=settings.carrier_id,
            carrier_name=settings.carrier_name,
            code=status or "pickup_not_booked",
            message=body.get("message")
            or "The PickupRequest API answered without a booking number",
            details=lib.identity(
                dict(status=body.get("status"))
                if body.get("status") is not None
                else dict(response=response)
            ),
        )
    ]


def _extract_details(
    data: dict, settings: provider_utils.Settings
) -> models.PickupDetails:
    # to_object returns None only for an empty value, and data carries a bookingNumber.
    pickup = typing.cast(
        dhl_freight_sweden_res.PickupResponseType,
        lib.to_object(dhl_freight_sweden_res.PickupResponseType, data),
    )
    formats = ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"]

    return models.PickupDetails(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        confirmation_number=str(pickup.bookingNumber),
        pickup_date=lib.identity(
            lib.fdate(pickup.pickupDateTime, try_formats=formats)
            if pickup.pickupDateTime
            else None
        ),
        ready_time=lib.identity(
            lib.ftime(pickup.pickupDateTime, try_formats=formats)
            if pickup.pickupDateTime
            else None
        ),
        meta=lib.identity(dict(message=pickup.message) if pickup.message else None),
    )


def _volume_m3(package: lib.units.Package) -> typing.Optional[float]:
    """The package volume in m³ to the 3 volume decimals of the product tables (102: §5.2 p14).

    ``Package.volume.m3`` rounds to 2 decimals, which turns a 30 x 20 x 10 cm
    parcel's 0.006 m³ into 0.01.
    """
    sides = (package.length.CM, package.width.CM, package.height.CM)
    if not all(sides):
        return None

    length, width, height = typing.cast(typing.Tuple[float, float, float], sides)
    return round(length * width * height / 1e6, 3)


def _status_name(status: typing.Any) -> typing.Optional[str]:
    if isinstance(status, int) and 0 <= status < len(RESPONSE_STATUSES):
        return RESPONSE_STATUSES[status]
    if isinstance(status, str) and status in RESPONSE_STATUSES:
        return status

    return None


def _pickup_service(value: typing.Optional[str]) -> str:
    products = ", ".join(provider_units.PICKUP_PRODUCTS)
    field = "dhl_freight_sweden_service"

    if not value:
        raise PickupServiceError(
            f"A pickup needs {field}, the product to pick up; "
            f"the PickupRequest API books {products} "
            f"({provider_units.PICKUP_PRODUCTS_CITATION})",
            details={
                field: dict(code="required", message=f"one of {products} is required")
            },
        )

    service = str(provider_units.ShippingService.map(value).value_or_key)
    if service in provider_units.PICKUP_PRODUCTS:
        return service

    raise PickupServiceError(
        f"Product {service} cannot be picked up through the PickupRequest API, "
        f"which books {products} ({provider_units.PICKUP_PRODUCTS_CITATION})",
        details={field: dict(code="invalid", message=f"valid products: {products}")},
    )


def _pickup_payer_code(service: str, value: typing.Optional[str]) -> str:
    valid_codes = provider_units.PAYER_CODES[service].codes
    codes = ", ".join(valid_codes)
    field = "dhl_freight_sweden_payer_code"

    if not value:
        raise provider_create.PayerCodeError(
            f"A pickup for product {service} needs {field}, one of {codes}",
            details={field: dict(code="required", message=f"one of {codes} is required")},
        )

    if value not in valid_codes:
        raise provider_create.PayerCodeError(
            f"Payer code {value} is not valid for product {service}; valid codes: {codes}",
            details={field: dict(code="invalid", message=f"valid codes: {codes}")},
        )

    return value


def _pickup_date(
    pickup_date: typing.Optional[str], ready_time: typing.Optional[str]
) -> str:
    """The pickup date and ready time as Swedish local time without an offset.

    The sandbox answered the offset-less 2026-10-20T10:00:00 with
    2026-10-20T10:00:00+02:00, keeping the time as Swedish local time
    (pickup-421-2026-10-19-12.16.37.636333-102-se-se-pickup-party-id.json).
    """
    missing = [
        field
        for field, value in (("pickup_date", pickup_date), ("ready_time", ready_time))
        if not value
    ]
    if any(missing):
        raise PickupDateError(
            f"A pickup needs {' and '.join(missing)}",
            details={field: dict(code="required", message="required") for field in missing},
        )

    value = lib.failsafe(
        lambda: lib.fdatetime(
            f"{pickup_date} {ready_time}",
            current_format="%Y-%m-%d %H:%M",
            output_format="%Y-%m-%dT%H:%M:%S",
            try_formats=["%Y-%m-%d %H:%M:%S"],
        )
    )
    if value:
        return value

    raise PickupDateError(
        f"Pickup date {pickup_date} and ready time {ready_time} must read as "
        "YYYY-MM-DD and HH:MM",
        details={
            "pickup_date": dict(code="invalid", message="expected YYYY-MM-DD"),
            "ready_time": dict(code="invalid", message="expected HH:MM"),
        },
    )


def _check_parcels(parcels: typing.List[models.Parcel]) -> None:
    if not parcels:
        raise PickupParcelError(
            "A pickup needs at least one parcel with its weight",
            details={"parcels": dict(code="required", message="at least one parcel")},
        )

    weightless = [index for index, parcel in enumerate(parcels) if not parcel.weight]
    if not weightless:
        return

    raise PickupParcelError(
        "Every parcel of a pickup needs its weight; the PickupRequest API "
        "takes the weight per piece and in total",
        details={
            f"parcels[{index}].weight": dict(code="required", message="weight is required")
            for index in weightless
        },
    )


def _party(
    role: str, address: lib.units.ComputedAddress, id: typing.Optional[str] = None
) -> dhl_freight_sweden_req.PartyType:
    return dhl_freight_sweden_req.PartyType(
        type=role,
        id=id,
        name=address.company_name or address.person_name,
        contactName=address.contact,
        phone=address.phone_number,
        email=address.email,
        address=dhl_freight_sweden_req.AddressType(
            street=address.address_line1,
            additionalAddressInfo=address.address_line2,
            cityName=address.city,
            postalCode=str(address.postal_code) if address.postal_code else None,
            countryCode=address.country_code,
        ),
    )
