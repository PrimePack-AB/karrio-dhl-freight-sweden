import typing

import karrio.lib as lib
import karrio.core.models as models
import karrio.core.units as units


class ServabilityMode(lib.StrEnum):
    """Postal-code servability check modes for the booking pre-flight.

    The class name must not contain "Address": the SDK references
    ``parse_type`` heuristic classifies any such enum as the Address model
    type, which the dashboard connection-config renderer drops.
    """

    off = "off"
    warn = "warn"
    enforce = "enforce"


class ConnectionConfig(lib.Enum):
    """DHL Freight connection configuration options."""

    server_url = lib.OptionEnum("server_url", str)
    # Last-resort label type tag. The API has no raster selector; the document
    # format is read from the printed bytes, then the report contentType.
    label_type = lib.OptionEnum("label_type", str, "PDF")
    # Print page layout, mapped to the Print API PageTypeEnum.
    label_page_type = lib.OptionEnum("label_page_type", str, "Label")
    # Booking pre-flight against the PostalCodes API route: off skips the
    # check, warn annotates the shipment with a message, enforce blocks the
    # transport instruction on a definitive negative.
    address_validation = lib.OptionEnum(
        "address_validation", ServabilityMode, "off"
    )
    shipping_options = lib.OptionEnum("shipping_options", list)
    shipping_services = lib.OptionEnum("shipping_services", list)


class PartyType(lib.StrEnum):
    """DHL Freight transport-instruction party roles."""

    Consignor = "Consignor"
    Pickup = "Pickup"
    Consignee = "Consignee"
    Delivery = "Delivery"
    AccessPoint = "AccessPoint"
    FreightPayer = "FreightPayer"


class PartySubType(lib.StrEnum):
    """DHL Freight access-point sub types (products 103/109)."""

    ParcelShop = "ParcelShop"
    ParcelStation = "ParcelStation"


class LocationType(lib.StrEnum):
    """DHL Freight Servicepoint API location types (LocationTypeEnum)."""

    servicepoint = "servicepoint"
    locker = "locker"
    postoffice = "postoffice"
    postbank = "postbank"


class AdditionalInformationCode(lib.StrEnum):
    """Shipment additionalInformation codes produced by typed options."""

    SENT_FREE = "SENT_FREE"
    SENT_REF = "SENT_REF"
    SENT_CARKEY = "SENT_CARKEY"
    EKAER_FREE = "EKAER_FREE"
    EKAER_NUMBER = "EKAER_NUMBER"
    UIT_FREE = "UIT_FREE"
    UIT_NUMBER = "UIT_NUMBER"


SENT_COUNTRY = "PL"
SENT_VALUE_MAX_LENGTH = 20


class PageType(lib.StrEnum):
    """DHL Freight Print API page layouts (PageTypeEnum)."""

    Label = "Label"
    Label2xPortraitA4 = "Label2xPortraitA4"
    Label3xLandscapeA4 = "Label3xLandscapeA4"
    LabelCompact = "LabelCompact"
    LabelCompact2x2PortraitA4 = "LabelCompact2x2PortraitA4"


class CustomsDocumentType(lib.StrEnum):
    """DHL Freight customs document types (CustomsDocument.type)."""

    CommercialInvoice = "CommercialInvoice"
    ProformaInvoice = "ProformaInvoice"


class TransportMovement(lib.StrEnum):
    """DHL Freight customs document transport movements."""

    Export = "Export"
    Import = "Import"


class CustomsOption(lib.Enum):
    """Unified ``customs.options`` registration identifiers.

    ``voec_number`` is not a member of the core
    ``karrio.core.units.CustomsOption`` enum, and the options helper drops
    keys unknown to both enums, so customs options are converted with this
    enum as the ``option_type`` to keep it visible.
    """

    eori_number = lib.OptionEnum("eori_number")
    voec_number = lib.OptionEnum("voec_number")


