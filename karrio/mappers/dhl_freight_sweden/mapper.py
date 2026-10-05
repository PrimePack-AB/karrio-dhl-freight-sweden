"""Karrio DHL Freight client mapper."""

import typing
import karrio.lib as lib
import karrio.api.mapper as mapper
import karrio.core.models as models
import karrio.providers.dhl_freight_sweden as provider
import karrio.mappers.dhl_freight_sweden.settings as provider_settings


class Mapper(mapper.Mapper):
    # Narrows the SDK base attribute to the connector settings the gateway
    # constructs this mapper with; pyright treats mutable attributes as invariant.
    settings: provider_settings.Settings  # pyright: ignore[reportIncompatibleVariableOverride]

    def create_address_validation_request(
        self, payload: models.AddressValidationRequest
    ) -> lib.Serializable:
        return provider.address_validation_request(payload, self.settings)


    def parse_address_validation_response(
        self, response: lib.Deserializable
    ) -> typing.Tuple[models.AddressValidationDetails, typing.List[models.Message]]:
        return provider.parse_address_validation_response(response, self.settings)

    def create_rate_request(
        self, payload: models.RateRequest
    ) -> lib.Serializable:
        return provider.rate_request(payload, self.settings)


    def parse_rate_response(
        self, response: lib.Deserializable
    ) -> typing.Tuple[typing.List[models.RateDetails], typing.List[models.Message]]:
        return provider.parse_rate_response(response, self.settings)

    def create_shipment_request(
        self, payload: models.ShipmentRequest
    ) -> lib.Serializable:
        return provider.shipment_request(payload, self.settings)
    
    def create_cancel_shipment_request(
        self, payload: models.ShipmentCancelRequest
    ) -> lib.Serializable[str]:
        return provider.shipment_cancel_request(payload, self.settings)
    
    
    # The SDK base annotates a non-optional ConfirmationDetails, but the
    # unsupported-cancellation stub returns None details with a message.
    def parse_cancel_shipment_response(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, response: lib.Deserializable[dict]
    ) -> typing.Tuple[
        typing.Optional[models.ConfirmationDetails], typing.List[models.Message]
    ]:
        return provider.parse_shipment_cancel_response(response, self.settings)
    
    def parse_shipment_response(
        self, response: lib.Deserializable[typing.List[dict]]
    ) -> typing.Tuple[models.ShipmentDetails, typing.List[models.Message]]:
        return provider.parse_shipment_response(response, self.settings)
    
