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



class TerritoryPostalCodes(typing.NamedTuple):
    """The postal codes of a territory booked under its parent country.

    A code matches when, normalised under the parent, it is numeric and lies
    in one of ``ranges`` or has ``digits`` digits.
    """

    name: str
    parent: str
    ranges: typing.Tuple[typing.Tuple[int, int], ...]
    digits: typing.Optional[int] = None

    def describe(self) -> str:
        article = "an" if self.parent[0] in "AEFHILMNORSX" else "a"
        ranges = " or ".join(f"{low}-{high}" for low, high in self.ranges)
        digits = f" or of {_DIGIT_WORDS.get(self.digits, str(self.digits))} digits" if self.digits else ""
        return f"{article} {self.parent} postal code in {ranges}{digits}"

    def matches(self, postal_code: typing.Optional[str]) -> bool:
        postal = normalized_postal_code(self.parent, postal_code)
        return postal.isdigit() and (
            any(low <= int(postal) <= high for low, high in self.ranges)
            or len(postal) == self.digits
        )


_DIGIT_WORDS = {3: "three"}

# The TERRITORY_PARENTS entries whose territory lies in a postal-code range of
# the parent, from NON_EU_VAT_POSTAL_RANGES and the Faroese three-digit codes
# of NON_EU_VAT_POSTAL_CODE_LENGTHS. JE, GG, IM, and XI have no numeric range.
TERRITORY_POSTAL_CODES: typing.Dict[str, TerritoryPostalCodes] = {
    "AX": TerritoryPostalCodes("Åland", "FI", ((22000, 22999),)),
    "IC": TerritoryPostalCodes("Canary Islands", "ES", ((35000, 35999), (38000, 38999))),
    "EA": TerritoryPostalCodes("Ceuta and Melilla", "ES", ((51000, 51999), (52000, 52999))),
    "FO": TerritoryPostalCodes("Faroe Islands", "DK", ((3800, 3999),), digits=3),
    "GL": TerritoryPostalCodes("Greenland", "DK", ((3800, 3999),)),
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

# Product manual v5.26 lists NO as the only valid country of Customs, joint
# declaration (§6.8 p98); product matches on account 116768 list
# customsJointDeclaration among 601's customs services to CH (tests/
# dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-8001.json).
JOINT_DECLARATION_OPTION = "dhl_freight_sweden_customs_joint_declaration"
JOINT_DECLARATION_COUNTRIES: typing.Tuple[str, ...] = ("NO", "CH")

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
# Without an EKAER or UIT declaration or number, the connector declares a
# TRANSPORT_DECLARATION_PRODUCTS shipment free below this total gross weight
# and refuses it at or above. The RO UIT exception covers goods "less than
# 500 kg" (with a value under 10,000 RON) and the HU EKAER threshold for
# risky products is 500 kg (with HUF 1,000,000); the connector checks
# weight only.
TRANSPORT_DECLARATION_FREE_WEIGHT_LIMIT_KG = 500.0
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


class BookingSystem(lib.StrEnum):
    """The DHL Freight Sweden system a product is booked in.

    The systems number customers separately, so the consignor id of a
    domestic product is the domestic customer number and that of an
    international product the international customer number
    ("utrikeskundnummer").
    """

    domestic = "domestic"
    international = "international"


# Booking system per connector product from the UNB recipient addresses of
# the DHL Freight (Sweden) IFTMIN shipment instruction v3.7 p10: the
# connector's products under 7330924000002 are domestic, and 202, 205, 233,
# SPI, and 601 under 7381000065002 international. p10 also lists 501
# (domestic) and 232 and PPI (international), which the connector does not
# implement. 104 goes to DPST, and its "DHL account number format" row of product manual
# v5.26 (§5.13 p60) asks for 6 digits like the domestic products' rows; the
# international products' rows ask for up to 35 alphanumeric characters
# (§5.4 p24, §5.9 p43, §5.10 p48, §5.11 p53, §5.19 p83). 107 has no such row.
PRODUCT_BOOKING_SYSTEMS: typing.Dict[str, BookingSystem] = {
    **{
        product.value: BookingSystem.domestic
        for product in (
            ShippingService.dhl_freight_sweden_paket,
            ShippingService.dhl_freight_sweden_parcel_connect_plus,
            ShippingService.dhl_freight_sweden_special,
            ShippingService.dhl_freight_sweden_pall,
            ShippingService.dhl_freight_sweden_stycke,
            ShippingService.dhl_freight_sweden_parti,
            ShippingService.dhl_freight_sweden_service_point_b2c,
            ShippingService.dhl_freight_sweden_service_point_c2b,
            ShippingService.dhl_freight_sweden_parcel_connect_b2c,
            ShippingService.dhl_freight_sweden_parcel_return_connect_c2b,
            ShippingService.dhl_freight_sweden_hemleverans_paket_b2c,
            ShippingService.dhl_freight_sweden_home_delivery_b2c,
            ShippingService.dhl_freight_sweden_home_delivery_c2b,
            ShippingService.dhl_freight_sweden_home_delivery_c2b_502,
        )
    },
    **{
        product.value: BookingSystem.international
        for product in (
            ShippingService.dhl_freight_sweden_road_freight_standard,
            ShippingService.dhl_freight_sweden_road_freight_direct,
            ShippingService.dhl_freight_sweden_road_freight_priority,
            ShippingService.dhl_freight_sweden_standard_pallet_international,
            ShippingService.dhl_freight_sweden_home_delivery_international_b2c,
        )
    },
}

# The Transport Instruction API caps Party.id at 15 characters
# (vendor/se-api-farm/transport-instruction-2.10.0.json), below the 35 that
# the manual allows an international customer number.
PARTY_ID_MAX_LENGTH = 15


def booking_system(product_code: str) -> BookingSystem:
    """The system ``product_code`` is booked in; codes outside the table are domestic."""
    return PRODUCT_BOOKING_SYSTEMS.get(product_code, BookingSystem.domestic)


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
    # SENT_FREE "false" (§5.4 p23). The sandbox rejected a 109 shipment to PL
    # without the identifiers or SENT_FREE "true" on 2026-10-05 (validation
    # error 22001, tests/dhl_freight_sweden/fixtures/sandbox/
    # rejection-22001-109-se-pl-without-sent.json) and accepted the same
    # request on 2026-10-08 (booking-2906769613-109-se-pl-without-sent.json).
    # Without SENT_FREE or either identifier, the connector declares the
    # shipment SENT free.
    dhl_freight_sweden_sent_free = lib.OptionEnum("SENT_FREE", bool)
    dhl_freight_sweden_sent_ref = lib.OptionEnum("SENT_REF", str)
    dhl_freight_sweden_sent_carkey = lib.OptionEnum("SENT_CARKEY", str)

    # EKAER (HU, AN..20) and UIT (RO, AN..19) declarations, see
    # TRANSPORT_DECLARATIONS and TRANSPORT_DECLARATION_FREE_WEIGHT_LIMIT_KG.
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


FLAG_TRUE_SPELLINGS: typing.FrozenSet[str] = frozenset({"true", "1", "yes"})
FLAG_FALSE_SPELLINGS: typing.FrozenSet[str] = frozenset({"false", "0", "no"})


@attr.s(auto_attribs=True, frozen=True)
class InvalidFlag:
    """A raw bool-option value that spells neither true, false, nor unset."""

    value: typing.Any


Flag = typing.Union[bool, None, InvalidFlag]


def parse_flag(value: typing.Any) -> Flag:
    """Read a raw bool-option value strictly.

    The SDK reads a bool option as ``value is not False``, so "false", 0, and
    None would select it. True, 1, and "true", "1", "yes" read as True;
    False, 0, and "false", "0", "no" read as False (strings trimmed and
    case-insensitive); None and a blank string read as None (unset). Any
    other value, including floats and other integers, is an InvalidFlag.
    """
    if value is None or isinstance(value, bool):
        return value

    if isinstance(value, int):
        return {1: True, 0: False}.get(value, InvalidFlag(value))

    if isinstance(value, str):
        spelling = value.strip().lower()

        if not spelling:
            return None
        if spelling in FLAG_TRUE_SPELLINGS:
            return True
        if spelling in FLAG_FALSE_SPELLINGS:
            return False

    return InvalidFlag(value)


def _flag_values(options: typing.Dict[str, typing.Any]) -> typing.Dict[str, Flag]:
    """The strictly read value of every bool-typed option key, aliases included."""
    return {
        key: parse_flag(value)
        for key, value in options.items()
        if key in ShippingOption and ShippingOption[key].value.type is bool  # type: ignore
    }


def invalid_flags(options: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
    """The raw value of each bool-typed option key that reads as an InvalidFlag."""
    return {
        key: flag.value
        for key, flag in _flag_values(options).items()
        if isinstance(flag, InvalidFlag)
    }


def shipping_options_initializer(
    options: dict,
    package_options: typing.Optional[units.ShippingOptions] = None,
) -> units.ShippingOptions:
    """Apply default values to the given options.

    Bool-typed options are read with ``parse_flag``: unset and invalid values
    are dropped, so the option reads as absent, and the initializer never
    raises. ``shipment_request`` refuses the invalid values it finds through
    ``invalid_flags``.
    """

    if package_options is not None:
        options.update(package_options.content)

    flags = _flag_values(options)
    readable = {
        key: flags.get(key, value)
        for key, value in options.items()
        if key not in flags or isinstance(flags[key], bool)
    }

    def items_filter(key: str) -> bool:
        return key in ShippingOption  # type: ignore

    return units.ShippingOptions(readable, ShippingOption, items_filter=items_filter)


def _countries(codes: str) -> typing.List[str]:
    return codes.split()


# Valid countries per product, from the "Valid countries" tables of product
# manual v5.26 section 5. Product manual v5.26 lists GB for 109 and 112 only
# according to a separate agreement (§5.3 p18, §5.14 p63, Appendix G p200),
# which the connector does not check. For 112 the manual requires the Print
# and TransportInstruction APIs for FR, which the connector books through,
# and excludes FR postal codes 97100-99999 (§5.3 p18, Appendix G p199).
PARCEL_CONNECT_B2C_COUNTRIES = _countries(
    "AT BE BG CZ DE DK EE ES FI FR GB HR HU IE IT LT LU LV NL NO PL PT RO SI SK"
)  # §5.14 p63
PARCEL_CONNECT_PLUS_COUNTRIES = _countries(
    "AT BE BG CZ DE DK EE ES FI FR GB HR HU IE IT LT LU LV NL NO PL PT RO SI SK"
)  # §5.3 p18
PARCEL_RETURN_CONNECT_COUNTRIES = _countries(
    "AT BE BG CZ DE DK EE ES FI FR HR HU IE IT LT LU LV NL NO PL PT RO SI SK"
)  # §5.15 p66
# 202 §5.4 p23, 205 §5.9 p43, SPI §5.11 p52.
ROAD_FREIGHT_COUNTRIES = _countries(
    "AD AL AM AT AZ BA BE BG CH CY CZ DE DK EE ES FI FR GB GE GI GR HR HU IE "
    "IT KG KZ LI LT LU LV MA MC MD ME MK MT NL NO PL PT RO RS SE SI SK SM TJ "
    "TR UA UZ XK"
)
ROAD_FREIGHT_PRIORITY_COUNTRIES = _countries(
    "AT BE BG CH CZ DE DK EE ES FI FR GB HR HU IE IT LI LT LU LV NL NO PL PT "
    "RO SE SI SK"
)  # §5.10 p47
HOME_DELIVERY_INTERNATIONAL_COUNTRIES = _countries(
    "AT BE BG CH CZ DE DK EE ES FI FR GB GR HR HU IE IT LT LU LV NL NO PL PT "
    "RO SE SI SK"
)  # §5.19 p82

SWEDEN = frozenset(["SE"])


class ProductLane(typing.NamedTuple):
    """Shipper and recipient countries a product carries shipments between."""

    origins: typing.FrozenSet[str]
    destinations: typing.FrozenSet[str]


def _from_sweden(countries: typing.Iterable[str]) -> typing.Tuple[ProductLane, ...]:
    return (ProductLane(SWEDEN, frozenset(countries) - SWEDEN),)


def _to_sweden(countries: typing.Iterable[str]) -> typing.Tuple[ProductLane, ...]:
    return (ProductLane(frozenset(countries) - SWEDEN, SWEDEN),)


def _to_and_from_sweden(countries: typing.Iterable[str]) -> typing.Tuple[ProductLane, ...]:
    return (*_from_sweden(countries), *_to_sweden(countries))


DOMESTIC_PRODUCTS = (
    ShippingService.dhl_freight_sweden_paket,
    ShippingService.dhl_freight_sweden_special,
    ShippingService.dhl_freight_sweden_pall,
    ShippingService.dhl_freight_sweden_stycke,
    ShippingService.dhl_freight_sweden_parti,
    ShippingService.dhl_freight_sweden_service_point_b2c,
    ShippingService.dhl_freight_sweden_service_point_c2b,
    ShippingService.dhl_freight_sweden_hemleverans_paket_b2c,
    ShippingService.dhl_freight_sweden_home_delivery_b2c,
    ShippingService.dhl_freight_sweden_home_delivery_c2b,
    ShippingService.dhl_freight_sweden_home_delivery_c2b_502,
)

# Lanes per product. The overview classifies each product as domestic or
# international (§5.1 p13), and the international products' lists include
# SE as the Swedish end of a lane: 202, 205, 233, SPI, and 601 "can be used
# to and from Sweden" (§5.4 p22, §5.9 p41, §5.10 p46, §5.11 p51, §5.19 p81),
# and 107 returns a 109 shipment from its listed countries to the original
# sender in SE (§5.15 p65).
PRODUCT_LANES: typing.Dict[str, typing.Tuple[ProductLane, ...]] = {
    **{product.value: (ProductLane(SWEDEN, SWEDEN),) for product in DOMESTIC_PRODUCTS},
    ShippingService.dhl_freight_sweden_parcel_connect_b2c.value: _from_sweden(
        PARCEL_CONNECT_B2C_COUNTRIES
    ),
    ShippingService.dhl_freight_sweden_parcel_connect_plus.value: _from_sweden(
        PARCEL_CONNECT_PLUS_COUNTRIES
    ),
    ShippingService.dhl_freight_sweden_parcel_return_connect_c2b.value: _to_sweden(
        PARCEL_RETURN_CONNECT_COUNTRIES
    ),
    ShippingService.dhl_freight_sweden_road_freight_standard.value: _to_and_from_sweden(
        ROAD_FREIGHT_COUNTRIES
    ),
    ShippingService.dhl_freight_sweden_road_freight_direct.value: _to_and_from_sweden(
        ROAD_FREIGHT_COUNTRIES
    ),
    ShippingService.dhl_freight_sweden_standard_pallet_international.value: _to_and_from_sweden(
        ROAD_FREIGHT_COUNTRIES
    ),
    ShippingService.dhl_freight_sweden_road_freight_priority.value: _to_and_from_sweden(
        ROAD_FREIGHT_PRIORITY_COUNTRIES
    ),
    ShippingService.dhl_freight_sweden_home_delivery_international_b2c.value: _to_and_from_sweden(
        HOME_DELIVERY_INTERNATIONAL_COUNTRIES
    ),
}

PRODUCT_LANE_CITATIONS: typing.Dict[str, str] = {
    ShippingService.dhl_freight_sweden_paket.value: "§5.2 p15",
    ShippingService.dhl_freight_sweden_parcel_connect_plus.value: "§5.3 p18",
    ShippingService.dhl_freight_sweden_road_freight_standard.value: "§5.4 p23",
    ShippingService.dhl_freight_sweden_special.value: "§5.5 p27",
    ShippingService.dhl_freight_sweden_pall.value: "§5.6 p30",
    ShippingService.dhl_freight_sweden_stycke.value: "§5.7 p34",
    ShippingService.dhl_freight_sweden_parti.value: "§5.8 p38",
    ShippingService.dhl_freight_sweden_road_freight_direct.value: "§5.9 p43",
    ShippingService.dhl_freight_sweden_road_freight_priority.value: "§5.10 p47",
    ShippingService.dhl_freight_sweden_standard_pallet_international.value: "§5.11 p52",
    ShippingService.dhl_freight_sweden_service_point_b2c.value: "§5.12 p56",
    ShippingService.dhl_freight_sweden_service_point_c2b.value: "§5.13 p59",
    ShippingService.dhl_freight_sweden_parcel_connect_b2c.value: "§5.14 p63",
    ShippingService.dhl_freight_sweden_parcel_return_connect_c2b.value: "§5.15 p66",
    ShippingService.dhl_freight_sweden_hemleverans_paket_b2c.value: "§5.16 p68",
    ShippingService.dhl_freight_sweden_home_delivery_b2c.value: "§5.17 p72",
    ShippingService.dhl_freight_sweden_home_delivery_c2b.value: "§5.18 p76",
    ShippingService.dhl_freight_sweden_home_delivery_c2b_502.value: "§5.18 p76",
    ShippingService.dhl_freight_sweden_home_delivery_international_b2c.value: "§5.19 p82",
}


def lane_served(
    product_code: str,
    origin: typing.Optional[str],
    destination: typing.Optional[str],
) -> bool:
    """Whether the product carries shipments from ``origin`` to ``destination``.

    Country codes are compared as given, so territory codes must already be
    replaced by their parent country (``with_parent_country``). A missing
    country leaves that party unchecked, and a product absent from
    ``PRODUCT_LANES`` serves every lane.
    """
    lanes = PRODUCT_LANES.get(product_code)
    origin_code, destination_code = (origin or "").upper(), (destination or "").upper()
    return lanes is None or any(
        (not origin_code or origin_code in lane.origins)
        and (not destination_code or destination_code in lane.destinations)
        for lane in lanes
    )


def unserved_lane_message(
    product_code: str,
    origin: typing.Optional[str],
    destination: typing.Optional[str],
) -> str:
    return (
        f"Product {product_code} does not ship "
        f"from {origin or 'an unknown country'} to {destination or 'an unknown country'} "
        f"(product manual v5.26 {PRODUCT_LANE_CITATIONS[product_code]})"
    )




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


def _destinations(product: ShippingService) -> typing.List[str]:
    """The recipient countries of a product's lanes from SE, sorted."""
    return sorted(
        country
        for lane in PRODUCT_LANES[product.value]
        if lane.origins == SWEDEN
        for country in lane.destinations
    )


# The API Farm publishes no money-rate API for these products (the pricequote
# API is not integrated); these defaults seed the rate-sheet catalog with the
# carrier's service levels and zones so universal rating can present the
# product set. The rate=0.0 placeholders are overridden by the merchant's
# negotiated prices at runtime.
#
# The rating mixin classifies a lane by the recipient: delivery in the
# account country (SE) counts as domicile. Zones list the recipient
# countries of each product's export lane, and rating drops rates on lanes
# outside PRODUCT_LANES, which also covers merchant rate sheets and the
# shipper side the zones cannot express:
# - Domestic products: domicile-only, Sweden zone.
# - Export products (109, 112, 202, 205, 233, SPI, 601): international-only,
#   a zone of their valid countries other than SE. Their import lanes into
#   SE count as domicile, so they do not rate.
# - Parcel Return Connect (107): its lanes end in SE, so its domicile flag
#   and Sweden zone let it rate; PRODUCT_LANES restricts the shipper.
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
        zones=[
            models.ServiceZone(
                label="International",
                rate=0.0,
                country_codes=_destinations(ShippingService.dhl_freight_sweden_road_freight_standard),
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
        zones=[
            models.ServiceZone(
                label="International",
                rate=0.0,
                country_codes=_destinations(ShippingService.dhl_freight_sweden_road_freight_direct),
            )
        ],
    ),
    models.ServiceLevel(
        service_name="Road Freight Priority",
        service_code="dhl_freight_sweden_road_freight_priority",
        carrier_service_code="233",
        currency="SEK",
        domicile=False,
        international=True,
        zones=[
            models.ServiceZone(
                label="International",
                rate=0.0,
                country_codes=_destinations(ShippingService.dhl_freight_sweden_road_freight_priority),
            )
        ],
    ),
    models.ServiceLevel(
        service_name="Home Delivery International B2C",
        service_code="dhl_freight_sweden_home_delivery_international_b2c",
        carrier_service_code="601",
        currency="SEK",
        domicile=False,
        international=True,
        zones=[
            models.ServiceZone(
                label="International",
                rate=0.0,
                country_codes=_destinations(ShippingService.dhl_freight_sweden_home_delivery_international_b2c),
            )
        ],
    ),
    models.ServiceLevel(
        service_name="Parcel Connect B2C",
        service_code="dhl_freight_sweden_parcel_connect_b2c",
        carrier_service_code="109",
        currency="SEK",
        domicile=False,
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
        domicile=False,
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
        zones=[
            models.ServiceZone(
                label="International",
                rate=0.0,
                country_codes=_destinations(ShippingService.dhl_freight_sweden_standard_pallet_international),
            )
        ],
    ),
]