# The SDK EUCountry enum lists Greece under its VAT prefix EL, so the ISO
# code GR is added, and Monaco, which Tullverket treats as EU, is likewise
# appended. Special fiscal territories outside the EU VAT area (Tullverket,
# EU customs and fiscal territories) either carry their own country code
# (AX, IC, GP, GF, MQ, RE, YT), which is absent from EUCountry, or are
# identified by postal-code range within a member state. Northern Ireland
# is inside the EU VAT area for goods and outside it for services; every
# caller here decides customs handling for goods, so its BT postcode area
# is admitted by prefix.
EU_VAT_AREA_COUNTRIES: typing.FrozenSet[str] = frozenset(
    [*(country.name for country in units.EUCountry), "GR", "MC"]
)
NON_EU_VAT_POSTAL_RANGES: typing.Tuple[typing.Tuple[str, int, int], ...] = (
    ("FI", 22000, 22999),  # Åland
    ("ES", 35000, 35999),  # Canary Islands (Las Palmas)
    ("ES", 38000, 38999),  # Canary Islands (Santa Cruz de Tenerife)
    ("ES", 51000, 51999),  # Ceuta
    ("ES", 52000, 52999),  # Melilla
    ("DE", 78266, 78266),  # Büsingen
    ("DE", 27498, 27498),  # Heligoland
    ("GR", 63086, 63086),  # Mount Athos
    ("IT", 23041, 23041),  # Livigno
    ("IT", 22061, 22061),  # Campione d'Italia
)
EU_VAT_POSTAL_PREFIXES: typing.Tuple[typing.Tuple[str, str], ...] = (
    ("GB", "BT"),  # Northern Ireland
)

# Warning code shared with the PostNord connector.
CUSTOMS_OMITTED_INTRA_EU = "customs_omitted_intra_eu"


def in_eu_vat_area(
    country_code: typing.Optional[str],
    postal_code: typing.Optional[str],
) -> bool:
    """Whether an address lies inside the EU VAT area for goods."""
    country = (country_code or "").upper()
    postal = str(postal_code or "").replace(" ", "")
    postal_number = int(postal) if postal.isdigit() else None

    inside_member_state = country in EU_VAT_AREA_COUNTRIES and not any(
        country == range_country
        and postal_number is not None
        and low <= postal_number <= high
        for range_country, low, high in NON_EU_VAT_POSTAL_RANGES
    )
    return inside_member_state or any(
        country == prefix_country and postal.upper().startswith(prefix)
        for prefix_country, prefix in EU_VAT_POSTAL_PREFIXES
    )


class ShippingService(lib.StrEnum):
    """DHL Freight product codes.

    Values are the carrier product codes as strings. They are intentionally
    not integers: the international "Standard Pallet International" product is
    non-numeric (``SPI``), and codes such as ``402``/``502`` must serialize as
    strings on the wire.
    """

    # Domestic (Sweden)
    dhl_freight_sweden_hemleverans_paket_b2c = "118"
    dhl_freight_sweden_home_delivery_b2c = "401"
    dhl_freight_sweden_home_delivery_c2b = "402"
    dhl_freight_sweden_home_delivery_c2b_502 = "502"
    dhl_freight_sweden_pall = "210"
    dhl_freight_sweden_paket = "102"
    dhl_freight_sweden_parti = "212"
    dhl_freight_sweden_service_point_b2c = "103"
    dhl_freight_sweden_service_point_c2b = "104"
    dhl_freight_sweden_special = "209"
    dhl_freight_sweden_stycke = "211"

    # International
    dhl_freight_sweden_road_freight_standard = "202"
    dhl_freight_sweden_euroconnect_plus = "232"
    dhl_freight_sweden_road_freight_direct = "205"
    dhl_freight_sweden_road_freight_priority = "233"
    dhl_freight_sweden_home_delivery_international_b2c = "601"
    dhl_freight_sweden_parcel_connect_b2c = "109"
    dhl_freight_sweden_parcel_return_connect_c2b = "107"
    dhl_freight_sweden_parcel_connect_plus = "112"
    dhl_freight_sweden_standard_pallet_international = "SPI"


