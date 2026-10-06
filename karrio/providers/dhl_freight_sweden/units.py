import fnmatch
import re
import typing

import attr

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
    # Requested label format; only SUPPORTED_LABEL_TYPES are accepted.
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


# Label formats the connector accepts. The Print API has no document format
# parameter (vendor/se-api-farm/print-api-2.10.0.json), and every sandbox
# label is a PDF (tests/dhl_freight_sweden/fixtures/sandbox/label-*.json).
SUPPORTED_LABEL_TYPES: typing.Tuple[str, ...] = ("PDF",)


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


# Karrio customs content types that describe goods not sold; every other
# content type, and an unset one, is sale-like. Mirrors NOT_SALE_LIKE_CONTENT
# in nordic_conventions' lanes.py.
NOT_SALE_LIKE_CONTENT: typing.FrozenSet[str] = frozenset(
    {
        units.CustomsContentType.documents.name,
        units.CustomsContentType.gift.name,
        units.CustomsContentType.return_merchandise.name,
        units.CustomsContentType.sample.name,
    }
)


def content_type_of(customs: typing.Optional[models.Customs]) -> typing.Optional[str]:
    """The customs content type lower-cased, so names and values compare alike."""
    content_type = getattr(customs, "content_type", None)
    return (str(content_type).strip().lower() or None) if content_type else None


def sale_like(customs: typing.Optional[models.Customs]) -> bool:
    """Whether customs data describes goods for sale."""
    return customs is not None and content_type_of(customs) not in NOT_SALE_LIKE_CONTENT


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


NUMERIC_POSTAL_TERRITORY_PARENTS: typing.Dict[str, str] = {
    "AX": "FI",  # Åland
    "FO": "DK",  # Faroe Islands
    "GL": "DK",  # Greenland
    "IC": "ES",  # Canary Islands
    "EA": "ES",  # Ceuta and Melilla
}
NON_EU_VAT_POSTAL_TERRITORY_PREFIXES: typing.Tuple[typing.Tuple[str, str], ...] = (
    ("DK", "FO"),  # Faroe Islands
    ("DK", "GL"),  # Greenland
)
NON_EU_VAT_POSTAL_CODE_LENGTHS: typing.Tuple[typing.Tuple[str, int], ...] = (
    ("DK", 3),  # Faroe Islands
)
UK_POSTCODE_AREA_CODES: typing.FrozenSet[str] = frozenset({"JE", "GY", "IM", "BT"})

# Territories with their own ISO or customs country code that DHL serves
# under their parent country: product matches answered no product for AX
# 22100, JE JE2 3AB, GG GY1 1AA, and FO 100, and matched products for FI
# 22100 and GB JE2 3AB (tests/dhl_freight_sweden/fixtures/sandbox/
# lookup-product-matches-se-ax-22100.json and the other territory probes).
TERRITORY_PARENTS: typing.Dict[str, str] = {
    **NUMERIC_POSTAL_TERRITORY_PARENTS,
    "JE": "GB",  # Jersey
    "GG": "GB",  # Guernsey
    "IM": "GB",  # Isle of Man
    "XI": "GB",  # Northern Ireland
}


def parent_country(country_code: typing.Optional[str]) -> typing.Optional[str]:
    """The country DHL serves a territory code under; other codes unchanged."""
    return TERRITORY_PARENTS.get((country_code or "").upper(), country_code)


def with_parent_country(address: models.Address) -> models.Address:
    """``address`` with a territory country code replaced by its parent's."""
    country_code = parent_country(address.country_code)
    return lib.identity(
        attr.evolve(address, country_code=country_code)
        if country_code != address.country_code
        else address
    )


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
    ("FR", 97000, 97999),  # French overseas departments and collectivities
    ("DK", 3800, 3999),  # Faroe Islands and Greenland
    ("FR", 98600, 98899),  # Wallis and Futuna, French Polynesia, New Caledonia
    ("EL", 63086, 63086),  # Mount Athos under Greece's VAT prefix
)
EU_VAT_POSTAL_PREFIXES: typing.Tuple[typing.Tuple[str, str], ...] = (
    ("GB", "BT"),  # Northern Ireland
)

