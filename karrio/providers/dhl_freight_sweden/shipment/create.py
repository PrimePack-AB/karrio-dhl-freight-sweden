"""Karrio DHL Freight shipment API implementation."""

import karrio.schemas.dhl_freight_sweden.transport_instruction_request as dhl_freight_sweden_req
import karrio.schemas.dhl_freight_sweden.transport_instruction_response as dhl_freight_sweden_res
import karrio.schemas.dhl_freight_sweden.print_request as dhl_freight_sweden_print
import karrio.schemas.dhl_freight_sweden.print_response as dhl_freight_sweden_report

import base64
import datetime
import typing
import karrio.lib as lib
import karrio.core.models as models
import karrio.core.units as units
import karrio.core.errors as errors
import karrio.providers.dhl_freight_sweden.error as error
import karrio.providers.dhl_freight_sweden.utils as provider_utils
import karrio.providers.dhl_freight_sweden.units as provider_units


class DeclarationCurrencyError(errors.ShippingSDKDetailedError):
    """Raised when commodity value currencies conflict with the declaration."""

    code = "SHIPPING_SDK_FIELD_ERROR"


class CustomsServiceIdentifierError(errors.ShippingSDKDetailedError):
    """Raised when a selected customs service lacks its required identifier."""

    code = "SHIPPING_SDK_FIELD_ERROR"


class CustomsInvoiceNumberError(errors.ShippingSDKDetailedError):
    """Raised when a customs document has neither invoice number nor reference."""

    code = "SHIPPING_SDK_FIELD_ERROR"


class ServicePointDetailsError(errors.ShippingSDKDetailedError):
    """Raised when an access point party is missing service point details."""

    code = "SHIPPING_SDK_FIELD_ERROR"


class ServicePointEligibilityError(errors.ShippingSDKDetailedError):
    """Raised when the product or destination accepts no such access point."""

    code = "SHIPPING_SDK_FIELD_ERROR"


class AdditionalInformationError(errors.ShippingSDKDetailedError):
    """Raised when a pass-through additionalInformation entry is invalid."""

    code = "SHIPPING_SDK_FIELD_ERROR"


class PayerCodeError(errors.ShippingSDKDetailedError):
    """Raised when no payer code valid for the product can be resolved."""

    code = "SHIPPING_SDK_FIELD_ERROR"


class SentInformationError(errors.ShippingSDKDetailedError):
    """Raised when the SENT options for a lane to or from PL are inconsistent."""

    code = "SHIPPING_SDK_FIELD_ERROR"


class TransportDeclarationError(errors.ShippingSDKDetailedError):
    """Raised when the EKAER (HU) or UIT (RO) options are missing or inconsistent."""

    code = "SHIPPING_SDK_FIELD_ERROR"


def parse_shipment_response(
    _response: lib.Deserializable[typing.List[dict]],
    settings: provider_utils.Settings,
) -> typing.Tuple[models.ShipmentDetails, typing.List[models.Message]]:
    # The proxy appends address-validation warning messages as optional
    # trailing elements after the booking and print bodies.
    booking, printed, *warnings = _response.deserialize()
    customs_omitted = (_response.ctx or {}).get("customs_omitted")
    messages = [
        *error.parse_error_response([booking, printed], settings),
        *(lib.to_object(models.Message, warning) for warning in warnings),
        *lib.identity(
            [_customs_omitted_message(customs_omitted, settings)]
            if customs_omitted
            else []
        ),
    ]

    instruction = (booking or {}).get("transportInstruction") or {}
    tracking_number = instruction.get("id")
    details = lib.identity(
        _extract_details(instruction, printed, tracking_number, settings)
        if tracking_number
        else None
    )

    return details, messages


def _customs_omitted_message(
    countries: dict,
    settings: provider_utils.Settings,
) -> models.Message:
    dropped_services = countries.get("dropped_services") or []

    return models.Message(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        code=provider_units.CUSTOMS_OMITTED_INTRA_EU,
        level="warning",
        message=(
            "Customs data was not sent: the shipment from "
            f"{countries['shipper_country_code']} to "
            f"{countries['recipient_country_code']} stays within the EU VAT area"
            + lib.identity(
                f"; dropped customs services: {', '.join(dropped_services)}"
                if any(dropped_services)
                else ""
            )
        ),
        details=countries,
    )