class TransportDeclaration(typing.NamedTuple):
    """A free flag and number pair declared under additionalInformation.

    ``number_required`` states whether a shipment that is not free must
    carry the number.
    """

    name: str
    country: str
    free_option: str
    number_option: str
    free_code: AdditionalInformationCode
    number_code: AdditionalInformationCode
    number_max_length: int
    number_required: bool


# Products whose "Related fields" tables in product manual v5.23 list the
# EKAER (HU) and UIT (RO) entries: §5.4 p19 (202), §5.9 p38 (205), §5.11 p46
# (233), §5.12 p51 (SPI), §5.21 p87 (601); PPI (§5.13 p56) is not a
# connector product. The v5.23 release note (p7) makes the UIT number
# optional even when the shipment is not UIT free.
TRANSPORT_DECLARATION_PRODUCTS = (
    ShippingService.dhl_freight_sweden_road_freight_standard.value,
    ShippingService.dhl_freight_sweden_road_freight_direct.value,
    ShippingService.dhl_freight_sweden_road_freight_priority.value,
    ShippingService.dhl_freight_sweden_standard_pallet_international.value,
    ShippingService.dhl_freight_sweden_home_delivery_international_b2c.value,
)
TRANSPORT_DECLARATIONS = (
    TransportDeclaration(
        name="EKAER",
        country="HU",
        free_option="dhl_freight_sweden_ekaer_free",
        number_option="dhl_freight_sweden_ekaer_number",
        free_code=AdditionalInformationCode.EKAER_FREE,
        number_code=AdditionalInformationCode.EKAER_NUMBER,
        number_max_length=20,
        number_required=True,
    ),
    TransportDeclaration(
        name="UIT",
        country="RO",
        free_option="dhl_freight_sweden_uit_free",
        number_option="dhl_freight_sweden_uit_number",
        free_code=AdditionalInformationCode.UIT_FREE,
        number_code=AdditionalInformationCode.UIT_NUMBER,
        number_max_length=19,
        number_required=False,
    ),
)


class PayerCodes(typing.NamedTuple):
    """Terms-of-delivery codes a product accepts.

    ``import_codes`` applies to lanes into Sweden when the product manual
    lists a separate import column; ``default`` overrides the derived
    default (the single listed code, else "1" when listed, else none).
    ``joint_declaration_codes`` are only valid with the customs joint
    declaration service.
    """

    codes: typing.Tuple[str, ...]
    import_codes: typing.Optional[typing.Tuple[str, ...]] = None
    default: typing.Optional[str] = None
    joint_declaration_codes: typing.Tuple[str, ...] = ()


FREIGHT_PAYER_CODES = ("1", "3", "4")
EXPORT_INCOTERMS = ("EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP")
IMPORT_INCOTERMS = ("EXW", "FCA")

