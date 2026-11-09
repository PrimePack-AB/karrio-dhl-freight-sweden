"""DHL Freight (SE API Farm) shipper phone number policy.

The ``phone_number_policy`` connection setting and the
``dhl_freight_sweden_phone_number_policy`` shipment option take ``always``
(the default) or ``omit_when_email_suffices``; the shipment option
overrides the setting. Under ``omit_when_email_suffices`` a booking omits
the Consignor party's phone when the shipper has an e-mail address, except
for the products whose sender phone is mandatory (402 and 502, manual
v5.26 §5.18 p76). The Consignee phone and pickups are never changed.
"""

import typing
import unittest

import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import OptionValueError

from .fixture import _gateway, as_list, detail_keys, gateway, serialize_request
from .test_pickup import PickupPayload
from .test_shipment import _payload, _recipient_se, _shipper

_OPTION = "dhl_freight_sweden_phone_number_policy"
_OMIT = "omit_when_email_suffices"

omit_gateway = _gateway({"phone_number_policy": _OMIT})
always_gateway = _gateway({"phone_number_policy": "always"})
unrecognized_gateway = _gateway({"phone_number_policy": "never"})

_HOME_DELIVERY_RETURNS = {
    "402": "dhl_freight_sweden_home_delivery_c2b",
    "502": "dhl_freight_sweden_home_delivery_c2b_502",
}


def _serialize(payload: dict, connection: typing.Any = gateway) -> dict:
    return serialize_request(
        connection.mapper.create_shipment_request(models.ShipmentRequest(**payload))
    )


def _domestic(options: typing.Optional[dict] = None, **parties: dict) -> dict:
    return {**_payload("dhl_freight_sweden_paket", _recipient_se, options), **parties}


def _party(serialized: dict, party_type: str) -> dict:
    return next(
        party for party in as_list(serialized["parties"]) if party["type"] == party_type
    )


class TestDHLFreightPhoneNumberPolicy(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_default_sends_the_shipper_phone(self):
        for connection in (gateway, always_gateway):
            with self.subTest(connection=connection):
                consignor = _party(_serialize(_domestic(), connection), "Consignor")

                self.assertEqual(consignor["phone"], _shipper["phone_number"])
                self.assertEqual(consignor["email"], _shipper["email"])

    def test_omit_drops_the_shipper_phone_an_email_covers(self):
        for serialized in (
            _serialize(_domestic(), omit_gateway),
            _serialize(_domestic({_OPTION: _OMIT})),
        ):
            consignor = _party(serialized, "Consignor")

            self.assertNotIn("phone", consignor)
            self.assertEqual(consignor["email"], _shipper["email"])

    def test_omit_keeps_the_shipper_phone_without_an_email(self):
        for email in (None, "", "   "):
            with self.subTest(email=email):
                serialized = _serialize(
                    _domestic(shipper={**_shipper, "email": email}), omit_gateway
                )

                self.assertEqual(
                    _party(serialized, "Consignor")["phone"], _shipper["phone_number"]
                )

    def test_omit_keeps_the_sender_phone_402_and_502_require(self):
        for code, service in _HOME_DELIVERY_RETURNS.items():
            with self.subTest(product=code):
                serialized = _serialize(
                    _payload(
                        service, _recipient_se, {"dhl_freight_sweden_payer_code": "3"}
                    ),
                    omit_gateway,
                )

                self.assertEqual(serialized["productCode"], code)
                self.assertEqual(
                    _party(serialized, "Consignor")["phone"], _shipper["phone_number"]
                )

    def test_omit_never_touches_the_consignee_phone(self):
        serialized = _serialize(_domestic(), omit_gateway)
        consignee = _party(serialized, "Consignee")

        self.assertEqual(
            (consignee["phone"], consignee["email"]),
            (_recipient_se["phone_number"], _recipient_se["email"]),
        )

    def test_shipment_option_overrides_the_connection_setting(self):
        cases = [
            (gateway, _OMIT, False),
            (omit_gateway, "always", True),
            (omit_gateway, " Always ", True),
            (gateway, "OMIT_WHEN_EMAIL_SUFFICES", False),
            (omit_gateway, None, False),
            (omit_gateway, "  ", False),
        ]

        for connection, value, phone_sent in cases:
            with self.subTest(value=value, connection=connection):
                consignor = _party(
                    _serialize(_domestic({_OPTION: value}), connection), "Consignor"
                )

                self.assertEqual("phone" in consignor, phone_sent)

    def test_unrecognized_connection_setting_sends_the_phone(self):
        consignor = _party(_serialize(_domestic(), unrecognized_gateway), "Consignor")

        self.assertEqual(consignor["phone"], _shipper["phone_number"])

    def test_invalid_shipment_option_is_refused(self):
        for value in ["never", "omit", True, 1, []]:
            with self.subTest(value=value):
                with self.assertRaises(OptionValueError) as context:
                    _serialize(_domestic({_OPTION: value}))

                self.assertEqual(detail_keys(context.exception), {_OPTION})
                self.assertEqual(
                    (context.exception.details or {})[_OPTION],
                    dict(
                        code="invalid",
                        message=f"expected always or omit_when_email_suffices, got {value!r}",
                    ),
                )
                self.assertEqual(
                    str(context.exception),
                    f"Options {_OPTION} must be always or omit_when_email_suffices",
                )

    def test_policy_is_not_sent_to_dhl(self):
        body = str(_serialize(_domestic({_OPTION: _OMIT})))

        self.assertNotIn("policy", body)
        self.assertNotIn(_OMIT, body)

    def test_pickup_keeps_the_phone_under_the_connection_setting(self):
        request = omit_gateway.mapper.create_pickup_request(
            models.PickupRequest(**PickupPayload)
        )
        serialized = serialize_request(request)

        for party in as_list(serialized["parties"]):
            with self.subTest(party=party["type"]):
                self.assertEqual(party["phone"], PickupPayload["address"]["phone_number"])


if __name__ == "__main__":
    unittest.main()