def _extract_details(
    instruction_data: dict,
    printed: typing.Optional[dict],
    tracking_number: str,
    settings: provider_utils.Settings,
) -> models.ShipmentDetails:
    instruction = lib.to_object(
        dhl_freight_sweden_res.TransportInstructionType, instruction_data
    )
    product_code = instruction.productCode if instruction else None
    result = lib.to_object(dhl_freight_sweden_report.PrintResponseType, printed)
    report = next(iter(result.reports or []), None) if result else None

    return models.ShipmentDetails(
        carrier_id=settings.carrier_id,
        carrier_name=settings.carrier_name,
        tracking_number=tracking_number,
        shipment_identifier=tracking_number,
        label_type=_label_type(report, settings),
        docs=models.Documents(label=getattr(report, "content", None) or ""),
        meta=dict(
            carrier_tracking_link=settings.tracking_url.format(tracking_number),
            product_code=str(product_code) if product_code is not None else None,
        ),
    )


# The Print API has no raster-format parameter, so the emitted document
# format is governed by the DHL account and is identified from the decoded
# report bytes' magic prefix (live-verified PDF A4, 2026-09-10).
LABEL_MAGICS: typing.Tuple[typing.Tuple[bytes, str], ...] = (
    (b"%PDF-", "PDF"),
    (b"^XA", "ZPL"),
)
CONTENT_TYPE_LABELS: typing.Tuple[typing.Tuple[str, str], ...] = (
    ("pdf", "PDF"),
    ("zpl", "ZPL"),
    ("png", "PNG"),
)


def _label_type(report, settings: provider_utils.Settings) -> str:
    prefix = (
        lib.failsafe(
            lambda: base64.b64decode(getattr(report, "content", None) or "")[:16].strip()
        )
        or b""
    )
    content_type = (getattr(report, "contentType", None) or "").lower()

    return (
        next((label for magic, label in LABEL_MAGICS if prefix.startswith(magic)), None)
        or next(
            (label for keyword, label in CONTENT_TYPE_LABELS if keyword in content_type),
            None,
        )
        or settings.connection_config.label_type.state
        or "PDF"
    )