# Product manual v5.26 lists each customs service as "Can not be combined
# with" the other three (§6.5 p92, §6.6 p94, §6.7 p96, §6.8 p98).
EXCLUSIVE_CUSTOMS_SERVICES: typing.Dict[str, str] = {
    "dhl_freight_sweden_customs_handling_full_service": "customsHandlingFullService",
    "dhl_freight_sweden_customs_handling_standard": "customsHandlingStandard",
    "dhl_freight_sweden_customs_own_declaration": "customsCustomersOwnDeclaration",
    "dhl_freight_sweden_customs_joint_declaration": "customsJointDeclaration",
}
EXCLUSIVE_CUSTOMS_SERVICES_CITATION = "§6.5 p92, §6.6 p94, §6.7 p96, §6.8 p98"

# DHL rejected customs handling full service and standard for SE to FI
# 22100 with 24003 "... is not available for this country combination"
# (tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland.json,
# rejection-24003-112-se-fi-aland-standard.json), although product manual
# v5.26 lists Åland (FI 22) for Customs handling - Standard (§6.6 p94).
ALAND_POSTAL_RANGE: typing.Tuple[str, int, int] = ("FI", 22000, 22999)
ALAND_REJECTED_CUSTOMS_SERVICES: typing.Dict[str, str] = {
    "dhl_freight_sweden_customs_handling_standard": "customsHandlingStandard",
    "dhl_freight_sweden_customs_handling_full_service": "customsHandlingFullService",
}
ALAND_CUSTOMS_EVIDENCE: typing.Tuple[str, ...] = (
    "tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland.json",
    "tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland-standard.json",
)


def in_aland(country_code: typing.Optional[str], postal_code: typing.Optional[str]) -> bool:
    """Whether an address lies in Åland, FI 22000-22999 once mapped and normalised."""
    country, low, high = ALAND_POSTAL_RANGE
    if parent_country((country_code or "").upper()) != country:
        return False
    postal = normalized_postal_code(country, postal_code)
    return postal.isdigit() and low <= int(postal) <= high


# Warning code shared with the PostNord connector.
CUSTOMS_OMITTED_INTRA_EU = "customs_omitted_intra_eu"


def postal_prefix_codes(country_code: str) -> typing.Tuple[str, ...]:
    """Codes that may lead a postal code of ``country_code`` and are removed.

    These are the country's own code and the codes of its territories with
    numeric postal codes. ``JE``, ``GY``, ``IM``, and ``BT`` are never
    removed, because they begin United Kingdom postcodes.
    """
    territories = (
        territory
        for territory, parent in NUMERIC_POSTAL_TERRITORY_PARENTS.items()
        if parent == country_code
    )
    return tuple(
        code
        for code in (country_code, *territories)
        if code and code not in UK_POSTCODE_AREA_CODES
    )


def _split_postal_code(
    country: str, postal_code: typing.Optional[str]
) -> typing.Tuple[typing.Optional[str], str]:
    postal = str(postal_code or "").strip().upper()
    for code in postal_prefix_codes(country):
        separator = r"[\s-]+" if code == "GB" else r"[\s-]+|(?=\d)"
        prefix = re.match(rf"{re.escape(code)}(?:{separator})", postal)
        if prefix:
            return code, postal[prefix.end():].replace(" ", "")
    return None, postal.replace(" ", "")


def normalized_postal_code(
    country_code: typing.Optional[str],
    postal_code: typing.Optional[str],
) -> str:
    """A postal code upper-cased, trimmed, without a leading prefix code, and without spaces.

    A prefix code (``postal_prefix_codes``) is removed when a hyphen,
    whitespace, or, except for ``GB``, a digit follows it, so ``FI-22100``,
    ``FI 22 100``, ``FI22100``, and ``AX-22100`` all read as ``22100`` under
    FI. The rule is shared with nordic_conventions' territories module.
    """
    return _split_postal_code((country_code or "").upper(), postal_code)[1]