# Payer codes per product from the "Payer codes" tables of DHL Freight
# Sweden product manual v5.23 (valid from 2025-04-14), section 5.
PAYER_CODES: typing.Dict[str, PayerCodes] = {
    ShippingService.dhl_freight_sweden_paket.value: PayerCodes(
        FREIGHT_PAYER_CODES  # §5.2 p11
    ),
    # §5.3 p15 lists only 023, so it stays the default; the sandbox also
    # accepted 022 (tests/dhl_freight_sweden/fixtures/sandbox/
    # booking-2906761149-112-se-pl-payer-022.json).
    ShippingService.dhl_freight_sweden_parcel_connect_plus.value: PayerCodes(
        ("022", "023"), default="023"
    ),
    ShippingService.dhl_freight_sweden_road_freight_standard.value: PayerCodes(
        EXPORT_INCOTERMS, IMPORT_INCOTERMS  # §5.4 p20
    ),
    ShippingService.dhl_freight_sweden_special.value: PayerCodes(
        FREIGHT_PAYER_CODES  # §5.5 p23
    ),
    ShippingService.dhl_freight_sweden_pall.value: PayerCodes(
        FREIGHT_PAYER_CODES  # §5.6 p26
    ),
    ShippingService.dhl_freight_sweden_stycke.value: PayerCodes(
        FREIGHT_PAYER_CODES  # §5.7 p31
    ),
    ShippingService.dhl_freight_sweden_parti.value: PayerCodes(
        FREIGHT_PAYER_CODES  # §5.8 p35
    ),
    ShippingService.dhl_freight_sweden_road_freight_direct.value: PayerCodes(
        ("CPT", "CIP", "DAP", "DPU", "DDP"), IMPORT_INCOTERMS  # §5.9 p39
    ),
    ShippingService.dhl_freight_sweden_euroconnect_plus.value: PayerCodes(
        ("DAP", "DDP")  # §5.10 p42
    ),
    ShippingService.dhl_freight_sweden_road_freight_priority.value: PayerCodes(
        EXPORT_INCOTERMS, IMPORT_INCOTERMS  # §5.11 p47
    ),
    ShippingService.dhl_freight_sweden_standard_pallet_international.value: PayerCodes(
        EXPORT_INCOTERMS, IMPORT_INCOTERMS  # §5.12 p52
    ),
    ShippingService.dhl_freight_sweden_service_point_b2c.value: PayerCodes(
        ("1", "4")  # §5.14 p61
    ),
    ShippingService.dhl_freight_sweden_service_point_c2b.value: PayerCodes(
        ("3",)  # §5.15 p64
    ),
    ShippingService.dhl_freight_sweden_parcel_connect_b2c.value: PayerCodes(
        ("022", "023"),  # §5.16 p67
        default="022",
        joint_declaration_codes=("023",),
    ),
    ShippingService.dhl_freight_sweden_parcel_return_connect_c2b.value: PayerCodes(
        ("001",)  # §5.17 p70
    ),
    ShippingService.dhl_freight_sweden_hemleverans_paket_b2c.value: PayerCodes(
        ("1", "4")  # §5.18 p73
    ),
    ShippingService.dhl_freight_sweden_home_delivery_b2c.value: PayerCodes(
        ("1", "4")  # §5.19 p77
    ),
    ShippingService.dhl_freight_sweden_home_delivery_c2b.value: PayerCodes(
        ("3", "4")  # §5.20 p82
    ),
    ShippingService.dhl_freight_sweden_home_delivery_c2b_502.value: PayerCodes(
        ("3", "4")  # §5.20 p82
    ),
    ShippingService.dhl_freight_sweden_home_delivery_international_b2c.value: PayerCodes(
        EXPORT_INCOTERMS, IMPORT_INCOTERMS  # §5.21 p88
    ),
}

# Combiterm equivalents of Incoterms (product manual v5.23 §7.6 p169), used
# to translate customs.incoterm for products that only accept Combiterms.
COMBITERM_BY_INCOTERM: typing.Dict[str, str] = {
    "CPT": "022",
    "CIP": "022",
    "DAP": "022",
    "DPU": "022",
    "DDP": "023",
}


def default_payer_code(payer_codes: typing.Tuple[str, ...]) -> typing.Optional[str]:
    """The derived default for a product's valid payer codes."""
    if len(payer_codes) == 1:
        return payer_codes[0]

    return "1" if "1" in payer_codes else None


PARCEL_SHOP = frozenset([PartySubType.ParcelShop.value])
PARCEL_SHOP_AND_STATION = frozenset(
    [PartySubType.ParcelShop.value, PartySubType.ParcelStation.value]
)