def shipment_request(
    payload: models.ShipmentRequest,
    settings: provider_utils.Settings,
) -> lib.Serializable:
    shipper = lib.to_address(payload.shipper)
    recipient = lib.to_address(payload.recipient)
    packages = lib.to_packages(payload.parcels)
    service = provider_units.ShippingService.map(payload.service).value_or_key
    options = lib.to_shipping_options(
        payload.options,
        package_options=packages.options,
        initializer=provider_units.shipping_options_initializer,
    )

    payer_code = _payer_code(
        service,
        options,
        payload.customs.incoterm if payload.customs else None,
        shipper.country_code,
        recipient.country_code,
    )
    # lib.fdate declares `date_str: str = None` and returns None for None.
    shipping_date = lib.fdate(payload.options.get("shipment_date"))  # pyright: ignore[reportArgumentType]
    procedure_code = (
        options.dhl_freight_sweden_customs_procedure_code.state or "1042"
    )
    service_point_party = _service_point_party(
        options, service, recipient.country_code
    )
    lane_countries = {shipper.country_code, recipient.country_code}
    additional_information = [
        *_sent_information(options, lane_countries),
        *_transport_declarations(
            options, service, lane_countries, recipient.country_code
        ),
        *_additional_information(
            options.dhl_freight_sweden_additional_information.state or [],
            _typed_information_codes(lane_countries),
        ),
    ]
    customs_options = lib.to_customs_info(
        payload.customs, option_type=provider_units.CustomsOption
    ).options
    page_type = provider_units.PageType.map(
        options.dhl_freight_sweden_label_page_type.state
        or settings.connection_config.label_page_type.state
        or provider_units.PageType.Label.value
    ).value_or_key
    has_customs_data = bool(
        payload.customs
        and any(
            [
                payload.customs.commodities,
                payload.customs.invoice,
                payload.customs.invoice_date,
            ]
        )
    )
    # Callers may send customs data maximally; within the EU VAT area no
    # customs declaration is required, so customs information and the priced
    # customs services are dropped instead of validated.
    within_eu_vat_area = all(
        provider_units.in_eu_vat_area(address.country_code, address.postal_code)
        for address in (shipper, recipient)
    )
    requested_customs_services = _customs_services(options, customs_options)
    customs_services = lib.identity(
        {} if within_eu_vat_area else requested_customs_services
    )
    customs_omitted = within_eu_vat_area and any(
        [
            has_customs_data,
            payload.customs and payload.customs.options,
            requested_customs_services,
        ]
    )
    if not within_eu_vat_area:
        _check_customs_service_identifiers(options, customs_options)
    customs = lib.identity(
        _customs_information(
            payload.customs,
            customs_options,
            shipper.country_code,
            recipient.country_code,
            procedure_code,
            payload.reference,
            shipping_date,
        )
        if has_customs_data and not within_eu_vat_area
        else None
    )

    parties = [
        # The consignor id is the customer/agreement number and is mandatory
        # according to the payer code; the consignor-pays default always needs it.
        _party(
            provider_units.PartyType.Consignor, shipper, id=settings.account_number
        ),
        _party(provider_units.PartyType.Consignee, recipient),
        *lib.identity([service_point_party] if service_point_party else []),
    ]

    request = dhl_freight_sweden_req.TransportInstructionRequestType(
        # productCode is generated as Optional[int]; the SPI product and codes
        # such as 402/502 must serialize as strings on the wire.
        productCode=str(service),  # pyright: ignore[reportArgumentType]
        shippingDate=shipping_date,
        pickupInstruction=options.dhl_freight_sweden_pickup_instruction.state,
        deliveryInstruction=options.dhl_freight_sweden_delivery_instruction.state,
        totalNumberOfPieces=len(packages),
        totalWeight=packages.weight.KG,
        references=lib.identity(
            [
                dhl_freight_sweden_req.ReferenceType(
                    # DHL Freight (Sweden) shipment-level reference qualifiers
                    # (product manual appendix E); the qualifier is limited to
                    # 3 characters and karrio's reference is the consignor's.
                    qualifier="CU",
                    value=payload.reference,
                )
            ]
            if payload.reference
            else []
        ),
        payerCode=lib.identity(
            dhl_freight_sweden_req.PayerCodeType(code=payer_code) if payer_code else None
        ),
        parties=parties,
        pieces=[
            dhl_freight_sweden_req.PieceType(
                # packageType/goodsType are product-documentation dependent and
                # not enumerated in the API Farm spec, so they are omitted.
                marksAndNumbers=package.reference_number,
                numberOfPieces=1,
                weight=package.weight.KG,
                volume=lib.failsafe(lambda: package.volume.m3),
                width=lib.identity(package.width.CM if package.width.value else None),
                height=lib.identity(
                    package.height.CM if package.height.value else None
                ),
                length=lib.identity(
                    package.length.CM if package.length.value else None
                ),
            )
            for package in packages
        ],
        additionalServices=dhl_freight_sweden_req.AdditionalServicesType(
            notification=options.dhl_freight_sweden_notification.state,
            preAdvice=options.dhl_freight_sweden_pre_advice.state,
            tailLiftUnloading=options.dhl_freight_sweden_tail_lift_unloading.state,
            doorstepDelivery=lib.identity(
                dhl_freight_sweden_req.DoorstepDeliveryType(
                    accessCode=options.dhl_freight_sweden_doorstep_access_code.state
                )
                if options.dhl_freight_sweden_doorstep_access_code.state is not None
                else None
            ),
            insurance=lib.identity(
                dhl_freight_sweden_req.InsuranceType(
                    value=options.dhl_freight_sweden_insurance.state,
                    currency=options.currency.state,
                )
                if options.dhl_freight_sweden_insurance.state is not None
                else None
            ),
            **customs_services,
        ),
        customsInformation=customs,
        additionalInformation=additional_information,
    )

    print_options = dhl_freight_sweden_print.OptionsType(
        label=True,
        pageOptions=dhl_freight_sweden_print.PageOptionsType(pageType=page_type),
    )

    return lib.Serializable(
        request,
        provider_utils.to_dict,
        dict(
            print_options=provider_utils.to_dict(print_options),
            customs_omitted=lib.identity(
                dict(
                    shipper_country_code=shipper.country_code,
                    recipient_country_code=recipient.country_code,
                    **lib.identity(
                        dict(dropped_services=list(requested_customs_services))
                        if requested_customs_services
                        else {}
                    ),
                )
                if customs_omitted
                else None
            ),
        ),
    )