def outside_by_postal_territory(
    country_code: typing.Optional[str],
    postal_code: typing.Optional[str],
) -> bool:
    """Whether the postal code alone places a member-state address outside the EU VAT area.

    That is a removed prefix code listed in
    ``NON_EU_VAT_POSTAL_TERRITORY_PREFIXES`` or a purely numeric code whose
    digit count ``NON_EU_VAT_POSTAL_CODE_LENGTHS`` lists, such as the Faroe
    Islands' three-digit codes under DK.
    """
    country = (country_code or "").upper()
    prefix_code, postal = _split_postal_code(country, postal_code)
    return (country, prefix_code) in NON_EU_VAT_POSTAL_TERRITORY_PREFIXES or (
        postal.isdigit() and (country, len(postal)) in NON_EU_VAT_POSTAL_CODE_LENGTHS
    )


def in_eu_vat_area(
    country_code: typing.Optional[str],
    postal_code: typing.Optional[str],
) -> bool:
    """Whether an address lies inside the EU VAT area for goods."""
    country = (country_code or "").upper()
    postal = normalized_postal_code(country, postal_code)
    postal_number = int(postal) if postal.isdigit() else None

    inside_member_state = (
        country in EU_VAT_AREA_COUNTRIES
        and not outside_by_postal_territory(country, postal_code)
        and not any(
            country == range_country
            and postal_number is not None
            and low <= postal_number <= high
            for range_country, low, high in NON_EU_VAT_POSTAL_RANGES
        )
    )
    return inside_member_state or any(
        country == prefix_country and postal.startswith(prefix)
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


# Products whose "Related fields" tables in product manual v5.26 list the
# EKAER (HU) and UIT (RO) entries: §5.4 p23 (202), §5.9 p42 (205), §5.10 p47
# (233), §5.11 p52 (SPI), §5.19 p82 (601). The same tables mark the UIT code
# conditional ("Code should be provided if possible") even when the shipment
# is not UIT free.
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


# Product manual v5.26 makes a VAT number/TIN mandatory for all parties in
# the shipment information of these products for shipments to or from GR:
# §5.4 p22 (202), §5.11 p51 (SPI), §5.19 p81 (601).
PARTY_TAX_ID_COUNTRY = "GR"
PARTY_TAX_ID_PRODUCTS = (
    ShippingService.dhl_freight_sweden_road_freight_standard.value,
    ShippingService.dhl_freight_sweden_standard_pallet_international.value,
    ShippingService.dhl_freight_sweden_home_delivery_international_b2c.value,
)


# Products offering a QR code through the print API selection "qrCode":
# true, by the country the shipment is sent from. Product manual v5.26
# §5.15 p65 lists BE, BG, CZ, DE, ES, LU, and PT for 107, whose shipments
# are returned from the consumer's country to the original sender.
QR_CODE_COUNTRIES: typing.Dict[str, typing.FrozenSet[str]] = {
    ShippingService.dhl_freight_sweden_parcel_return_connect_c2b.value: frozenset(
        ["BE", "BG", "CZ", "DE", "ES", "LU", "PT"]
    ),
}


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
# Sweden product manual v5.26 (valid from 2026-11-01), section 5.
PAYER_CODES: typing.Dict[str, PayerCodes] = {
    ShippingService.dhl_freight_sweden_paket.value: PayerCodes(
        FREIGHT_PAYER_CODES  # §5.2 p15
    ),
    # §5.3 p19 lists only 023, so it stays the default; the sandbox also
    # accepted 022 (tests/dhl_freight_sweden/fixtures/sandbox/
    # booking-2906761149-112-se-pl-payer-022.json).
    ShippingService.dhl_freight_sweden_parcel_connect_plus.value: PayerCodes(
        ("022", "023"), default="023"
    ),
    ShippingService.dhl_freight_sweden_road_freight_standard.value: PayerCodes(
        EXPORT_INCOTERMS, IMPORT_INCOTERMS  # §5.4 p24
    ),
    # §5.5 p27; 8 is manual invoicing, which needs a separate agreement.
    ShippingService.dhl_freight_sweden_special.value: PayerCodes(
        (*FREIGHT_PAYER_CODES, "8")
    ),
    ShippingService.dhl_freight_sweden_pall.value: PayerCodes(
        FREIGHT_PAYER_CODES  # §5.6 p30
    ),
    ShippingService.dhl_freight_sweden_stycke.value: PayerCodes(
        FREIGHT_PAYER_CODES  # §5.7 p35
    ),
    ShippingService.dhl_freight_sweden_parti.value: PayerCodes(
        FREIGHT_PAYER_CODES  # §5.8 p39
    ),
    ShippingService.dhl_freight_sweden_road_freight_direct.value: PayerCodes(
        ("CPT", "CIP", "DAP", "DPU", "DDP"), IMPORT_INCOTERMS  # §5.9 p43
    ),
    ShippingService.dhl_freight_sweden_road_freight_priority.value: PayerCodes(
        EXPORT_INCOTERMS, IMPORT_INCOTERMS  # §5.10 p48
    ),
    ShippingService.dhl_freight_sweden_standard_pallet_international.value: PayerCodes(
        EXPORT_INCOTERMS, IMPORT_INCOTERMS  # §5.11 p53
    ),
    ShippingService.dhl_freight_sweden_service_point_b2c.value: PayerCodes(
        ("1", "4")  # §5.12 p57
    ),
    ShippingService.dhl_freight_sweden_service_point_c2b.value: PayerCodes(
        ("3",)  # §5.13 p60
    ),
    ShippingService.dhl_freight_sweden_parcel_connect_b2c.value: PayerCodes(
        ("022", "023"),  # §5.14 p63
        default="022",
        joint_declaration_codes=("023",),
    ),
    ShippingService.dhl_freight_sweden_parcel_return_connect_c2b.value: PayerCodes(
        ("001",)  # §5.15 p66
    ),
    ShippingService.dhl_freight_sweden_hemleverans_paket_b2c.value: PayerCodes(
        ("1", "4")  # §5.16 p69
    ),
    ShippingService.dhl_freight_sweden_home_delivery_b2c.value: PayerCodes(
        ("1", "4")  # §5.17 p73
    ),
    ShippingService.dhl_freight_sweden_home_delivery_c2b.value: PayerCodes(
        ("3", "4")  # §5.18 p77
    ),
    ShippingService.dhl_freight_sweden_home_delivery_c2b_502.value: PayerCodes(
        ("3", "4")  # §5.18 p77
    ),
    ShippingService.dhl_freight_sweden_home_delivery_international_b2c.value: PayerCodes(
        EXPORT_INCOTERMS, IMPORT_INCOTERMS  # §5.19 p83
    ),
}

# Combiterm equivalents of Incoterms (product manual v5.26 §7.6 p163), used
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
# Freight Sweden product manual v5.26. Products and countries absent here
# accept no AccessPoint party (e.g. 112, §5.3 p19; 109 to IE and LU).
ACCESS_POINT_SUB_TYPES: typing.Dict[str, typing.Dict[str, typing.FrozenSet[str]]] = {
    # §5.12 p55-56
    ShippingService.dhl_freight_sweden_service_point_b2c.value: {
        "SE": PARCEL_SHOP_AND_STATION
    },
    # Appendix C.3 §10.4.2 p192-194
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
        "IT": PARCEL_SHOP_AND_STATION,
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

    # Print API QR code, see QR_CODE_COUNTRIES.
    dhl_freight_sweden_qr_code = lib.OptionEnum("qrCode", bool)

    # Terms-of-delivery code, validated against the product's PAYER_CODES
    # entry. Falls back to customs.incoterm, then to the product default.
    dhl_freight_sweden_payer_code = lib.OptionEnum("payerCode", str)

    # Customs procedure code per commodity (maxLength 4). "1042" is the
    # standard definitive-export procedure in the Swedish export declaration.
    dhl_freight_sweden_customs_procedure_code = lib.OptionEnum("procedureCode", str)

    # SENT (Polish road transport monitoring) entries for lanes to or from PL,
    # sent under the shipment's additionalInformation. Product manual v5.26
    # makes SENT_FREE mandatory and, for a shipment that is not SENT free,
    # SENT_REF and SENT_CARKEY (AN..20), which its API example sends after
    # SENT_FREE "false" (§5.4 p23). The live API rejects a PL shipment
    # without the identifiers unless SENT_FREE is "true" (validation error
    # 22001, tests/dhl_freight_sweden/fixtures/sandbox/
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
# - Outbound parcel family (109/112): both flags set so all lanes are
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
# Product manual v5.26 lists GB for 109 only according to a separate
# agreement (§5.14 p63, Appendix G p200).
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
    "GB",
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
# FR is listed for 112 by product manual v5.26 (§5.3 p18, Appendix G p199),
# which excludes FR postal codes 97100-99999 and requires the Print and
# TransportInstruction APIs for FR; the connector books through both. The
# same pages list GB for 112 only according to a separate agreement.
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
    "FR",
    "GB",
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


class PostalCodeFormat(typing.NamedTuple):
    """A country's postal-code shape for the excluded-range checks.

    ``pattern`` must match the whole code once spaces are removed, and its
    ``key`` group holds the ``key_digits`` digits the ranges compare.
    """

    pattern: str
    key_digits: int
    description: str


FOUR_DIGITS = PostalCodeFormat(r"(?P<key>\d{4})", 4, "4-digit")
FIVE_DIGITS = PostalCodeFormat(r"(?P<key>\d{5})", 5, "5-digit")
# Portuguese codes are NNNN-NNN; the excluded ranges cover the first four
# digits, so a bare four-digit prefix is accepted too.
PORTUGUESE = PostalCodeFormat(r"(?P<key>\d{4})(-?\d{3})?", 4, "NNNN-NNN")
POSTAL_CODE_FORMATS: typing.Dict[str, PostalCodeFormat] = {
    "DK": FOUR_DIGITS,
    "ES": FIVE_DIGITS,
    "FR": FIVE_DIGITS,
    "IT": FIVE_DIGITS,
    "NO": FOUR_DIGITS,
    "PT": PORTUGUESE,
    "UA": FIVE_DIGITS,
}


class PostalCodeExclusion(typing.NamedTuple):
    """A postal-code range of a country a product does not serve.

    ``parties`` names the transport-instruction addresses the range applies
    to. A code that does not match the country's ``POSTAL_CODE_FORMATS``
    entry cannot be shown to lie outside the range, so it counts as
    excluded.
    """

    product: str
    country: str
    low: int
    high: int
    region: str
    parties: typing.Tuple[str, ...] = ("recipient",)
    danish_territories: bool = False

    def describe(self) -> str:
        width = POSTAL_CODE_FORMATS[self.country].key_digits
        low, high = f"{self.low:0{width}d}", f"{self.high:0{width}d}"
        return low if low == high else f"{low}-{high}"

    def excluded_codes(self) -> str:
        return f"{self.country} postal codes {self.describe()} ({self.region})"

    def required_code(self) -> str:
        return f"{POSTAL_CODE_FORMATS[self.country].description} postal code"

    def verdict(self, postal_code: typing.Optional[str]) -> typing.Optional[bool]:
        """Whether the code is excluded, or None when it is malformed or missing.

        With ``danish_territories`` a code ``outside_by_postal_territory``
        places in the Faroe Islands or Greenland is excluded too, whatever its
        digits.
        """
        if self.danish_territories and outside_by_postal_territory(self.country, postal_code):
            return True
        key = postal_code_key(self.country, postal_code)
        return None if key is None else self.low <= key <= self.high


class PostalCodePatternExclusion(typing.NamedTuple):
    """Postal codes of a country a product does not serve, as wildcard patterns.

    A pattern is matched against the whole normalised code, ``*`` standing
    for any characters and ``?`` for one, as in the Product API catalog's
    ``postalCodeExcludes``; the single pattern ``*`` excludes the whole
    country, a missing code included. A missing code matched by no pattern
    cannot be shown to be served, so it counts as excluded.
    """

    product: str
    country: str
    patterns: typing.Tuple[str, ...]
    region: str
    parties: typing.Tuple[str, ...] = ("recipient",)

    def describe(self) -> str:
        return ", ".join(self.patterns)

    def excluded_codes(self) -> str:
        return lib.identity(
            f"{self.country} ({self.region})"
            if self.patterns == ("*",)
            else f"{self.country} postal codes {self.describe()} ({self.region})"
        )

    def required_code(self) -> str:
        return "postal code"

    def verdict(self, postal_code: typing.Optional[str]) -> typing.Optional[bool]:
        """Whether the code is excluded, or None when it is missing and unmatched."""
        code = normalized_postal_code(self.country, postal_code)
        matched = any(fnmatch.fnmatchcase(code, pattern) for pattern in self.patterns)
        return True if matched else (None if not code else False)


Exclusion = typing.Union[PostalCodeExclusion, PostalCodePatternExclusion]


def _excluded(
    products: typing.Iterable[ShippingService],
    country: str,
    region: str,
    *ranges: typing.Union[int, typing.Tuple[int, int]],
    parties: typing.Tuple[str, ...] = ("recipient",),
    danish_territories: bool = False,
) -> typing.Tuple[PostalCodeExclusion, ...]:
    return tuple(
        PostalCodeExclusion(
            product.value, country, low, high, region, parties, danish_territories
        )
        for product in products
        for low, high in (
            code if isinstance(code, tuple) else (code, code) for code in ranges
        )
    )


PARCEL_CONNECT_PLUS = (ShippingService.dhl_freight_sweden_parcel_connect_plus,)
PARCEL_CONNECT = (ShippingService.dhl_freight_sweden_parcel_connect_b2c,)
PARCEL_RETURN_CONNECT = (ShippingService.dhl_freight_sweden_parcel_return_connect_c2b,)
SHIPPER = ("shipper",)
BOTH_PARTIES = ("shipper", "recipient")
CRIMEA_PRODUCTS = (
    ShippingService.dhl_freight_sweden_road_freight_standard,
    ShippingService.dhl_freight_sweden_road_freight_direct,
    ShippingService.dhl_freight_sweden_standard_pallet_international,
)

# The numeric "Excluded regions/areas" of product manual v5.26; the areas
# without ranges are in POSTAL_CODE_PATTERN_EXCLUSIONS. The DK entries read
# "Greenland & The Faroe Islands (3800-3999)" (§5.3 p18, §5.14 p63, §5.15
# p66), so they also exclude FO- and GL-led and three-digit Faroese codes.
POSTAL_CODE_EXCLUSIONS: typing.Tuple[PostalCodeExclusion, ...] = (
    # 112, §5.3 p18
    *_excluded(
        PARCEL_CONNECT_PLUS, "DK", "Greenland and the Faroe Islands", (3800, 3999),
        danish_territories=True,
    ),
    *_excluded(PARCEL_CONNECT_PLUS, "ES", "Canary Islands", (35000, 35999), (38000, 38999)),
    *_excluded(PARCEL_CONNECT_PLUS, "ES", "Ceuta and Melilla", 51080, 52080),
    *_excluded(PARCEL_CONNECT_PLUS, "FR", "outside mainland France and Corsica", (97100, 99999)),
    *_excluded(
        PARCEL_CONNECT_PLUS,
        "IT",
        "Campione d'Italia, Livigno, Trepalle, San Marino, Ventotene, Ponza, "
        "Serle, Isola Bella, and Giglio",
        22061, 23041, 23030, (47890, 47899), 4020, 4027, 25080, 28838, 58012,
    ),
    *_excluded(PARCEL_CONNECT_PLUS, "NO", "Jan Mayen and Svalbard", 8099, (9170, 9179)),
    *_excluded(PARCEL_CONNECT_PLUS, "PT", "the Azores, Madeira, and other islands", (9000, 9999)),
    # 109, §5.14 p63
    *_excluded(
        PARCEL_CONNECT, "DK", "Greenland and the Faroe Islands", (3800, 3999),
        danish_territories=True,
    ),
    *_excluded(PARCEL_CONNECT, "ES", "Canary Islands", (35000, 35999), (38000, 38999)),
    *_excluded(PARCEL_CONNECT, "ES", "Ceuta and Melilla", 51080, 52080),
    *_excluded(PARCEL_CONNECT, "FR", "outside mainland France and Corsica", (97100, 99999)),
    *_excluded(
        PARCEL_CONNECT,
        "IT",
        "Vatican, Campione d'Italia, Livigno-Trepalle, and San Marino",
        120, 22061, 23041, (47890, 47899),
    ),
    *_excluded(PARCEL_CONNECT, "NO", "Jan Mayen and Svalbard", 8099, (9170, 9179)),
    *_excluded(PARCEL_CONNECT, "PT", "the Azores, Madeira, and other islands", (9000, 9999)),
    # 107, §5.15 p66: returns are sent from the listed countries, and the FR
    # entry reads "Delivery only from France mainland and Corsica".
    *_excluded(
        PARCEL_RETURN_CONNECT, "DK", "Greenland and the Faroe Islands", (3800, 3999),
        parties=SHIPPER, danish_territories=True,
    ),
    *_excluded(
        PARCEL_RETURN_CONNECT, "ES", "Canary Islands", (35000, 35999), (38000, 38999),
        parties=SHIPPER,
    ),
    *_excluded(
        PARCEL_RETURN_CONNECT, "ES", "Ceuta and Melilla", 51080, 52080, parties=SHIPPER
    ),
    *_excluded(
        PARCEL_RETURN_CONNECT,
        "IT",
        "Vatican, Campione d'Italia, Livigno-Trepalle, and San Marino",
        120, 22061, 23041, (47890, 47899),
        parties=SHIPPER,
    ),
    *_excluded(
        PARCEL_RETURN_CONNECT, "NO", "Jan Mayen and Svalbard", 8099, (9170, 9179),
        parties=SHIPPER,
    ),
    *_excluded(
        PARCEL_RETURN_CONNECT, "PT", "the Azores, Madeira, and other islands", (9000, 9999),
        parties=SHIPPER,
    ),
    # 202 §5.4 p23, 205 §5.9 p43, SPI §5.11 p52: postal codes starting with
    # 95 to 99. These products are used to and from SE, so both parties.
    *_excluded(
        CRIMEA_PRODUCTS, "UA", "Crimea/Sebastopol region", (95000, 99999),
        parties=BOTH_PARTIES,
    ),
)


def _patterns(
    products: typing.Iterable[ShippingService],
    country: str,
    region: str,
    patterns: str,
    parties: typing.Tuple[str, ...] = ("recipient",),
) -> typing.Tuple[PostalCodePatternExclusion, ...]:
    """Exclusions from a comma-separated pattern list, catalog style."""
    return tuple(
        PostalCodePatternExclusion(
            product.value,
            country,
            tuple(pattern.strip().upper() for pattern in patterns.split(",") if pattern.strip()),
            region,
            parties,
        )
        for product in products
    )


PARCEL_CONNECT_PRODUCTS = (*PARCEL_CONNECT_PLUS, *PARCEL_CONNECT)
NL_CARIBBEAN = "Aruba, Bonaire, Curaçao, Saba, Sint Maarten, and Sint Eustatius"
NL_CARIBBEAN_CODES = ("AW", "BQ", "CW", "SX")
CATALOG = "Product API catalog postalCodeExcludes"
ROAD_FREIGHT_STANDARD = (ShippingService.dhl_freight_sweden_road_freight_standard,)
ROAD_FREIGHT_PRIORITY = (ShippingService.dhl_freight_sweden_road_freight_priority,)
HOME_DELIVERY_INTERNATIONAL = (
    ShippingService.dhl_freight_sweden_home_delivery_international_b2c,
)

# Excluded areas without postal-code ranges. The manual's GB entry for 112
# (§5.3 p18) and 109 (§5.14 p63) names Jersey (JE), Guernsey (GY), and
# Northern Ireland (BT), matched as postcode prefixes. Its NL Caribbean
# islands for 112, 109, and 107 (§5.15 p66) carry no postal codes; they are
# excluded under their own country codes, which reach DHL unchanged.
# For 202, 233, and 601, for which the manual lists no excluded areas other
# than 202's UA range, the patterns are the Product API catalog's
# postalCodeExcludes quoted verbatim from the product matches answers of
# 2026-10-06 (tests/dhl_freight_sweden/fixtures/sandbox/
# lookup-product-matches-se-fi-00100.json). 601's DK list reads 2142 where
# the others read 2412; it is applied as 2412 (Christiansø), the code the
# other products list.
POSTAL_CODE_PATTERN_EXCLUSIONS: typing.Tuple[PostalCodePatternExclusion, ...] = (
    *_patterns(
        PARCEL_CONNECT_PRODUCTS, "GB", "Jersey, Guernsey, and Northern Ireland", "JE*,GY*,BT*"
    ),
    *(
        exclusion
        for country in NL_CARIBBEAN_CODES
        for exclusion in (
            *_patterns(PARCEL_CONNECT_PRODUCTS, country, NL_CARIBBEAN, "*"),
            *_patterns(PARCEL_RETURN_CONNECT, country, NL_CARIBBEAN, "*", parties=SHIPPER),
        )
    ),
    *_patterns(ROAD_FREIGHT_STANDARD, "DK", CATALOG, "39*, ???,2412"),
    *_patterns(ROAD_FREIGHT_STANDARD, "ES", CATALOG, "35*,38*,51*,52*"),
    *_patterns(ROAD_FREIGHT_STANDARD, "FR", CATALOG, "97*"),
    *_patterns(ROAD_FREIGHT_STANDARD, "GB", CATALOG, "GY*,JE*"),
    *_patterns(ROAD_FREIGHT_STANDARD, "NO", CATALOG, "917*,8099"),
    *_patterns(ROAD_FREIGHT_STANDARD, "PT", CATALOG, "9*"),
    *_patterns(ROAD_FREIGHT_PRIORITY, "DK", CATALOG, "39*, ???,2412"),
    *_patterns(ROAD_FREIGHT_PRIORITY, "ES", CATALOG, "35*,38*,51*,52*"),
    *_patterns(ROAD_FREIGHT_PRIORITY, "NO", CATALOG, "917*,8099"),
    *_patterns(ROAD_FREIGHT_PRIORITY, "PT", CATALOG, "9*"),
    *_patterns(HOME_DELIVERY_INTERNATIONAL, "DK", CATALOG, "39*,???,2412"),
    *_patterns(HOME_DELIVERY_INTERNATIONAL, "ES", CATALOG, "35*,38*,51*,52*"),
    *_patterns(HOME_DELIVERY_INTERNATIONAL, "FR", CATALOG, "97*"),
    *_patterns(HOME_DELIVERY_INTERNATIONAL, "GB", CATALOG, "GY*,JE*"),
    *_patterns(HOME_DELIVERY_INTERNATIONAL, "NO", CATALOG, "917*,8099"),
    *_patterns(HOME_DELIVERY_INTERNATIONAL, "PT", CATALOG, "9*"),
)


def postal_code_key(
    country_code: typing.Optional[str], postal_code: typing.Optional[str]
) -> typing.Optional[int]:
    """The compared digits of a postal code, or None when it is malformed."""
    postal_format = POSTAL_CODE_FORMATS.get((country_code or "").upper())
    match = lib.identity(
        re.fullmatch(postal_format.pattern, normalized_postal_code(country_code, postal_code))
        if postal_format
        else None
    )
    return int(match.group("key")) if match else None


class ExcludedParty(typing.NamedTuple):
    exclusion: Exclusion
    party: str
    postal_code: typing.Optional[str]
    well_formed: bool


def excluded_party_message(product_code: str, excluded: "ExcludedParty") -> str:
    exclusion = excluded.exclusion
    direction = "to" if excluded.party == "recipient" else "from"
    excluded_codes = exclusion.excluded_codes()

    return lib.identity(
        f"Product {product_code} does not ship {direction} {excluded_codes}; "
        f"got {excluded.party} postal code {excluded.postal_code}"
        if excluded.well_formed
        else f"Product {product_code} {direction} {exclusion.country} requires a "
        f"{excluded.party} {exclusion.required_code()} to rule out {excluded_codes}; "
        f"got {excluded.postal_code!r}"
    )


def excluded_party(
    product_code: str,
    addresses: typing.Mapping[str, typing.Mapping[str, typing.Any]],
    skip_missing: bool = False,
) -> typing.Optional[ExcludedParty]:
    """The first party an exclusion bars the product from, if any.

    ``addresses`` maps party names to ``country_code``/``postal_code`` dicts.
    ``skip_missing`` leaves a party without a postal code unchecked instead
    of treating it as excluded.
    """
    exclusions: typing.Tuple[Exclusion, ...] = (
        *POSTAL_CODE_EXCLUSIONS,
        *POSTAL_CODE_PATTERN_EXCLUSIONS,
    )
    return next(
        (
            ExcludedParty(exclusion, party, postal_code, verdict is True)
            for exclusion in exclusions
            if exclusion.product == product_code
            for party in exclusion.parties
            for address in [addresses.get(party) or {}]
            if (address.get("country_code") or "").upper() == exclusion.country
            for postal_code in [address.get("postal_code")]
            for verdict in [exclusion.verdict(postal_code)]
            if verdict is True
            or (verdict is None and not (skip_missing and not str(postal_code or "").strip()))
        ),
        None,
    )


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
