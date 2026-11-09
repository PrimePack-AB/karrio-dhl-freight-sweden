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
from .test_shipment import _payload, _recipient_se, _shipper

_OPTION = "dhl_freight_sweden_phone_number_policy"
_OMIT = "omit_when_email_suffices"

always_gateway = _gateway({"phone_number_policy": "always"})
unrecognized_gateway = _gateway({"phone_number_policy": "never"})


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


if __name__ == "__main__":
    unittest.main()