def _customs_information(
    customs: models.Customs,
    customs_options: units.CustomsOptions,
    origin_country: str,
    destination_country: str,
    procedure_code: str,
    reference: typing.Optional[str],
    shipping_date: typing.Optional[str],
) -> dhl_freight_sweden_req.CustomsInformationType:
    duty = customs.duty
    commodities = customs.commodities or []
    # A customs declaration carries a single currency: the duty currency when
    # present, otherwise the commodities' common currency. Commodity lines
    # without a currency are gap-filled from it, and a line carrying a
    # different currency would corrupt the declaration, so it is rejected.
    declaration_currency = lib.identity(
        (duty.currency if duty else None)
        or next(
            (c.value_currency for c in commodities if c.value_currency), None
        )
    )
    conflicting = {
        commodity.value_currency
        for commodity in commodities
        if commodity.value_currency
        and declaration_currency
        and commodity.value_currency != declaration_currency
    }
    if any(conflicting):
        raise DeclarationCurrencyError(
            "Commodity value currencies must match the customs declaration "
            f"currency {declaration_currency}; "
            f"found {', '.join(sorted(conflicting))}",
            details={
                "customs.commodities.value_currency": dict(
                    code="invalid",
                    message="mixed commodity currencies",
                )
            },
        )

    invoice_number = customs.invoice or reference
    if not invoice_number:
        raise CustomsInvoiceNumberError(
            "A customs document requires an invoice number "
            "(customs.invoice) or a shipment reference",
            details={
                "customs.invoice": dict(
                    code="required", message="invoice number is required"
                )
            },
        )

    # The API requires at least one customs document whenever the customs
    # information section is present, so the document is always emitted.
    # DHL records a missing invoice date as 0001-01-01 (booking 2906745548),
    # so it falls back to the shipping date, then the booking date.
    document = dhl_freight_sweden_req.CustomsDocumentType(
        id=invoice_number,
        type=lib.identity(
            provider_units.CustomsDocumentType.CommercialInvoice.value
            if customs.commercial_invoice
            else provider_units.CustomsDocumentType.ProformaInvoice.value
        ),
        transportMovement=lib.identity(
            provider_units.TransportMovement.Export.value
            if destination_country and destination_country != origin_country
            else None
        ),
        invoiceDate=lib.identity(
            lib.fdate(customs.invoice_date)
            or shipping_date
            or datetime.date.today().isoformat()
        ),
        invoiceCurrency=declaration_currency,
        invoiceAmount=duty.declared_value if duty else None,
        eori=customs_options.eori_number.state or None,
    )

    return dhl_freight_sweden_req.CustomsInformationType(
        customsDocuments=[document],
        customsCommodities=[
            _customs_commodity(commodity, declaration_currency, procedure_code)
            for commodity in commodities
        ],
    )


def _customs_commodity(
    commodity: models.Commodity,
    declaration_currency: typing.Optional[str],
    procedure_code: str,
) -> dhl_freight_sweden_req.CustomsCommodityType:
    # DHL stores each line as a quantity total: the line values must sum to
    # the invoice amount (booking 2906745548 recorded a per-unit value 30
    # against an invoice amount 60 for 2 units).
    quantity = commodity.quantity or 1

    return dhl_freight_sweden_req.CustomsCommodityType(
        countryCodeOfOrigin=commodity.origin_country,
        customsValueCurrency=commodity.value_currency or declaration_currency,
        customsValue=lib.identity(
            lib.to_money(commodity.value_amount * quantity)
            if commodity.value_amount is not None
            else None
        ),
        # hsItemId and procedureCode are strings on the wire even though the
        # generated type annotates them as int.
        hsItemId=commodity.hs_code,  # pyright: ignore[reportArgumentType]
        commodityDescription=commodity.description or commodity.title,
        procedureCode=procedure_code,  # pyright: ignore[reportArgumentType]
        # A commodity without a weight unit keeps the kilogram reading it had
        # before unit conversion, unlike the SDK Product default of pounds.
        netWeight=lib.identity(
            units.Weight(
                commodity.weight * quantity,
                commodity.weight_unit or units.WeightUnit.KG.name,
            ).KG
            if commodity.weight is not None
            else None
        ),
        numberOfUnits=quantity,
    )