# Access-point sub types per product and destination country from DHL
# Freight Sweden product manual v5.23. Products and countries absent here
# accept no AccessPoint party (e.g. 112, §5.3 p14; 109 to IE and LU).
ACCESS_POINT_SUB_TYPES: typing.Dict[str, typing.Dict[str, typing.FrozenSet[str]]] = {
    # §5.14 p59-60
    ShippingService.dhl_freight_sweden_service_point_b2c.value: {
        "SE": PARCEL_SHOP_AND_STATION
    },
    # Appendix B.3 §10.3.2 p196-197
    ShippingService.dhl_freight_sweden_parcel_connect_b2c.value: {
        "AT": PARCEL_SHOP_AND_STATION,
        "BE": PARCEL_SHOP_AND_STATION,
        "BG": PARCEL_SHOP_AND_STATION,
        "CZ": PARCEL_SHOP_AND_STATION,
        "DE": PARCEL_SHOP,
        "DK": PARCEL_SHOP_AND_STATION,
        "EE": PARCEL_SHOP_AND_STATION,
        "ES": PARCEL_SHOP,
        "FI": PARCEL_SHOP_AND_STATION,
        "FR": PARCEL_SHOP,
        "GB": PARCEL_SHOP,
        "HR": PARCEL_SHOP,
        "HU": PARCEL_SHOP_AND_STATION,
        "IT": PARCEL_SHOP,
        "LT": PARCEL_SHOP_AND_STATION,
        "LV": PARCEL_SHOP_AND_STATION,
        "NL": PARCEL_SHOP_AND_STATION,
        "NO": PARCEL_SHOP,
        "PL": PARCEL_SHOP_AND_STATION,
        "PT": PARCEL_SHOP,
        "RO": PARCEL_SHOP,
        "SI": PARCEL_SHOP,
        "SK": PARCEL_SHOP_AND_STATION,
    },
}

# Sub type and location type names, which are never access-point ids.
ACCESS_POINT_TYPE_NAMES: typing.FrozenSet[str] = frozenset(
    name.lower()
    for name in [
        *(sub_type.value for sub_type in PartySubType.__members__.values()),
        *(location.value for location in LocationType.__members__.values()),
    ]
)


