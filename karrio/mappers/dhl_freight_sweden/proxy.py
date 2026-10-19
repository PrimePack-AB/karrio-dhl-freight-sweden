"""Karrio DHL Freight client proxy."""

import typing
import urllib.parse

import karrio.lib as lib
import karrio.api.proxy as proxy
import karrio.core.models as models
import karrio.mappers.dhl_freight_sweden.settings as provider_settings
import karrio.providers.dhl_freight_sweden.address as provider_address
import karrio.providers.dhl_freight_sweden.product_matches as provider_product_matches
import karrio.providers.dhl_freight_sweden.utils as provider_utils
import karrio.schemas.dhl_freight_sweden.print_request_by_id as dhl_freight_sweden_print
from karrio.universal.mappers.rating_proxy import RatingMixinProxy


class Proxy(proxy.Proxy):
    # Narrows the SDK base attribute to the connector settings the gateway
    # constructs this proxy with; pyright treats mutable attributes as invariant.
    settings: provider_settings.Settings  # pyright: ignore[reportIncompatibleVariableOverride]

    def validate_address(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        """Look up the postal-code route for an address (PostalCodes API).

        GETs ``/postalcodes/{countryCode}/{postalCode}/route`` with the
        standard client-key header; the route body feeds the unified
        ``AddressValidationDetails`` through the shared evaluation helpers.
        A failed lookup (network error, timeout, or a body that is not JSON)
        deserializes to an empty body, which the helpers report as
        unverified rather than aborting the caller.
        """
        params = request.serialize()
        response = lib.failsafe(
            lambda: lib.request(
                url=f"{self.settings.postal_code_api_url}/postalcodes/"
                f"{urllib.parse.quote(str(params.get('country_code') or '').upper(), safe='')}/"
                f"{urllib.parse.quote(str(params.get('postal_code') or ''), safe='')}/route",
                trace=self.trace_as("json"),
                method="GET",
                headers={"client-key": self.settings.client_key},
                on_error=lib.error_decoder,
            )
        )

        return lib.Deserializable(
            response, provider_address.to_route_body, request.ctx
        )

    def get_rates(self, request: lib.Serializable) -> lib.Deserializable:
        """Resolve static prices from the server-side rate sheet.

        The SE API Farm pricequote API is not integrated, so rating
        delegates to the universal rating mixin against the service levels
        seeded in ``units.DEFAULT_SERVICES``; no carrier call is made.
        """
        # RatingMixinProxy.get_rates reads only self.settings, which this
        # proxy's RatingMixinSettings-derived settings satisfy.
        response = RatingMixinProxy.get_rates(
            typing.cast(RatingMixinProxy, self), request
        )

        return lib.Deserializable(response.deserialize(), lib.identity, request.ctx)

    def create_shipment(
        self, request: lib.Serializable
    ) -> lib.Deserializable[typing.List[dict]]:
        """Book a transport instruction, then print its documents by id.

        The shipment id only exists once the booking response returns, so the
        by-id print request is completed here with the runtime id and posted
        to ``/print/printdocumentsbyid`` — the booked shipment is not re-sent.
        Two config-gated pre-flights run first, product matches and then
        address validation; their warnings travel to the parser as optional
        trailing elements.
        """
        ctx = request.ctx or {}
        headers = {
            "Content-Type": "application/json",
            "client-key": self.settings.client_key,
        }
        warnings = [
            *self._product_match_messages(request),
            *self._destination_route_messages(request),
        ]

        booking = lib.request(
            url=f"{self.settings.transport_instruction_url}/transportinstruction/sendtransportinstruction",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="POST",
            headers=headers,
            on_error=lib.error_decoder,
        )

        instruction = (provider_utils.to_dict(booking) or {}).get("transportInstruction") or {}
        shipment_id = instruction.get("id")

        printed = lib.identity(
            lib.request(
                url=f"{self.settings.print_url}/print/printdocumentsbyid",
                data=lib.to_json(
                    lib.to_dict(
                        dhl_freight_sweden_print.PrintRequestByIDType(
                            shipmentIds=[shipment_id],
                            options=lib.to_object(
                                dhl_freight_sweden_print.OptionsType,
                                ctx.get("print_options") or {},
                            ),
                        )
                    )
                ),
                trace=self.trace_as("json"),
                method="POST",
                headers=headers,
                on_error=lib.error_decoder,
            )
            if shipment_id
            else "{}"
        )

        return lib.Deserializable(
            [booking, printed, *warnings],
            lambda responses: [
                provider_utils.to_dict(response) for response in responses
            ],
            ctx,
        )

    def schedule_pickup(self, request: lib.Serializable) -> lib.Deserializable[dict]:
        """Book a pickup through the PickupRequest API.

        The API has no cancel or update endpoint and a booked pickup cannot
        be cancelled electronically (product manual v5.26 §5.2 p14), so the
        proxy defines neither ``modify_pickup`` nor ``cancel_pickup``.
        """
        response = lib.request(
            url=f"{self.settings.pickup_request_url}/pickuprequest/pickuprequest",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "client-key": self.settings.client_key,
            },
            on_error=lib.error_decoder,
        )

        return lib.Deserializable(response, provider_utils.to_dict, request.ctx)

    def _destination_route_messages(
        self, request: lib.Serializable
    ) -> typing.List[models.Message]:
        """Run the config-gated destination servability pre-flight.

        Off mode, products without a documented per-product flag, non-Swedish
        consignees, and missing postal codes skip the check with no HTTP
        call; the mode branch and fail-open semantics live in the provider's
        ``check_booking_route``.
        """
        mode = _preflight_mode(
            self.settings.connection_config.address_validation.state
        )
        destination = _booking_destination(provider_utils.to_dict(request.serialize()))

        if mode == "off" or destination is None:
            return []

        lookup = lib.Serializable(
            dict(
                country_code=destination["country_code"],
                postal_code=destination["postal_code"],
            ),
            provider_utils.to_dict,
            dict(service=destination["product"]),
        )
        return provider_address.check_booking_route(
            self.validate_address(lookup), self.settings, mode
        )

    def _product_match_messages(
        self, request: lib.Serializable
    ) -> typing.List[models.Message]:
        """Run the config-gated product matches booking guard.

        Off mode and ``PRODUCT_MATCH_UNGUARDED`` products skip the lookup
        silently; a booking whose consignor, or whose consignee and access
        point, lack a postal or country code skips it with a warning. A lookup
        that raises (a non-JSON HTTP error body, a network error) is turned
        into a message, so it leaves availability unverified rather than
        failing the booking.
        """
        mode = _preflight_mode(self.settings.connection_config.product_matches.state)
        data = provider_utils.to_dict(request.serialize())
        criteria = provider_product_matches.booking_match_criteria(data)

        if mode == "off" or criteria is None:
            return []

        if isinstance(criteria, provider_product_matches.CriteriaUnavailable):
            return [
                provider_product_matches.criteria_unavailable_warning(
                    criteria, self.settings
                )
            ]

        try:
            products, messages = provider_product_matches.parse_product_matches_response(
                self.find_product_matches(
                    lib.Serializable(criteria, provider_utils.to_dict)
                ),
                self.settings,
            )
        except Exception as exception:
            products, messages = [], [
                provider_product_matches.lookup_failure(exception, self.settings)
            ]

        return provider_product_matches.check_booking_product(
            criteria,
            str(data.get("productCode")),
            products,
            messages,
            self.settings,
            mode,
            (request.ctx or {}).get("separate_agreement"),
        )

    def find_product_matches(
        self, request: lib.Serializable
    ) -> lib.Deserializable[typing.Union[dict, list]]:
        """Look up matching products for an address pair (connector-local).

        POSTs the serialized ``MatchCriteria`` body to the Product API's
        ``/productmatches`` endpoint with the standard client-key headers; the
        caller invokes this duck-typed method directly on the proxy, as with
        the postnord ``find_service_points`` precedent.
        """
        response = lib.request(
            url=f"{self.settings.product_api_url}/productmatches",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "client-key": self.settings.client_key,
            },
            on_error=lib.error_decoder,
        )

        return lib.Deserializable(response, provider_utils.to_json_body)

    def find_service_points(
        self, request: lib.Serializable
    ) -> lib.Deserializable[typing.Union[dict, list]]:
        """Look up the nearest service points for an address (connector-local).

        POSTs the serialized ``NearestServicePointRequest`` body to the
        Servicepoint API's ``findnearestservicepoints`` endpoint with the
        standard client-key headers; the caller invokes this duck-typed method
        directly on the proxy, as with the postnord precedent.
        """
        response = lib.request(
            url=f"{self.settings.service_point_locator_url}/servicepoint/findnearestservicepoints",
            data=lib.to_json(request.serialize()),
            trace=self.trace_as("json"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "client-key": self.settings.client_key,
            },
            on_error=lib.error_decoder,
        )

        return lib.Deserializable(response, provider_utils.to_json_body, request.ctx)


def _preflight_mode(state: typing.Any) -> str:
    """Resolve a pre-flight mode setting to off, warn, or enforce.

    Config values are stored free-form: resolve case-insensitively and treat
    anything that names no mode as off, so an unrecognized value never
    silently enables a check.
    """
    mode = str(state or "").lower()
    return mode if mode in ("warn", "enforce") else "off"


def _booking_destination(data: dict) -> typing.Optional[dict]:
    """Consignee destination of a serialized transport instruction.

    Returns None unless the product has a documented per-product servability
    flag and the consignee is Swedish with a postal code — the pre-flight
    trigger scope.
    """
    parties = data.get("parties") or []
    consignee = next(
        (party for party in parties if party.get("type") == "Consignee"), None
    )
    address = (consignee or {}).get("address") or {}
    product = str(data.get("productCode") or "")
    postal_code = address.get("postalCode")

    if (
        product not in provider_address.PRODUCT_SERVICABILITY_FLAGS
        or str(address.get("countryCode") or "").upper() != "SE"
        or not postal_code
    ):
        return None

    return dict(
        country_code=str(address.get("countryCode")).upper(),
        postal_code=str(postal_code),
        product=product,
    )