def _customs_services(
    options: units.ShippingOptions,
    customs_options: units.CustomsOptions,
) -> typing.Dict[str, typing.Any]:
    """Selected DHL customs services keyed by transport-instruction field."""
    services = dict(
        customsHandlingStandard=lib.identity(
            True if options.dhl_freight_sweden_customs_handling_standard.state else None
        ),
        customsHandlingFullService=lib.identity(
            True
            if options.dhl_freight_sweden_customs_handling_full_service.state
            else None
        ),
        customsCustomersOwnDeclaration=lib.identity(
            dhl_freight_sweden_req.CustomsCustomersOwnDeclarationType(
                customsId=options.dhl_freight_sweden_customs_own_declaration_id.state
            )
            if options.dhl_freight_sweden_customs_own_declaration.state
            else None
        ),
        customsJointDeclaration=lib.identity(
            dhl_freight_sweden_req.CustomsJointDeclarationType(
                sfid=options.dhl_freight_sweden_customs_joint_declaration_id.state
            )
            if options.dhl_freight_sweden_customs_joint_declaration.state
            else None
        ),
        voecSupplyVAT=lib.identity(
            dhl_freight_sweden_req.VoecSupplyVATType(
                vatId=customs_options.voec_number.state
            )
            if customs_options.voec_number.state
            else None
        ),
    )

    return {key: value for key, value in services.items() if value is not None}


def _check_customs_service_identifiers(
    options: units.ShippingOptions,
    customs_options: units.CustomsOptions,
) -> None:
    def is_blank(value: typing.Optional[str]) -> bool:
        return not (value or "").strip()

    missing = {
        field: label
        for field, label, is_missing in [
            (
                "customs.options.eori_number",
                "the EORI number for standard customs handling",
                bool(options.dhl_freight_sweden_customs_handling_standard.state)
                and is_blank(customs_options.eori_number.state),
            ),
            (
                "dhl_freight_sweden_customs_own_declaration_id",
                "the customs identifier (MRN) for customer's own declaration",
                bool(options.dhl_freight_sweden_customs_own_declaration.state)
                and is_blank(options.dhl_freight_sweden_customs_own_declaration_id.state),
            ),
            (
                "dhl_freight_sweden_customs_joint_declaration_id",
                "the joint-declaration identifier (SFID) for joint declaration",
                bool(options.dhl_freight_sweden_customs_joint_declaration.state)
                and is_blank(
                    options.dhl_freight_sweden_customs_joint_declaration_id.state
                ),
            ),
        ]
        if is_missing
    }

    if any(missing):
        raise CustomsServiceIdentifierError(
            "The selected customs services require "
            f"{'; '.join(missing.values())}",
            details={
                field: dict(code="required", message=label)
                for field, label in missing.items()
            },
        )