class ShippingOption(lib.Enum):
    """DHL Freight shipping options."""

    # Additional services
    dhl_freight_sweden_notification = lib.OptionEnum(
        "notification", bool, meta=dict(category="NOTIFICATION")
    )
    dhl_freight_sweden_pre_advice = lib.OptionEnum("preAdvice", bool)
    dhl_freight_sweden_tail_lift_unloading = lib.OptionEnum("tailLiftUnloading", bool)
    dhl_freight_sweden_insurance = lib.OptionEnum(
        "insurance", float, meta=dict(category="INSURANCE")
    )
    # Access code (int) for home-delivery doorstep delivery.
    dhl_freight_sweden_doorstep_access_code = lib.OptionEnum("doorstepDelivery", int)

    # Customs services each carry a DHL fee, so they are only sent when their
    # selector is true. Own declaration carries the customs identifier (MRN)
    # and joint declaration the joint-declaration identifier (SFID) in
    # separate options, so a selector without its identifier fails fast.
    dhl_freight_sweden_customs_handling_standard = lib.OptionEnum(
        "customsHandlingStandard", bool
    )
    dhl_freight_sweden_customs_handling_full_service = lib.OptionEnum(
        "customsHandlingFullService", bool
    )
    dhl_freight_sweden_customs_own_declaration = lib.OptionEnum(
        "customsCustomersOwnDeclaration", bool
    )
    dhl_freight_sweden_customs_own_declaration_id = lib.OptionEnum(
        "customsId", str
    )
    dhl_freight_sweden_customs_joint_declaration = lib.OptionEnum(
        "customsJointDeclaration", bool
    )
    dhl_freight_sweden_customs_joint_declaration_id = lib.OptionEnum("sfid", str)

    # Driver instructions (maxLength 140 characters each per the
    # transport-instruction spec).
    dhl_freight_sweden_pickup_instruction = lib.OptionEnum("pickupInstruction", str)
    dhl_freight_sweden_delivery_instruction = lib.OptionEnum("deliveryInstruction", str)

    # Access point / service point (products 103/109): the location id, the
    # access-point sub type (ParcelShop | ParcelStation), and the party
    # details DHL requires on the AccessPoint party (name + address).
    dhl_freight_sweden_service_point = lib.OptionEnum("servicepoint", str)
    dhl_freight_sweden_service_point_type = lib.OptionEnum("servicepointType", str)
    dhl_freight_sweden_service_point_name = lib.OptionEnum(
        "servicepointName", str, meta=dict(category="PUDO")
    )
    dhl_freight_sweden_service_point_street = lib.OptionEnum(
        "servicepointStreet", str, meta=dict(category="PUDO")
    )
    dhl_freight_sweden_service_point_city = lib.OptionEnum(
        "servicepointCity", str, meta=dict(category="PUDO")
    )
    dhl_freight_sweden_service_point_postal_code = lib.OptionEnum(
        "servicepointPostalCode", str, meta=dict(category="PUDO")
    )
    dhl_freight_sweden_service_point_country_code = lib.OptionEnum(
        "servicepointCountryCode", str, meta=dict(category="PUDO")
    )

    # Print page layout override (PageTypeEnum).
    dhl_freight_sweden_label_page_type = lib.OptionEnum("labelPageType", str)

    # Terms-of-delivery code, validated against the product's PAYER_CODES
    # entry. Falls back to customs.incoterm, then to the product default.
    dhl_freight_sweden_payer_code = lib.OptionEnum("payerCode", str)

    # Customs procedure code per commodity (maxLength 4). "1042" is the
    # standard definitive-export procedure in the Swedish export declaration.
    dhl_freight_sweden_customs_procedure_code = lib.OptionEnum("procedureCode", str)

    # SENT (Polish road transport monitoring) entries for lanes to or from PL,
    # sent under the shipment's additionalInformation. The manual lists
    # SENT_REF and SENT_CARKEY (AN..20, product manual v5.23 §5.4 p19); the
    # live API additionally requires SENT_FREE "true" when neither is sent
    # (validation error 22001, tests/dhl_freight_sweden/fixtures/sandbox/
    # rejection-22001-109-se-pl-without-sent.json). The connector requires
    # an explicit choice and never declares SENT free by itself.
    dhl_freight_sweden_sent_free = lib.OptionEnum("SENT_FREE", bool)
    dhl_freight_sweden_sent_ref = lib.OptionEnum("SENT_REF", str)
    dhl_freight_sweden_sent_carkey = lib.OptionEnum("SENT_CARKEY", str)

    # EKAER (HU, AN..20) and UIT (RO, AN..19) declarations, see
    # TRANSPORT_DECLARATIONS.
    dhl_freight_sweden_ekaer_free = lib.OptionEnum("EKAER_FREE", bool)
    dhl_freight_sweden_ekaer_number = lib.OptionEnum("EKAER_NUMBER", str)
    dhl_freight_sweden_uit_free = lib.OptionEnum("UIT_FREE", bool)
    dhl_freight_sweden_uit_number = lib.OptionEnum("UIT_NUMBER", str)

    # Further shipment additionalInformation entries ({code, stringValue,
    # dateValue, numericValue}), sent after the SENT, EKAER, and UIT entries.
    dhl_freight_sweden_additional_information = lib.OptionEnum(
        "additionalInformation", list
    )

    """ Unified Option type mapping """
    email_notification = dhl_freight_sweden_notification
    insurance = dhl_freight_sweden_insurance
    shipper_instructions = dhl_freight_sweden_pickup_instruction
    recipient_instructions = dhl_freight_sweden_delivery_instruction


