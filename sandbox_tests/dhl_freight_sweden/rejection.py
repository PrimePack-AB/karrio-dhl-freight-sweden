"""Expected DHL-side rejections: payload mutations and the rejection attempt.

The connector never sends these payloads: it refuses most of them locally
and adds a default SENT entry to PL lanes. Each case therefore builds a valid request through the connector and mutates its serialized
TransportInstruction with ``harness.mutated_request`` just before the call.
"""

import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.dhl_freight_sweden.units as provider_units
from . import booking, harness

SENT_CODES = frozenset(
    code.value
    for code in (
        provider_units.AdditionalInformationCode.SENT_FREE,
        provider_units.AdditionalInformationCode.SENT_REF,
        provider_units.AdditionalInformationCode.SENT_CARKEY,
    )
)


def without_sent(instruction: dict) -> dict:
    """``instruction`` without its SENT additionalInformation entries."""
    remaining = [
        entry
        for entry in instruction.get("additionalInformation") or []
        if entry.get("code") not in SENT_CODES
    ]
    rest = {
        key: value
        for key, value in instruction.items()
        if key != "additionalInformation"
    }
    return {**rest, **({"additionalInformation": remaining} if remaining else {})}


def with_party(party: dict) -> typing.Callable[[dict], dict]:
    """A mutation appending ``party`` to the instruction's parties."""
    return lambda instruction: {
        **instruction,
        "parties": [*(instruction.get("parties") or []), party],
    }


def with_payer_code(code: str) -> typing.Callable[[dict], dict]:
    """A mutation replacing the instruction's payer code with ``code``."""
    return lambda instruction: {**instruction, "payerCode": {"code": code}}


def access_point_id_only(instruction: dict) -> dict:
    """``instruction`` with its AccessPoint parties reduced to id, type, and sub type."""
    return {
        **instruction,
        "parties": [
            {key: party[key] for key in ("id", "type", "subType") if key in party}
            if party.get("type") == provider_units.PartyType.AccessPoint.value
            else party
            for party in instruction.get("parties") or []
        ],
    }


def access_point_party(point: dict) -> dict:
    """The AccessPoint party the connector builds for a service point lookup result."""
    address = point["address"]
    return {
        "id": point["service_point_id"],
        "type": provider_units.PartyType.AccessPoint.value,
        "subType": booking.sub_type(point),
        "name": point.get("name"),
        "address": {
            "street": address["street"],
            "cityName": address["city"],
            "postalCode": str(address["postal_code"]),
            "countryCode": address["country_code"],
        },
    }


def reject(
    test: unittest.TestCase,
    session: harness.Session,
    gateway,
    label: str,
    product: str,
    payload: dict,
    mutate: typing.Callable[[dict], dict],
    expected_code: str,
) -> typing.List[models.Message]:
    """Send ``payload`` mutated by ``mutate`` once and assert DHL's ``expected_code``.

    The attempt counts against the booking budget and is logged to
    ``bookings.jsonl``. A shipment id in the response means DHL accepted
    the payload; the test then fails and reports the id as a finding.
    """
    booking.require_booking(
        test, session, product, str(payload["recipient"]["country_code"]).upper()
    )
    request = gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
    mutated = harness.mutated_request(request, mutate)
    if not session.budget.reserve():
        test.skipTest("booking budget exhausted")

    shipment: typing.Optional[models.ShipmentDetails] = None
    messages: typing.List[models.Message] = []
    try:
        shipment, messages = gateway.mapper.parse_shipment_response(
            gateway.proxy.create_shipment(mutated)
        )
    finally:
        session.log_booking(
            product, shipment.tracking_number if shipment else None, test.id()
        )
        session.capture(gateway, label)
        session.capture_parsed(
            label,
            dict(
                tracking_number=shipment.tracking_number if shipment else None,
                messages=lib.to_dict(messages),
            ),
        )

    if shipment is not None:
        test.fail(
            f"finding: DHL accepted the {label} payload expected to fail with "
            f"{expected_code}; shipment id {shipment.tracking_number}"
        )
    codes = [str(message.code) for message in messages]
    test.assertIn(
        expected_code,
        codes,
        f"DHL rejected {label} with {lib.to_dict(messages)}",
    )
    return messages
