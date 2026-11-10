"""DHL Freight (SE API Farm) shipper phone number policy.

The ``phone_number_policy`` connection setting and the
``dhl_freight_sweden_phone_number_policy`` shipment option take ``always``
(the default), ``omit_when_email_suffices``, or ``omit_unless_required``;
the shipment option overrides the setting. Under ``omit_when_email_suffices``
a booking omits the Consignor party's phone when the shipper has an e-mail
address, except for the products whose sender phone is mandatory (402 and
502, manual v5.26 §5.18 p76), and never changes the Consignee phone.
Under ``omit_unless_required`` a booking omits the Consignor phone except
for 402 and 502, and the Consignee phone except where the manual requires
it: 118, 401, and 601 (§5.16 p68, §5.17 p72, §5.19 p81), 103 without a
recipient e-mail (§5.12 p56), 109 and 112 to SK (§9.4.2 p170), and the
notification and pre-advice services (§6.38 p134, §6.46 p144).
Pickups are never changed.
"""

import typing
import unittest

import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import OptionValueError

from .fixture import _gateway, as_list, detail_keys, gateway, serialize_request
from .test_pickup import PickupPayload
from .test_shipment import (
    ShipmentPayload103,
    ShipmentPayload109,
    _payload,
    _recipient_dk,
    _recipient_se,
    _shipper,
)

_OPTION = "dhl_freight_sweden_phone_number_policy"
_OMIT = "omit_when_email_suffices"
_REQUIRED = "omit_unless_required"

omit_gateway = _gateway({"phone_number_policy": _OMIT})
always_gateway = _gateway({"phone_number_policy": "always"})
unrecognized_gateway = _gateway({"phone_number_policy": "never"})
required_gateway = _gateway({"phone_number_policy": _REQUIRED})

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
                        message=(
                            "expected always, omit_when_email_suffices, "
                            f"or omit_unless_required, got {value!r}"
                        ),
                    ),
                )
                self.assertEqual(
                    str(context.exception),
                    f"Options {_OPTION} must be always, omit_when_email_suffices, or omit_unless_required",
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


_recipient_sk = {
    **_recipient_se,
    "city": "Bratislava",
    "postal_code": "81106",
    "country_code": "SK",
}

_service_point_sk = {
    "dhl_freight_sweden_service_point": "123456",
    "dhl_freight_sweden_service_point_type": "ParcelShop",
    "dhl_freight_sweden_service_point_name": "Test Shop",
    "dhl_freight_sweden_service_point_street": "Obchodna 1",
    "dhl_freight_sweden_service_point_city": "Bratislava",
    "dhl_freight_sweden_service_point_postal_code": "81106",
    "dhl_freight_sweden_service_point_country_code": "SK",
}


def _consignee_phone(payload: dict, connection: typing.Any = required_gateway):
    return _party(_serialize(payload, connection), "Consignee").get("phone")


class TestDHLFreightPhoneNumberPolicyOmitUnlessRequired(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_omits_the_shipper_phone_with_or_without_an_email(self):
        for email in (_shipper["email"], None, "", "   "):
            with self.subTest(email=email):
                serialized = _serialize(
                    _domestic(shipper={**_shipper, "email": email}), required_gateway
                )

                self.assertNotIn("phone", _party(serialized, "Consignor"))

    def test_shipment_option_selects_it(self):
        for connection in (gateway, omit_gateway, always_gateway):
            with self.subTest(connection=connection):
                serialized = _serialize(
                    _domestic({_OPTION: " OMIT_UNLESS_REQUIRED "}), connection
                )

                self.assertNotIn("phone", _party(serialized, "Consignor"))
                self.assertNotIn("phone", _party(serialized, "Consignee"))

    def test_keeps_the_sender_phone_402_and_502_require(self):
        for code, service in _HOME_DELIVERY_RETURNS.items():
            with self.subTest(product=code):
                serialized = _serialize(
                    _payload(
                        service, _recipient_se, {"dhl_freight_sweden_payer_code": "3"}
                    ),
                    required_gateway,
                )

                self.assertEqual(serialized["productCode"], code)
                self.assertEqual(
                    _party(serialized, "Consignor")["phone"], _shipper["phone_number"]
                )
                self.assertNotIn("phone", _party(serialized, "Consignee"))

    def test_omits_the_recipient_phone_no_rule_requires(self):
        cases = {
            "102": _domestic(),
            "102 without e-mail": _domestic(recipient={**_recipient_se, "email": None}),
            "103 with e-mail": ShipmentPayload103,
            "109 to DK": ShipmentPayload109,
            "112 to DK": _payload("dhl_freight_sweden_parcel_connect_plus", _recipient_dk),
            "102 with services false": _domestic(
                {
                    "dhl_freight_sweden_notification": False,
                    "dhl_freight_sweden_pre_advice": False,
                }
            ),
        }

        for case, payload in cases.items():
            with self.subTest(case=case):
                self.assertIsNone(_consignee_phone(payload))

    def test_keeps_the_recipient_phone_the_product_requires(self):
        cases = {
            "118": _payload("dhl_freight_sweden_hemleverans_paket_b2c", _recipient_se),
            "401": _payload("dhl_freight_sweden_home_delivery_b2c", _recipient_se),
            "601": _payload(
                "dhl_freight_sweden_home_delivery_international_b2c",
                _recipient_dk,
                {"dhl_freight_sweden_payer_code": "DAP"},
            ),
        }

        for code, payload in cases.items():
            with self.subTest(product=code):
                self.assertEqual(_consignee_phone(payload), _recipient_se["phone_number"])

    def test_keeps_the_103_recipient_phone_without_an_email(self):
        for email in (None, "", "   "):
            with self.subTest(email=email):
                payload = {
                    **ShipmentPayload103,
                    "recipient": {**_recipient_se, "email": email},
                }

                self.assertEqual(
                    _consignee_phone(payload), _recipient_se["phone_number"]
                )

    def test_keeps_the_recipient_phone_on_109_and_112_to_sk(self):
        cases = {
            "109": _payload(
                "dhl_freight_sweden_parcel_connect_b2c", _recipient_sk, _service_point_sk
            ),
            "112": _payload("dhl_freight_sweden_parcel_connect_plus", _recipient_sk),
        }

        for code, payload in cases.items():
            with self.subTest(product=code):
                self.assertEqual(_consignee_phone(payload), _recipient_sk["phone_number"])

    def test_keeps_the_recipient_phone_for_notification_and_pre_advice(self):
        for option in (
            "dhl_freight_sweden_notification",
            "email_notification",
            "sms_notification",
            "dhl_freight_sweden_pre_advice",
        ):
            with self.subTest(option=option):
                self.assertEqual(
                    _consignee_phone(_domestic({option: True})),
                    _recipient_se["phone_number"],
                )

    def test_existing_values_never_omit_the_recipient_phone(self):
        for connection in (gateway, always_gateway, omit_gateway):
            with self.subTest(connection=connection):
                self.assertEqual(
                    _consignee_phone(ShipmentPayload109, connection),
                    _recipient_se["phone_number"],
                )

    def test_pickup_keeps_the_phone(self):
        serialized = serialize_request(
            required_gateway.mapper.create_pickup_request(
                models.PickupRequest(**PickupPayload)
            )
        )

        for party in as_list(serialized["parties"]):
            with self.subTest(party=party["type"]):
                self.assertEqual(party["phone"], PickupPayload["address"]["phone_number"])


if __name__ == "__main__":
    unittest.main()
