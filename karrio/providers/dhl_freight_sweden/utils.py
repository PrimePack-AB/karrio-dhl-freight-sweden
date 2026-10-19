import typing
import karrio.lib as lib
import karrio.core as core
import karrio.core.errors as errors
import karrio.providers.dhl_freight_sweden.units as units


class Settings(core.Settings):
    """DHL Freight (Sweden API Farm) connection settings."""

    client_key: str
    # karrio's reference builder (karrio.references.parse_type) maps only a
    # bare `str` annotation to the dashboard's string input; Optional[str]
    # serializes as its repr and the form renders a label with no input box.
    account_number: str = None  # pyright: ignore[reportAssignmentType]
    international_account_number: str = None  # pyright: ignore[reportAssignmentType]

    @property
    def carrier_name(self):
        return "dhl_freight_sweden"

    @property
    def server_url(self):
        """Base host for the SE API Farm.

        A per-connection ``server_url`` config value overrides the
        sandbox/production default, allowing a connection to pin a host.
        """
        return self.connection_config.server_url.state or (
            "https://test-api.freight-logistics.dhl.com"
            if self.test_mode
            else "https://api.freight-logistics.dhl.com"
        )

    @property
    def transport_instruction_url(self):
        return f"{self.server_url}/transportinstructionapi/v1"

    @property
    def print_url(self):
        return f"{self.server_url}/printapi/v1"

    @property
    def product_api_url(self):
        return f"{self.server_url}/productapi/v1"

    @property
    def service_point_locator_url(self):
        return f"{self.server_url}/servicepointlocatorapi/v1"

    @property
    def postal_code_api_url(self):
        return f"{self.server_url}/postalcodeapi/v1"

    @property
    def pickup_request_url(self):
        return f"{self.server_url}/pickuprequestapi/v1"

    @property
    def tracking_url(self):
        # The API Farm exposes no native shipment-tracking URL, so this uses the
        # public DHL Freight Sweden tracking widget keyed by shipment id.
        return "https://www.dhl.com/se-en/home/tracking/tracking-freight.html?submit=1&tracking-id={}"

    @property
    def connection_config(self) -> lib.units.ConnectionConfigOptions:
        return lib.to_connection_config(
            self.config or {},
            option_type=units.ConnectionConfig,
        )


def to_dict(value: typing.Any) -> dict:
    """``lib.to_dict`` for a value that encodes a JSON object.

    ``lib.to_dict`` is annotated as returning ``dict | list | Any`` and takes
    an implicitly optional ``clear_empty``, so it neither narrows to a dict nor
    fits the one-argument (de)serializer of ``lib.Serializable`` and
    ``lib.Deserializable``.
    """
    return typing.cast(dict, lib.to_dict(value))


def to_json_body(value: typing.Any) -> typing.Union[dict, list]:
    """``lib.to_dict`` for a response body that is a JSON object or array."""
    return typing.cast(typing.Union[dict, list], lib.to_dict(value))


class InternationalAccountNumberError(errors.ShippingSDKDetailedError):
    """Raised when an international product lacks a usable international customer number."""

    code = "SHIPPING_SDK_FIELD_ERROR"


def customer_number(product_code: str, settings: Settings) -> typing.Optional[str]:
    """The customer number ``product_code`` books under: ``account_number`` for
    domestic products, the guarded ``international_account_number`` for products
    of ``units.PRODUCT_BOOKING_SYSTEMS`` booked in DHL's international system.
    """
    system = units.booking_system(product_code)
    if system != units.BookingSystem.international:
        return settings.account_number

    number = (settings.international_account_number or "").strip()
    limit = units.PARTY_ID_MAX_LENGTH
    # DHL rejected non-digit Consignor ids with 22014 while accepting
    # 12345, 123456, and 1234567 (2026-10-13 sandbox probes), so the guard
    # checks digits only and no length rule; the manual's account number
    # rows allow up to 35 alphanumeric characters, pending DHL API Farm's
    # answer on the real number's format.
    if number and len(number) <= limit and number.isdigit():
        return number

    raise InternationalAccountNumberError(
        lib.identity(
            f"Product {product_code} is booked in DHL's international system "
            "and needs the international customer number; set "
            "international_account_number on the connection"
            if not number
            else f"The international customer number has {len(number)} "
            f"characters; the DHL Transport Instruction API accepts at most {limit}"
            if len(number) > limit
            else "The international customer number must be digits only; "
            "the DHL Transport Instruction API rejected a non-digit "
            "Consignor id with 22014"
        ),
        details={
            "international_account_number": lib.identity(
                dict(code="required", message="international customer number is required")
                if not number
                else dict(code="invalid", message=f"at most {limit} characters")
                if len(number) > limit
                else dict(code="invalid", message="digits only")
            )
        },
    )
