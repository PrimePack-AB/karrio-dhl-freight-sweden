"""DHL Freight (SE API Farm) carrier test fixtures and typed accessors.

The SDK types ``gateway.settings`` and ``gateway.proxy`` as the generic
core classes and ``lib.to_dict`` as a dict, list, or Any union; the
accessors below narrow them to what these tests know they hold, without
changing any runtime value.
"""

import email.message
import enum
import http
import io
import typing
import urllib.error

import karrio.core.errors as errors
import karrio.core.models as models
import karrio.lib as lib
import karrio.mappers.dhl_freight_sweden.proxy as connector_proxy
import karrio.mappers.dhl_freight_sweden.settings as connector_settings
import karrio.sdk as karrio


def _gateway(config: dict):
    return karrio.gateway["dhl_freight_sweden"].create(
        dict(
            id="123456789",
            test_mode=True,
            carrier_id="dhl_freight_sweden",
            client_key="TEST_CLIENT_KEY",
            account_number="1234567",
            config=config,
        )
    )


gateway = _gateway({})

# Connection-configured label type variant; the connector refuses ZPL.
zpl_gateway = _gateway({"label_type": "ZPL"})

# Booking pre-flight mode variants: the address_validation config gates the
# create_shipment route check only, never the unified validate_address.
# Mode values resolve case-insensitively; values naming no mode resolve to off.
warn_gateway = _gateway({"address_validation": "warn"})
enforce_gateway = _gateway({"address_validation": "enforce"})
warn_case_gateway = _gateway({"address_validation": "Warn"})
unrecognized_gateway = _gateway({"address_validation": "strict"})


def settings_of(gateway) -> connector_settings.Settings:
    return typing.cast(connector_settings.Settings, gateway.settings)


def proxy_of(gateway) -> connector_proxy.Proxy:
    return typing.cast(connector_proxy.Proxy, gateway.proxy)


def as_dict(value: typing.Any) -> typing.Dict[str, typing.Any]:
    """``value`` as a dict, asserting it is one."""
    assert isinstance(value, dict), type(value)
    return typing.cast(typing.Dict[str, typing.Any], value)


def as_list(value: typing.Any) -> typing.List[typing.Any]:
    """``value`` as a list, asserting it is one."""
    assert isinstance(value, list), type(value)
    return typing.cast(typing.List[typing.Any], value)


def serialize_request(request: lib.Serializable) -> typing.Dict[str, typing.Any]:
    """The serialized request payload as a plain dict."""
    return as_dict(lib.to_dict(request.serialize()))


def detail_keys(error: errors.ShippingSDKDetailedError) -> typing.Set[str]:
    """The keys of an SDK error's ``details``, which the SDK types as optional."""
    return set(error.details or {})


def members(enum_type: typing.Any) -> typing.List[enum.Enum]:
    """The members of a ``lib.Enum`` or ``lib.StrEnum``, whose base the SDK picks at runtime."""
    return list(enum_type)


def shipment_request(**fields: typing.Any) -> models.ShipmentRequest:
    """A ``ShipmentRequest`` from plain dict fields, which its attrs converters accept."""
    return models.ShipmentRequest(**fields)


def address_validation_request(**fields: typing.Any) -> models.AddressValidationRequest:
    """An ``AddressValidationRequest`` from plain dict fields, which its attrs converters accept."""
    return models.AddressValidationRequest(**fields)


def http_error(status: int, body: str = "") -> typing.Callable[..., typing.Any]:
    """A mocked ``lib.request`` answer that fails with ``status`` and ``body``.

    The answer hands a real ``HTTPError`` to the request's ``on_error``
    decoder, so ``lib.error_decoder`` enriches a JSON body with the HTTP
    metadata and raises on a body that is not JSON, as it does live.
    """

    def respond(**kwargs: typing.Any) -> typing.Any:
        return kwargs["on_error"](
            urllib.error.HTTPError(
                kwargs["url"],
                status,
                http.HTTPStatus(status).phrase,
                email.message.Message(),
                io.BytesIO(body.encode()),
            )
        )

    return respond


def answers(*responses: typing.Any) -> typing.Callable[..., typing.Any]:
    """A ``lib.request`` side effect answering calls in order.

    An exception is raised, an ``http_error`` answer is run against the
    call's arguments, and any other value is returned as the body.
    """
    pending = list(responses)

    def side_effect(**kwargs: typing.Any) -> typing.Any:
        response = pending.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response(**kwargs) if callable(response) else response

    return side_effect
