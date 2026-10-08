"""DHL Freight (SE API Farm) strict reading of bool-typed shipping options.

The SDK reads a bool option as ``value is not False``, so "false", "0", 0,
None, and "" all select it. Karrio server and dashboard payloads can carry
string values, so the connector reads its flag options strictly: true, "1",
1, and "yes" select; false, "0", 0, and "no" deselect; None and "" leave the
option unset; anything else is refused before any request is built.
"""

import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.providers.dhl_freight_sweden.units as provider_units
import karrio.sdk as karrio
from karrio.providers.dhl_freight_sweden.shipment.create import (
    OptionValueError,
    SentInformationError,
)

from .fixture import detail_keys, gateway, serialize_request
from .test_customs_service_combination import SERVICES, _to_no
from .test_sent import SentFree, SentIdentified, _recipient_pl
from .test_sent import _parcel_connect as _parcel_connect_pl
from .test_shipment import CustomsServiceKeys, _payload, _recipient_se
from .test_transport_declarations import _recipient_hu, _recipient_ro, _road_freight

FLAG_OPTIONS = {
    "dhl_freight_sweden_notification",
    "dhl_freight_sweden_pre_advice",
    "dhl_freight_sweden_tail_lift_unloading",
    "dhl_freight_sweden_customs_handling_standard",
    "dhl_freight_sweden_customs_handling_full_service",
    "dhl_freight_sweden_customs_own_declaration",
    "dhl_freight_sweden_customs_joint_declaration",
    "dhl_freight_sweden_qr_code",
    "dhl_freight_sweden_sent_free",
    "dhl_freight_sweden_ekaer_free",
    "dhl_freight_sweden_uit_free",
}
TRUE_SPELLINGS = [True, "true", "TRUE", " True ", "1", 1, "yes", "Yes"]
FALSE_SPELLINGS = [False, "false", "FALSE", " False ", "0", 0, "no", "No"]
UNSET_SPELLINGS = [None, "", "  "]
INVALID_VALUES = ["maybe", 1.0, 0.0, 2, "2", "on", [], {}]

ADDITIONAL_SERVICE_FLAGS = {
    "dhl_freight_sweden_notification": "notification",
    "dhl_freight_sweden_pre_advice": "preAdvice",
    "dhl_freight_sweden_tail_lift_unloading": "tailLiftUnloading",
}


def _request(payload: dict):
    return gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))


def _domestic(options: dict) -> dict:
    return _payload("dhl_freight_sweden_paket", _recipient_se, options)


class TestDHLFreightFlagOptionsAudit(unittest.TestCase):
    def test_flag_options_are_every_bool_typed_option(self):
        self.assertEqual(
            {
                member.name
                for member in provider_units.ShippingOption
                if member.value.type is bool
            },
            FLAG_OPTIONS,
        )


class TestDHLFreightFlagParsing(unittest.TestCase):
    def test_initializer_reads_flags_strictly(self):
        for value, expected in [
            *((value, True) for value in TRUE_SPELLINGS),
            *((value, False) for value in FALSE_SPELLINGS),
            *((value, None) for value in UNSET_SPELLINGS),
        ]:
            with self.subTest(value=value):
                options = provider_units.shipping_options_initializer(
                    {option: value for option in FLAG_OPTIONS}
                )

                self.assertEqual(
                    {option: options[option].state for option in FLAG_OPTIONS},
                    {option: expected for option in FLAG_OPTIONS},
                )

    def test_unset_flags_are_not_in_options(self):
        options = provider_units.shipping_options_initializer(
            {option: None for option in FLAG_OPTIONS}
        )

        self.assertFalse(any(option in options for option in FLAG_OPTIONS))

    def test_unified_alias_is_read_strictly(self):
        options = provider_units.shipping_options_initializer(
            {"email_notification": "false"}
        )

        self.assertIs(options.dhl_freight_sweden_notification.state, False)

    def test_initializer_never_raises_and_drops_invalid_flags(self):
        for value in INVALID_VALUES:
            with self.subTest(value=value):
                options = provider_units.shipping_options_initializer(
                    {option: value for option in FLAG_OPTIONS}
                )

                self.assertFalse(any(option in options for option in FLAG_OPTIONS))

    def test_invalid_flags_names_each_invalid_option(self):
        self.assertEqual(
            provider_units.invalid_flags(
                {
                    "dhl_freight_sweden_qr_code": "maybe",
                    "email_notification": 1.0,
                    "dhl_freight_sweden_sent_free": "false",
                    "dhl_freight_sweden_pre_advice": None,
                    "dhl_freight_sweden_payer_code": "maybe",
                }
            ),
            {"dhl_freight_sweden_qr_code": "maybe", "email_notification": 1.0},
        )

    def test_non_flag_options_are_untouched(self):
        options = provider_units.shipping_options_initializer(
            {"dhl_freight_sweden_payer_code": "DAP", "dhl_freight_sweden_insurance": "100"}
        )

        self.assertEqual(options.dhl_freight_sweden_payer_code.state, "DAP")
        self.assertEqual(options.dhl_freight_sweden_insurance.state, 100.0)