def _payer_code(
    product_code: str,
    options: units.ShippingOptions,
    incoterm: typing.Optional[str],
    shipper_country: typing.Optional[str],
    recipient_country: typing.Optional[str],
) -> typing.Optional[str]:
    explicit = (options.dhl_freight_sweden_payer_code.state or "").strip().upper()
    incoterm = (incoterm or "").strip().upper()
    payer_codes = provider_units.PAYER_CODES.get(product_code)

    if payer_codes is None:
        return explicit or incoterm or "1"

    is_import = recipient_country == "SE" and shipper_country != "SE"
    valid_codes = lib.identity(
        payer_codes.import_codes
        if is_import and payer_codes.import_codes is not None
        else payer_codes.codes
    )
    lane = " (import)" if is_import and payer_codes.import_codes is not None else ""
    combiterms_only = set(valid_codes) <= set(
        provider_units.COMBITERM_BY_INCOTERM.values()
    )

    if explicit:
        payer_code, field = explicit, "dhl_freight_sweden_payer_code"
    elif incoterm and (incoterm in valid_codes or combiterms_only):
        payer_code = lib.identity(
            provider_units.COMBITERM_BY_INCOTERM.get(incoterm, incoterm)
            if combiterms_only
            else incoterm
        )
        field = "customs.incoterm"
    else:
        payer_code = payer_codes.default or provider_units.default_payer_code(
            valid_codes
        )
        field = "dhl_freight_sweden_payer_code"

    if payer_code is None:
        raise PayerCodeError(
            f"Product {product_code}{lane} has no default payer code; set "
            f"dhl_freight_sweden_payer_code to one of {', '.join(valid_codes)}",
            details={
                field: dict(
                    code="required",
                    message=f"one of {', '.join(valid_codes)} is required",
                )
            },
        )

    if payer_code not in valid_codes:
        raise PayerCodeError(
            f"Payer code {payer_code} is not valid for product {product_code}{lane}; "
            f"valid codes: {', '.join(valid_codes)}",
            details={
                field: dict(
                    code="invalid",
                    message=f"valid codes: {', '.join(valid_codes)}",
                )
            },
        )

    if (
        payer_code in payer_codes.joint_declaration_codes
        and not options.dhl_freight_sweden_customs_joint_declaration.state
    ):
        raise PayerCodeError(
            f"Payer code {payer_code} for product {product_code} requires the "
            "customs joint declaration service "
            "(dhl_freight_sweden_customs_joint_declaration)",
            details={
                "dhl_freight_sweden_customs_joint_declaration": dict(
                    code="required",
                    message=f"required by payer code {payer_code}",
                )
            },
        )

    return payer_code


def _sent_information(
    options: units.ShippingOptions,
    country_codes: typing.Set[str],
) -> typing.List[dhl_freight_sweden_req.AdditionalInformationType]:
    if provider_units.SENT_COUNTRY not in country_codes:
        return []

    codes = provider_units.AdditionalInformationCode
    identifiers = [
        (
            "dhl_freight_sweden_sent_ref",
            codes.SENT_REF,
            (options.dhl_freight_sweden_sent_ref.state or "").strip(),
        ),
        (
            "dhl_freight_sweden_sent_carkey",
            codes.SENT_CARKEY,
            (options.dhl_freight_sweden_sent_carkey.state or "").strip(),
        ),
    ]
    given = [(name, code, value) for name, code, value in identifiers if value]
    missing = [name for name, _, value in identifiers if not value]
    too_long = [
        name
        for name, _, value in given
        if len(value) > provider_units.SENT_VALUE_MAX_LENGTH
    ]
    sent_free = options.dhl_freight_sweden_sent_free.state

    if any(too_long):
        raise SentInformationError(
            f"SENT values are limited to {provider_units.SENT_VALUE_MAX_LENGTH} "
            f"characters: {', '.join(too_long)}",
            details={
                name: dict(
                    code="invalid",
                    message=f"at most {provider_units.SENT_VALUE_MAX_LENGTH} characters",
                )
                for name in too_long
            },
        )

    if sent_free is True and any(given):
        given_names = [name for name, _, _ in given]
        raise SentInformationError(
            "dhl_freight_sweden_sent_free contradicts the SENT identifiers "
            f"{', '.join(given_names)}; send either SENT free or the SENT "
            "reference and carrier key",
            details={
                name: dict(code="invalid", message="SENT free with SENT identifiers")
                for name in ["dhl_freight_sweden_sent_free", *given_names]
            },
        )

    if len(given) == len(identifiers):
        return [
            dhl_freight_sweden_req.AdditionalInformationType(
                code=code.value, stringValue=value
            )
            for _, code, value in given
        ]

    if any(given) or sent_free is False:
        raise SentInformationError(
            "A shipment to or from PL that is not SENT free requires both the "
            f"SENT reference and carrier key; missing {', '.join(missing)}",
            details={
                name: dict(code="required", message="SENT identifier is required")
                for name in missing
            },
        )

    if sent_free is not True:
        raise SentInformationError(
            "A shipment to or from PL requires an explicit SENT declaration: "
            "dhl_freight_sweden_sent_free, or "
            "dhl_freight_sweden_sent_ref with dhl_freight_sweden_sent_carkey",
            details={
                "dhl_freight_sweden_sent_free": dict(
                    code="required", message="explicit SENT declaration is required"
                )
            },
        )

    return [
        dhl_freight_sweden_req.AdditionalInformationType(
            code=codes.SENT_FREE.value, stringValue="true"
        )
    ]


