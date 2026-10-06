"""DHL Freight (SE API Farm) customs services that cannot be combined.

Product manual v5.26 lists each of the four customs services under "Can not
be combined with" on the other three (§6.5 p92, §6.6 p94, §6.7 p96, §6.8 p98).
Outside the EU VAT area the connector refuses more than one selected customs
service before it sends any request; within it, customs services are dropped.
"""

import itertools
import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio
from karrio.providers.dhl_freight_sweden.shipment.create import (
    AlandCustomsServiceError,
    CustomsInformationRequiredError,
    CustomsServiceCombinationError,
    PayerCodeError,
)

from .fixture import as_dict, detail_keys, gateway, serialize_request
from .test_shipment import (
    BookingResponse102,
    Customs,
    CustomsServiceKeys,
    PrintResponse,
    ShipmentPayload109CustomsNO,
    ShipmentPayload202CustomsPL,
    _payload,
    _recipient_no,
    _recipient_se,
)

STANDARD = "dhl_freight_sweden_customs_handling_standard"
FULL_SERVICE = "dhl_freight_sweden_customs_handling_full_service"
OWN_DECLARATION = "dhl_freight_sweden_customs_own_declaration"
JOINT_DECLARATION = "dhl_freight_sweden_customs_joint_declaration"

SERVICES = {
    STANDARD: ("customsHandlingStandard", {}),
    FULL_SERVICE: ("customsHandlingFullService", {}),
    OWN_DECLARATION: (
        "customsCustomersOwnDeclaration",
        {"dhl_freight_sweden_customs_own_declaration_id": "26SE000000000000A1"},
    ),
    JOINT_DECLARATION: (
        "customsJointDeclaration",
        {"dhl_freight_sweden_customs_joint_declaration_id": "SFID-0001"},
    ),
}


def _selecting(*options: str) -> dict:
    return {
        key: value
        for option in options
        for key, value in {option: True, **SERVICES[option][1]}.items()
    }


def _to_no(options: dict) -> dict:
    return {**ShipmentPayload109CustomsNO, "options": options}


def _request(payload: dict):
    return gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))


class TestDHLFreightCustomsServiceCombination(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _refusal(self, payload: dict) -> CustomsServiceCombinationError:
        with self.assertRaises(CustomsServiceCombinationError) as context:
            _request(payload)
        return context.exception

    def test_every_pair_of_customs_services_is_refused(self):
        for pair in itertools.combinations(SERVICES, 2):
            with self.subTest(pair=pair):
                error = self._refusal(_to_no(_selecting(*pair)))

                self.assertEqual(detail_keys(error), set(pair))
                for option in pair:
                    self.assertIn(SERVICES[option][0], str(error))
                self.assertIn("§6.5 p92", str(error))
                self.assertIn("§6.8 p98", str(error))

    def test_all_four_customs_services_are_refused(self):
        error = self._refusal(_to_no(_selecting(*SERVICES)))

        self.assertEqual(detail_keys(error), set(SERVICES))

    def test_three_customs_services_are_refused(self):
        error = self._refusal(_to_no(_selecting(STANDARD, FULL_SERVICE, OWN_DECLARATION)))

        self.assertEqual(detail_keys(error), {STANDARD, FULL_SERVICE, OWN_DECLARATION})

    def test_single_customs_service_books(self):
        for option, (field, _) in SERVICES.items():
            with self.subTest(option=option):
                serialized = serialize_request(_request(_to_no(_selecting(option))))

                self.assertEqual(
                    set(serialized["additionalServices"]) & CustomsServiceKeys, {field}
                )

    def test_false_valued_customs_services_are_not_counted(self):
        for option, (field, _) in SERVICES.items():
            with self.subTest(option=option):
                others = {other: False for other in SERVICES if other != option}
                serialized = serialize_request(
                    _request(_to_no({**others, **_selecting(option)}))
                )

                self.assertEqual(
                    set(serialized["additionalServices"]) & CustomsServiceKeys, {field}
                )

    def test_refusal_sends_no_request(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            details, messages = (
                karrio.Shipment.create(
                    models.ShipmentRequest(**_to_no(_selecting(STANDARD, FULL_SERVICE)))
                )
                .from_(gateway)
                .parse()
            )

        mock.assert_not_called()
        self.assertIsNone(details)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].code, "SHIPPING_SDK_FIELD_ERROR")
        self.assertEqual(set(messages[0].details), {STANDARD, FULL_SERVICE})


class TestDHLFreightCustomsServiceCombinationOrdering(unittest.TestCase):
    def test_combination_precedes_missing_identifiers(self):
        error = self._combination_refusal(
            _to_no({OWN_DECLARATION: True, JOINT_DECLARATION: True})
        )

        self.assertEqual(detail_keys(error), {OWN_DECLARATION, JOINT_DECLARATION})

    def test_missing_customs_data_precedes_combination(self):
        payload = _payload(
            "dhl_freight_sweden_road_freight_standard",
            _recipient_no,
            {"dhl_freight_sweden_payer_code": "DAP", **_selecting(STANDARD, FULL_SERVICE)},
        )

        with self.assertRaises(CustomsInformationRequiredError):
            _request(payload)

    def test_aland_refusal_precedes_combination(self):
        recipient = {**_recipient_se, "city": "Mariehamn", "country_code": "FI", "postal_code": "22100"}
        payload = {
            **_payload(
                "dhl_freight_sweden_road_freight_direct",
                recipient,
                {"dhl_freight_sweden_payer_code": "DAP", **_selecting(STANDARD, FULL_SERVICE)},
            ),
            "customs": {**Customs, "options": {"eori_number": "SE0000000000"}},
        }

        with self.assertRaises(AlandCustomsServiceError):
            _request(payload)

    def test_payer_code_joint_declaration_rule_precedes_combination(self):
        payload = _to_no(
            {"dhl_freight_sweden_payer_code": "023", **_selecting(STANDARD, OWN_DECLARATION)}
        )

        with self.assertRaises(PayerCodeError) as context:
            _request(payload)

        self.assertEqual(detail_keys(context.exception), {JOINT_DECLARATION})

    def test_within_eu_vat_area_combined_services_are_dropped(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.side_effect = [BookingResponse102, PrintResponse]
            details, messages = (
                karrio.Shipment.create(
                    models.ShipmentRequest(
                        **{
                            **ShipmentPayload202CustomsPL,
                            "options": {
                                **ShipmentPayload202CustomsPL["options"],
                                **_selecting(*SERVICES),
                            },
                        }
                    )
                )
                .from_(gateway)
                .parse()
            )

        booking = as_dict(lib.to_dict(mock.call_args_list[0].kwargs["data"]))
        self.assertFalse(set(booking.get("additionalServices") or {}) & CustomsServiceKeys)
        self.assertIsNotNone(details)
        self.assertEqual([message.code for message in messages], ["customs_omitted_intra_eu"])

    def _combination_refusal(self, payload: dict) -> CustomsServiceCombinationError:
        with self.assertRaises(CustomsServiceCombinationError) as context:
            _request(payload)
        return context.exception


if __name__ == "__main__":
    unittest.main()