class TestDHLFreightInvalidFlagRefusal(unittest.TestCase):
    def test_invalid_flag_values_are_refused(self):
        for value in ["maybe", 1.0]:
            for option in sorted(FLAG_OPTIONS):
                with self.subTest(option=option, value=value):
                    with self.assertRaises(OptionValueError) as context:
                        _request(_domestic({option: value}))

                    self.assertEqual(detail_keys(context.exception), {option})
                    self.assertIn(option, str(context.exception))

    def test_refusal_names_every_invalid_option(self):
        with self.assertRaises(OptionValueError) as context:
            _request(
                _domestic(
                    {
                        "dhl_freight_sweden_notification": "maybe",
                        "dhl_freight_sweden_qr_code": 1.0,
                        "dhl_freight_sweden_pre_advice": "true",
                    }
                )
            )

        self.assertEqual(
            detail_keys(context.exception),
            {"dhl_freight_sweden_notification", "dhl_freight_sweden_qr_code"},
        )

    def test_refusal_precedes_option_checks(self):
        with self.assertRaises(OptionValueError):
            _request(
                _to_no(
                    {
                        "dhl_freight_sweden_customs_handling_standard": True,
                        "dhl_freight_sweden_customs_handling_full_service": True,
                        "dhl_freight_sweden_qr_code": "maybe",
                    }
                )
            )

    def test_refusal_sends_no_request(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            details, messages = (
                karrio.Shipment.create(
                    models.ShipmentRequest(
                        **_domestic({"dhl_freight_sweden_notification": "maybe"})
                    )
                )
                .from_(gateway)
                .parse()
            )

        mock.assert_not_called()
        self.assertIsNone(details)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].code, "SHIPPING_SDK_FIELD_ERROR")
        self.assertEqual(set(messages[0].details), {"dhl_freight_sweden_notification"})


class TestDHLFreightCustomsServiceFlags(unittest.TestCase):
    def test_false_spelled_customs_services_are_not_sent(self):
        for option in SERVICES:
            for value in [*FALSE_SPELLINGS, *UNSET_SPELLINGS]:
                with self.subTest(option=option, value=value):
                    serialized = serialize_request(
                        _request(_to_no({option: value, **SERVICES[option][1]}))
                    )

                    self.assertFalse(
                        set(serialized.get("additionalServices") or {})
                        & CustomsServiceKeys
                    )

    def test_false_spelled_customs_services_are_not_counted(self):
        for option, (field, extra) in SERVICES.items():
            for value in [*FALSE_SPELLINGS, *UNSET_SPELLINGS]:
                with self.subTest(option=option, value=value):
                    others = {
                        key: item
                        for other, (_, other_extra) in SERVICES.items()
                        if other != option
                        for key, item in {other: value, **other_extra}.items()
                    }
                    serialized = serialize_request(
                        _request(_to_no({**others, option: "true", **extra}))
                    )

                    self.assertEqual(
                        set(serialized["additionalServices"]) & CustomsServiceKeys,
                        {field},
                    )

    def test_true_spelled_customs_services_are_sent(self):
        for option, (field, extra) in SERVICES.items():
            for value in TRUE_SPELLINGS:
                with self.subTest(option=option, value=value):
                    serialized = serialize_request(
                        _request(_to_no({option: value, **extra}))
                    )

                    self.assertEqual(
                        set(serialized["additionalServices"]) & CustomsServiceKeys,
                        {field},
                    )