def shipping_options_initializer(
    options: dict,
    package_options: typing.Optional[units.ShippingOptions] = None,
) -> units.ShippingOptions:
    """Apply default values to the given options."""

    if package_options is not None:
        options.update(package_options.content)

    def items_filter(key: str) -> bool:
        return key in ShippingOption  # type: ignore

    return units.ShippingOptions(options, ShippingOption, items_filter=items_filter)


# The API Farm publishes no money-rate API for these products (the pricequote
# API is not integrated); these defaults seed the rate-sheet catalog with the
# carrier's service levels and zones so universal rating can present the
# product set. The rate=0.0 placeholders are overridden by the merchant's
# negotiated prices at runtime.
#
# Zone model (recipient-gated, account_country_code="SE"):
# - Domestic products: domicile-only, Sweden zone.
# - Outbound parcel family (109/112/232): both flags set so all lanes are
#   granted, Europe zone list from the product catalog gates the recipient.
# - Parcel Return Connect (107): the reverse lane to Sweden; the zone matches
#   the recipient, so Sweden.
# - International freight: international-only with an unrestricted zone
#   (no country list), so any non-SE destination rates without maintaining
#   a country list.
#
# Outbound destination footprints from the DHL Product API catalog
# (GET /productapi/v1/products/{code} toCountries, all from SE; every
# product below is isDomestic=false).
PARCEL_CONNECT_B2C_COUNTRIES = [
    "AT",
    "BE",
    "BG",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "NL",
    "NO",
    "PL",
    "PT",
    "RO",
    "SI",
    "SK",
]
PARCEL_CONNECT_PLUS_COUNTRIES = [
    "AT",
    "BE",
    "BG",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "NL",
    "NO",
    "PL",
    "PT",
    "RO",
    "SI",
    "SK",
]
EUROCONNECT_PLUS_COUNTRIES = [
    "AT",
    "BE",
    "BG",
    "CH",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GB",
    "GR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "NL",
    "NO",
    "PL",
    "PT",
    "RO",
    "SI",
    "SK",
]

