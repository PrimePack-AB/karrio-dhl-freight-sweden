"""Sandbox segment ``pickup-probes``: hand-built PickupRequest API calls,
the evidence behind the request shape of the connector's ``schedule_pickup``.

The PickupRequest API (vendor/se-api-farm/pickup-request-api-2.10.0.json)
books a pickup for one or several shipments of 102, 112, 209, 210, 211, 212,
103, 109, 118, and 401 (product manual v5.26 §10.14.12 p236), and a booking
cannot be cancelled electronically (§5.2 p14). The 102 probe sends the
transport instruction shape of the committed 102 SE booking
(tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761222-102-se-se.json)
with the parties the manual lists for 102 (§5.2 p15: CZ, CN, and PW, the
pickup address), payer code 1, a pickup date, and a pickup instruction.
Each test sends one distinct request: the base 102 probe and variants that
place the customer number in other parties. Every call counts against the
booking budget and is captured and recorded once, whatever DHL answers, and
never retried.
"""

import datetime
import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio
import karrio.providers.dhl_freight_sweden.units as provider_units
from . import booking, harness

PICKUP_URL = "/pickuprequestapi/v1/pickuprequest/pickuprequest"
# The next Swedish business day after the probe was written (Monday
# 2026-10-19). The spec types pickupDate as date-time; the 10:00 time of day
# differs from midnight so the response's pickupDateTime shows whether DHL
# keeps the requested time.
PICKUP_DATE = datetime.datetime(2026, 10, 20, 10, 0, 0)
PICKUP_INSTRUCTION = "Sandbox test, no pickup needed"


def party(
    type: provider_units.PartyType, address: dict, id: typing.Optional[str] = None
) -> dict:
    """A PickupRequest party in the transport instruction party shape."""
    return typing.cast(
        dict,
        lib.to_dict(
            dict(
                id=id,
                type=type.value,
                name=address.get("company_name") or address["person_name"],
                contactName=address["person_name"],
                address=dict(
                    street=address["address_line1"],
                    cityName=address["city"],
                    postalCode=address["postal_code"],
                    countryCode=address["country_code"],
                ),
                phone=address.get("phone_number"),
                email=address.get("email"),
            )
        ),
    )


def pickup_request_102(account_number: str) -> dict:
    """The 102 SE pickup request: one 1 kg parcel picked up at the shipper."""
    parcel = booking.PARCEL
    return dict(
        productCode="102",
        pickupDate=PICKUP_DATE.isoformat(),
        pickupInstruction=PICKUP_INSTRUCTION,
        totalNumberOfPieces=1,
        totalWeight=parcel["weight"],
        totalVolume=0.006,
        payerCode=dict(code="1"),
        parties=[
            party(provider_units.PartyType.Consignor, booking.SHIPPER, account_number),
            party(provider_units.PartyType.Consignee, booking.RECIPIENTS["SE"]),
            party(provider_units.PartyType.Pickup, booking.SHIPPER),
        ],
        pieces=[
            dict(
                marksAndNumbers=parcel["reference_number"],
                numberOfPieces=1,
                weight=parcel["weight"],
                volume=0.006,
                length=parcel["length"],
                width=parcel["width"],
                height=parcel["height"],
            )
        ],
    )


def with_party(request: dict, extra: dict) -> dict:
    """The request with one more party appended."""
    return {**request, "parties": [*request["parties"], extra]}