class TestDHLFreightAdditionalServiceFlags(unittest.TestCase):
    def test_unset_additional_services_are_omitted(self):
        for value in UNSET_SPELLINGS:
            with self.subTest(value=value):
                serialized = serialize_request(
                    _request(_domestic({option: value for option in ADDITIONAL_SERVICE_FLAGS}))
                )

                self.assertFalse(
                    set(serialized.get("additionalServices") or {})
                    & set(ADDITIONAL_SERVICE_FLAGS.values())
                )

    def test_false_spelled_additional_services_are_sent_false(self):
        for value in FALSE_SPELLINGS:
            with self.subTest(value=value):
                serialized = serialize_request(
                    _request(_domestic({option: value for option in ADDITIONAL_SERVICE_FLAGS}))
                )

                self.assertEqual(
                    {
                        field: serialized["additionalServices"].get(field)
                        for field in ADDITIONAL_SERVICE_FLAGS.values()
                    },
                    {field: False for field in ADDITIONAL_SERVICE_FLAGS.values()},
                )

    def test_false_spelled_qr_code_is_not_requested(self):
        for value in [*FALSE_SPELLINGS, *UNSET_SPELLINGS]:
            with self.subTest(value=value):
                request = _request(_domestic({"dhl_freight_sweden_qr_code": value}))

                self.assertNotIn("qrCode", request.ctx["print_options"])


class TestDHLFreightDeclarationFlags(unittest.TestCase):
    def _serialize(self, payload: dict) -> dict:
        return serialize_request(_request(payload))

    def test_sent_free_false_spellings_send_identifiers(self):
        for value in FALSE_SPELLINGS:
            with self.subTest(value=value):
                serialized = self._serialize(
                    _parcel_connect_pl(
                        _recipient_pl,
                        {
                            "dhl_freight_sweden_sent_free": value,
                            "dhl_freight_sweden_sent_ref": "123456789A",
                            "dhl_freight_sweden_sent_carkey": "82727166666",
                        },
                    )
                )

                self.assertEqual(serialized["additionalInformation"], SentIdentified)

    def test_sent_free_false_spellings_require_identifiers(self):
        with self.assertRaises(SentInformationError) as context:
            _request(_parcel_connect_pl(_recipient_pl, {"dhl_freight_sweden_sent_free": "false"}))

        self.assertEqual(
            detail_keys(context.exception),
            {"dhl_freight_sweden_sent_ref", "dhl_freight_sweden_sent_carkey"},
        )

    def test_sent_free_true_spellings_send_sent_free(self):
        for value in TRUE_SPELLINGS:
            with self.subTest(value=value):
                serialized = self._serialize(
                    _parcel_connect_pl(_recipient_pl, {"dhl_freight_sweden_sent_free": value})
                )

                self.assertEqual(serialized["additionalInformation"], [SentFree])

    def test_sent_free_unset_sends_sent_free(self):
        for value in UNSET_SPELLINGS:
            with self.subTest(value=value):
                serialized = self._serialize(
                    _parcel_connect_pl(_recipient_pl, {"dhl_freight_sweden_sent_free": value})
                )

                self.assertEqual(
                    serialized["additionalInformation"],
                    [{"code": "SENT_FREE", "stringValue": "true"}],
                )

    def test_ekaer_free_false_spellings_send_number(self):
        for value in FALSE_SPELLINGS:
            with self.subTest(value=value):
                serialized = self._serialize(
                    _road_freight(
                        _recipient_hu,
                        {
                            "dhl_freight_sweden_ekaer_free": value,
                            "dhl_freight_sweden_ekaer_number": "E2026100500001",
                        },
                    )
                )

                self.assertEqual(
                    serialized["additionalInformation"],
                    [
                        {"code": "EKAER_FREE", "stringValue": "false"},
                        {"code": "EKAER_NUMBER", "stringValue": "E2026100500001"},
                    ],
                )

    def test_ekaer_free_unset_sends_ekaer_free(self):
        for value in UNSET_SPELLINGS:
            with self.subTest(value=value):
                serialized = self._serialize(
                    _road_freight(_recipient_hu, {"dhl_freight_sweden_ekaer_free": value})
                )

                self.assertEqual(
                    serialized["additionalInformation"],
                    [{"code": "EKAER_FREE", "stringValue": "true"}],
                )

    def test_uit_free_false_spellings_send_uit_free_false(self):
        for value in FALSE_SPELLINGS:
            with self.subTest(value=value):
                serialized = self._serialize(
                    _road_freight(_recipient_ro, {"dhl_freight_sweden_uit_free": value})
                )

                self.assertEqual(
                    serialized["additionalInformation"],
                    [{"code": "UIT_FREE", "stringValue": "false"}],
                )

    def test_uit_free_unset_sends_uit_free(self):
        for value in UNSET_SPELLINGS:
            with self.subTest(value=value):
                serialized = self._serialize(
                    _road_freight(_recipient_ro, {"dhl_freight_sweden_uit_free": value})
                )

                self.assertEqual(
                    serialized["additionalInformation"],
                    [{"code": "UIT_FREE", "stringValue": "true"}],
                )


if __name__ == "__main__":
    unittest.main()