def _transport_declarations(
    options: units.ShippingOptions,
    product_code: str,
    lane_countries: typing.Set[str],
    recipient_country: typing.Optional[str],
) -> typing.List[dhl_freight_sweden_req.AdditionalInformationType]:
    return [
        entry
        for declaration in provider_units.TRANSPORT_DECLARATIONS
        if declaration.country in lane_countries
        for entry in _transport_declaration(
            declaration,
            options,
            required=(
                product_code in provider_units.TRANSPORT_DECLARATION_PRODUCTS
                and recipient_country == declaration.country
            ),
        )
    ]


def _transport_declaration(
    declaration: provider_units.TransportDeclaration,
    options: units.ShippingOptions,
    required: bool,
) -> typing.List[dhl_freight_sweden_req.AdditionalInformationType]:
    free = options[declaration.free_option].state
    number = (options[declaration.number_option].state or "").strip()

    def entry(
        code: provider_units.AdditionalInformationCode, value: str
    ) -> dhl_freight_sweden_req.AdditionalInformationType:
        return dhl_freight_sweden_req.AdditionalInformationType(
            code=code.value, stringValue=value
        )

    if len(number) > declaration.number_max_length:
        raise TransportDeclarationError(
            f"The {declaration.name} number is limited to "
            f"{declaration.number_max_length} characters",
            details={
                declaration.number_option: dict(
                    code="invalid",
                    message=f"at most {declaration.number_max_length} characters",
                )
            },
        )

    if free is True and number:
        raise TransportDeclarationError(
            f"{declaration.free_option} contradicts {declaration.number_option}; "
            f"send either {declaration.name} free or the {declaration.name} number",
            details={
                name: dict(
                    code="invalid",
                    message=f"{declaration.name} free with {declaration.name} number",
                )
                for name in [declaration.free_option, declaration.number_option]
            },
        )

    if free is True:
        return [entry(declaration.free_code, "true")]

    if number:
        return [
            entry(declaration.free_code, "false"),
            entry(declaration.number_code, number),
        ]

    if free is False and declaration.number_required:
        raise TransportDeclarationError(
            f"A shipment to or from {declaration.country} that is not "
            f"{declaration.name} free requires {declaration.number_option}",
            details={
                declaration.number_option: dict(
                    code="required",
                    message=f"{declaration.name} number is required",
                )
            },
        )

    if free is False:
        return [entry(declaration.free_code, "false")]

    if required:
        raise TransportDeclarationError(
            f"A shipment to {declaration.country} with this product requires an "
            f"explicit {declaration.name} declaration: {declaration.free_option}, "
            f"or {declaration.number_option}",
            details={
                declaration.free_option: dict(
                    code="required",
                    message=f"explicit {declaration.name} declaration is required",
                )
            },
        )

    return []


def _typed_information_codes(lane_countries: typing.Set[str]) -> typing.Set[str]:
    codes = provider_units.AdditionalInformationCode
    sent_codes = lib.identity(
        {codes.SENT_FREE.value, codes.SENT_REF.value, codes.SENT_CARKEY.value}
        if provider_units.SENT_COUNTRY in lane_countries
        else set()
    )

    return sent_codes | {
        code.value
        for declaration in provider_units.TRANSPORT_DECLARATIONS
        if declaration.country in lane_countries
        for code in (declaration.free_code, declaration.number_code)
    }


def _additional_information(
    entries: typing.List[typing.Any],
    typed_codes: typing.AbstractSet[str],
) -> typing.List[dhl_freight_sweden_req.AdditionalInformationType]:
    def invalid(message: str) -> AdditionalInformationError:
        return AdditionalInformationError(
            message,
            details={
                "dhl_freight_sweden_additional_information": dict(
                    code="invalid", message=message
                )
            },
        )

    if any(not isinstance(entry, dict) or not entry.get("code") for entry in entries):
        raise invalid("Each additionalInformation entry requires a code")

    duplicates = sorted({entry["code"] for entry in entries} & typed_codes)
    if any(duplicates):
        raise invalid(
            f"additionalInformation codes {', '.join(duplicates)} are set "
            "through the SENT, EKAER, or UIT options on this lane"
        )

    return [
        dhl_freight_sweden_req.AdditionalInformationType(
            code=entry["code"],
            stringValue=entry.get("stringValue"),
            dateValue=entry.get("dateValue"),
            numericValue=entry.get("numericValue"),
        )
        for entry in entries
    ]