DEFAULT_SERVICES: typing.List[models.ServiceLevel] = [
    models.ServiceLevel(
        service_name="Hemleverans Paket B2C",
        service_code="dhl_freight_sweden_hemleverans_paket_b2c",
        carrier_service_code="118",
        currency="SEK",
        domicile=True,
        international=False,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    ),
    models.ServiceLevel(
        service_name="Home Delivery B2C",
        service_code="dhl_freight_sweden_home_delivery_b2c",
        carrier_service_code="401",
        currency="SEK",
        domicile=True,
        international=False,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    ),
    models.ServiceLevel(
        service_name="Home Delivery C2B",
        service_code="dhl_freight_sweden_home_delivery_c2b",
        carrier_service_code="402",
        currency="SEK",
        domicile=True,
        international=False,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    ),
    models.ServiceLevel(
        service_name="Home Delivery C2B (502)",
        service_code="dhl_freight_sweden_home_delivery_c2b_502",
        carrier_service_code="502",
        currency="SEK",
        domicile=True,
        international=False,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    ),
    models.ServiceLevel(
        service_name="Pall",
        service_code="dhl_freight_sweden_pall",
        carrier_service_code="210",
        currency="SEK",
        domicile=True,
        international=False,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    ),
    models.ServiceLevel(
        service_name="Paket",
        service_code="dhl_freight_sweden_paket",
        carrier_service_code="102",
        currency="SEK",
        domicile=True,
        international=False,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    ),
    models.ServiceLevel(
        service_name="Parti",
        service_code="dhl_freight_sweden_parti",
        carrier_service_code="212",
        currency="SEK",
        domicile=True,
        international=False,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    ),
    models.ServiceLevel(
        service_name="Service Point B2C",
        service_code="dhl_freight_sweden_service_point_b2c",
        carrier_service_code="103",
        currency="SEK",
        domicile=True,
        international=False,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    ),
    models.ServiceLevel(
        service_name="Service Point C2B",
        service_code="dhl_freight_sweden_service_point_c2b",
        carrier_service_code="104",
        currency="SEK",
        domicile=True,
        international=False,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    ),
    models.ServiceLevel(
        service_name="Special",
        service_code="dhl_freight_sweden_special",
        carrier_service_code="209",
        currency="SEK",
        domicile=True,
        international=False,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    ),
    models.ServiceLevel(
        service_name="Stycke",
        service_code="dhl_freight_sweden_stycke",
        carrier_service_code="211",
        currency="SEK",
        domicile=True,
        international=False,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    ),
    models.ServiceLevel(
        service_name="Road Freight Standard",
        service_code="dhl_freight_sweden_road_freight_standard",
        carrier_service_code="202",
        currency="SEK",
        domicile=False,
        international=True,
        zones=[models.ServiceZone(label="International", rate=0.0)],
    ),
    models.ServiceLevel(
        service_name="Euroconnect Plus",
        service_code="dhl_freight_sweden_euroconnect_plus",
        carrier_service_code="232",
        currency="SEK",
        domicile=True,
        international=True,
        zones=[
            models.ServiceZone(
                label="Europe",
                rate=0.0,
                country_codes=EUROCONNECT_PLUS_COUNTRIES,
            )
        ],
    ),
    models.ServiceLevel(
        service_name="Road Freight Direct",
        service_code="dhl_freight_sweden_road_freight_direct",
        carrier_service_code="205",
        currency="SEK",
        domicile=False,
        international=True,
        zones=[models.ServiceZone(label="International", rate=0.0)],
    ),
    models.ServiceLevel(
        service_name="Road Freight Priority",
        service_code="dhl_freight_sweden_road_freight_priority",
        carrier_service_code="233",
        currency="SEK",
        domicile=False,
        international=True,
        zones=[models.ServiceZone(label="International", rate=0.0)],
    ),
    models.ServiceLevel(
        service_name="Home Delivery International B2C",
        service_code="dhl_freight_sweden_home_delivery_international_b2c",
        carrier_service_code="601",
        currency="SEK",
        domicile=False,
        international=True,
        zones=[models.ServiceZone(label="International", rate=0.0)],
    ),
    models.ServiceLevel(
        service_name="Parcel Connect B2C",
        service_code="dhl_freight_sweden_parcel_connect_b2c",
        carrier_service_code="109",
        currency="SEK",
        domicile=True,
        international=True,
        zones=[
            models.ServiceZone(
                label="Europe",
                rate=0.0,
                country_codes=PARCEL_CONNECT_B2C_COUNTRIES,
            )
        ],
    ),
    models.ServiceLevel(
        service_name="Parcel Return Connect C2B",
        service_code="dhl_freight_sweden_parcel_return_connect_c2b",
        carrier_service_code="107",
        currency="SEK",
        domicile=True,
        international=True,
        zones=[models.ServiceZone(label="Sweden", rate=0.0, country_codes=["SE"])],
    ),
    models.ServiceLevel(
        service_name="Parcel Connect Plus",
        service_code="dhl_freight_sweden_parcel_connect_plus",
        carrier_service_code="112",
        currency="SEK",
        domicile=True,
        international=True,
        zones=[
            models.ServiceZone(
                label="Europe",
                rate=0.0,
                country_codes=PARCEL_CONNECT_PLUS_COUNTRIES,
            )
        ],
    ),
    models.ServiceLevel(
        service_name="Standard Pallet International",
        service_code="dhl_freight_sweden_standard_pallet_international",
        carrier_service_code="SPI",
        currency="SEK",
        domicile=False,
        international=True,
        zones=[models.ServiceZone(label="International", rate=0.0)],
    ),
]
