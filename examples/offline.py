"""Offline gateway and request printer shared by the examples.

The gateway holds placeholder credentials and the examples only call the
mapper, which serialises a request without contacting DHL.
"""

import json
import typing

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio


def offline_gateway():
    """A test-mode gateway with placeholder credentials."""
    return karrio.gateway["dhl_freight_sweden"].create(
        dict(
            carrier_id="dhl_freight_sweden",
            client_key="YOUR_CLIENT_KEY",
            account_number="YOUR_ACCOUNT_NUMBER",
            test_mode=True,
        )
    )


def transport_instruction(request: models.ShipmentRequest) -> typing.Dict[str, typing.Any]:
    """The TransportInstruction body the connector would send for ``request``."""
    serializable = offline_gateway().mapper.create_shipment_request(request)
    return typing.cast(typing.Dict[str, typing.Any], lib.to_dict(serializable.serialize()))


def print_transport_instruction(request: models.ShipmentRequest) -> None:
    print(json.dumps(transport_instruction(request), indent=2, ensure_ascii=False))