def _service_point_party(
    options,
    product_code: str,
    country_code: typing.Optional[str],
) -> typing.Optional[dhl_freight_sweden_req.PartyType]:
    service_point = options.dhl_freight_sweden_service_point.state

    if not service_point:
        return None

    if service_point.strip().lower() in provider_units.ACCESS_POINT_TYPE_NAMES:
        raise ServicePointEligibilityError(
            f"The service point option carries the type name {service_point!r} "
            "instead of a service point id; set the id there and the sub type "
            "in dhl_freight_sweden_service_point_type",
            details={
                "dhl_freight_sweden_service_point": dict(
                    code="invalid",
                    message="expected a service point id, not a type name",
                )
            },
        )

    sub_type = provider_units.PartySubType.map(
        options.dhl_freight_sweden_service_point_type.state
        or provider_units.PartySubType.ParcelShop.value
    ).value_or_key
    allowed_sub_types = provider_units.ACCESS_POINT_SUB_TYPES.get(
        product_code, {}
    ).get(country_code or "", frozenset())

    if sub_type not in allowed_sub_types:
        raise ServicePointEligibilityError(
            f"Product {product_code} to {country_code} accepts "
            + lib.identity(
                f"only {', '.join(sorted(allowed_sub_types))} access points"
                if any(allowed_sub_types)
                else "no access point"
            )
            + f"; got {sub_type}",
            details={
                lib.identity(
                    "dhl_freight_sweden_service_point_type"
                    if any(allowed_sub_types)
                    else "dhl_freight_sweden_service_point"
                ): dict(
                    code="invalid",
                    message="access point not available for product and country",
                )
            },
        )

    # Keys double as the ``dhl_freight_sweden_service_point_{key}`` option names.
    details = dict(
        name=options.dhl_freight_sweden_service_point_name.state,
        street=options.dhl_freight_sweden_service_point_street.state,
        city=options.dhl_freight_sweden_service_point_city.state,
        postal_code=options.dhl_freight_sweden_service_point_postal_code.state,
        country_code=options.dhl_freight_sweden_service_point_country_code.state,
    )
    missing = [key for key, value in details.items() if not value]

    # DHL rejects an AccessPoint party without name and address (validation
    # errors 22001 and 22006, live sandbox 2026-09-10), so incomplete details
    # fail here with the missing option names instead of as a carrier 400.
    if any(missing):
        raise ServicePointDetailsError(
            "The service point option requires the full service point details; "
            f"missing {', '.join(missing)}",
            details={
                f"dhl_freight_sweden_service_point_{key}": dict(
                    code="required", message="service point detail is required"
                )
                for key in missing
            },
        )

    return dhl_freight_sweden_req.PartyType(
        id=service_point,
        type=provider_units.PartyType.AccessPoint.value,
        subType=sub_type,
        name=details["name"],
        address=dhl_freight_sweden_req.AddressType(
            street=details["street"],
            cityName=details["city"],
            # postalCode is generated as Optional[int]; keep it a string so
            # alphanumeric/space-bearing postal codes survive serialization.
            postalCode=str(details["postal_code"]) if details["postal_code"] else None,  # pyright: ignore[reportArgumentType]
            countryCode=details["country_code"],
        ),
    )


def _party(
    role: str, address, id: typing.Optional[str] = None
) -> dhl_freight_sweden_req.PartyType:
    return dhl_freight_sweden_req.PartyType(
        type=role,
        id=id,
        name=address.company_name or address.person_name,
        contactName=address.contact,
        vatEoriSocialSecurityNumber=address.tax_id,
        phone=address.phone_number,
        email=address.email,
        address=dhl_freight_sweden_req.AddressType(
            street=address.address_line1,
            additionalAddressInfo=address.address_line2,
            cityName=address.city,
            # postalCode is generated as Optional[int]; keep it a string so
            # alphanumeric/space-bearing postal codes survive serialization.
            postalCode=str(address.postal_code) if address.postal_code else None,  # pyright: ignore[reportArgumentType]
            countryCode=address.country_code,
        ),
    )