class TestSandboxPickupProbes(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment("pickup-probes")
        cls.gateway = cls.session.gateway()

    def test_pickup_request_102_se(self):
        self._request_pickup("pickup-102-se", pickup_request_102)

    def test_pickup_request_102_se_freight_payer(self):
        """Variant: a FreightPayer party carries the customer number too.

        The manual's 102 party table lists FP, freight payer (§5.2 p15), and
        for 212 a pickup request needs the freight payer party with the paying
        DHL account number (§5.8 p38).
        """
        self._request_pickup(
            "pickup-102-se-freight-payer",
            lambda account: with_party(
                pickup_request_102(account),
                party(provider_units.PartyType.FreightPayer, booking.SHIPPER, account),
            ),
        )

    def test_pickup_request_102_se_pickup_party_id(self):
        """Variant: the customer number moves from the Consignor to the Pickup party."""

        def build(account: str) -> dict:
            request = pickup_request_102(account)
            parties = [
                {**p, "id": account} if p["type"] == provider_units.PartyType.Pickup.value
                else {k: v for k, v in p.items() if k != "id"}
                for p in request["parties"]
            ]
            return {**request, "parties": parties}

        self._request_pickup("pickup-102-se-pickup-party-id", build)

    def test_pickup_request_102_se_no_consignee(self):
        """Variant: the accepted Pickup party id request without a Consignee party.

        A karrio pickup request carries one address, the pickup address, so
        this shows whether DHL books a pickup with no Consignee.
        """

        def build(account: str) -> dict:
            request = pickup_request_102(account)
            parties = [
                {**p, "id": account} if p["type"] == provider_units.PartyType.Pickup.value
                else {k: v for k, v in p.items() if k != "id"}
                for p in request["parties"]
                if p["type"] != provider_units.PartyType.Consignee.value
            ]
            return {**request, "parties": parties}

        self._request_pickup("pickup-102-se-no-consignee", build)

    def test_pickup_request_102_se_consignor_and_pickup_party_id(self):
        """Variant: the accepted no-Consignee request with 999999 on the Consignor too.

        The Consignor id alone was answered as an unknown customer number and
        the Pickup party id alone was accepted, so this shows whether a
        Consignor id causes the rejection or the Pickup party id is required.
        """

        def build(account: str) -> dict:
            request = pickup_request_102(account)
            parties = [
                {**p, "id": account}
                for p in request["parties"]
                if p["type"] != provider_units.PartyType.Consignee.value
            ]
            return {**request, "parties": parties}

        self._request_pickup("pickup-102-se-consignor-and-pickup-party-id", build)

    def test_pickup_request_212_se_connector(self):
        """212 within SE through the connector's own pickup path, payer code 1.

        The manual makes a pickup request for 212 carry the complete pickup
        address, at least the delivery place's address, postal code, and city,
        and the freight payer party with the paying DHL account number
        (§5.8 p38); the connector sends the Consignor and the Pickup party at
        the karrio pickup address only.
        """
        booking.require_booking(self, self.session, "212", "SE")
        label = "pickup-212-se-connector"
        payload = models.PickupRequest(
            pickup_date=PICKUP_DATE.strftime("%Y-%m-%d"),
            ready_time=PICKUP_DATE.strftime("%H:%M"),
            closing_time="16:00",
            address=models.Address(**typing.cast(typing.Dict[str, typing.Any], booking.SHIPPER)),
            parcels=[models.Parcel(**booking.PARCEL)],
            instruction=PICKUP_INSTRUCTION,
            options=dict(
                dhl_freight_sweden_service="212",
                dhl_freight_sweden_payer_code="1",
            ),
        )
        if not self.session.budget.reserve():
            self.skipTest("booking budget exhausted")

        details: typing.Any = None
        messages: typing.List[models.Message] = []
        try:
            details, messages = (
                karrio.Pickup.schedule(payload).from_(self.gateway).parse()
            )
        finally:
            self.session.log_booking(
                "212",
                details.confirmation_number if details else None,
                self.id(),
            )
            self.session.capture(self.gateway, label)
            self.session.capture_parsed(
                label,
                dict(
                    details=lib.to_dict(details),
                    messages=lib.to_dict(messages),
                ),
            )

        self.assertTrue(details and details.confirmation_number, messages)

    def _request_pickup(
        self, label: str, build: typing.Callable[[str], dict]
    ) -> None:
        booking.require_booking(self, self.session, "102", "SE")
        settings = harness.settings_of(self.gateway)
        payload = build(str(settings.account_number))
        if not self.session.budget.reserve():
            self.skipTest("booking budget exhausted")

        response: typing.Any = None
        try:
            response = lib.request(
                url=f"{settings.server_url}{PICKUP_URL}",
                data=lib.to_json(payload),
                trace=self.gateway.proxy.trace_as("json"),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "client-key": settings.client_key,
                },
                on_error=lib.error_decoder,
            )
        finally:
            body = harness.decoded_body(response)
            self.session.log_booking(
                "102",
                body.get("bookingNumber") if isinstance(body, dict) else None,
                self.id(),
            )
            self.session.capture(self.gateway, label)
            self.session.capture_parsed(label, dict(response=body))

        body = harness.decoded_body(response)
        self.assertIsInstance(body, dict)
        # ResponseStatus is an integer enum whose first name is Accepted.
        self.assertIn(body.get("status"), (0, "Accepted"), body)
        self.assertTrue(body.get("bookingNumber"), body)
