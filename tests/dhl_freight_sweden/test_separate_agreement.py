"""GB rejections of 109 and 112 explained as a separate-agreement lane.

Product manual v5.26 lists GB for 109 (§5.14 p63) and 112 (§5.3 p18) only
according to a separate agreement with DHL. The sandbox rejected both to GB
with 22005 and 22026 (fixtures/sandbox/rejection-22005-112-se-gb.json,
rejection-22005-109-se-gb.json); the parser keeps DHL's messages and adds a
note naming the agreement.
"""

import json
import pathlib
import typing
import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio
from karrio.providers.dhl_freight_sweden import units
from karrio.providers.dhl_freight_sweden.shipment import create

from .fixture import answers, gateway, http_error, settings_of, shipment_request

SANDBOX = pathlib.Path(__file__).parent / "fixtures" / "sandbox"
TI_PATH = "/transportinstructionapi/v1/transportinstruction/sendtransportinstruction"
GB_REJECTIONS = {
    "112": "rejection-22005-112-se-gb.json",
    "109": "rejection-22005-109-se-gb.json",
}


def booking_exchange(name: str) -> typing.Dict[str, typing.Any]:
    evidence = json.loads((SANDBOX / name).read_text())
    return next(
        exchange for exchange in evidence["exchanges"] if exchange["endpoint"].endswith(TI_PATH)
    )


def parse(request: dict, response: dict) -> typing.List[models.Message]:
    _, messages = create.parse_shipment_response(
        lib.Deserializable(
            [response, None],
            lib.identity,
            dict(separate_agreement=create.separate_agreement_lane(request)),
        ),
        settings_of(gateway),
    )
    return messages


def dhl_messages(response: dict) -> typing.List[typing.Tuple[str, str]]:
    return [(str(item["errorCode"]), item["message"]) for item in response["validationErrors"]]


def notes(messages: typing.List[models.Message]) -> typing.List[models.Message]:
    return [m for m in messages if m.code == units.SEPARATE_AGREEMENT_LANE]


LONDON_PAYLOAD: typing.Dict[str, typing.Any] = dict(
    service="dhl_freight_sweden_parcel_connect_b2c",
    shipper=dict(
        company_name="Test Shipper AB",
        person_name="Sven Svensson",
        address_line1="Kungsgatan 1",
        city="Stockholm",
        postal_code="11143",
        country_code="SE",
        phone_number="+46 8 123 456",
    ),
    recipient=dict(
        person_name="John Smith",
        address_line1="10 Rotherhithe New Road",
        city="London",
        postal_code="SE16 2BE",
        country_code="GB",
        phone_number="+44 7700 900123",
        email="john.smith@example.co.uk",
    ),
    parcels=[dict(weight=1.0, length=30.0, width=20.0, height=10.0, weight_unit="KG", dimension_unit="CM")],
    options=dict(
        dhl_freight_sweden_service_point="60753",
        dhl_freight_sweden_service_point_type="ParcelShop",
        dhl_freight_sweden_service_point_name="DHL Servicepoint",
        dhl_freight_sweden_service_point_street="173-181 Rotherhithe New Road",
        dhl_freight_sweden_service_point_city="London",
        dhl_freight_sweden_service_point_postal_code="SE16 2BE",
        dhl_freight_sweden_service_point_country_code="GB",
        dhl_freight_sweden_customs_handling_full_service=True,
    ),
    customs=dict(
        incoterm="DAP",
        invoice="SANDBOX-INV-1",
        content_type="merchandise",
        commercial_invoice=True,
        commodities=[
            dict(
                title="Cotton T-shirt",
                description="Cotton T-shirt",
                quantity=1,
                weight=0.5,
                weight_unit="KG",
                value_amount=200,
                value_currency="SEK",
                origin_country="SE",
                hs_code="610910",
            )
        ],
    ),
)


class TestSeparateAgreementNote(unittest.TestCase):
    def test_gb_rejections_keep_dhl_messages_and_add_the_note(self):
        for product, name in GB_REJECTIONS.items():
            with self.subTest(product=product):
                exchange = booking_exchange(name)
                messages = parse(exchange["request"], exchange["response"])

                self.assertEqual(
                    [(m.code, m.message) for m in messages if m.code != units.SEPARATE_AGREEMENT_LANE],
                    dhl_messages(exchange["response"]),
                )
                (note,) = notes(messages)
                self.assertIn(f"Product {product}", note.message)
                self.assertIn(units.PRODUCT_LANE_CITATIONS[product], note.message)
                self.assertIn("separate agreement", note.message)
                self.assertEqual(note.details, dict(product=product, country="GB"))
                self.assertEqual(note.level, "warning")

    def test_shipment_create_rejected_to_gb_carries_the_note(self):
        exchange = booking_exchange(GB_REJECTIONS["109"])
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.side_effect = answers(http_error(400, json.dumps(exchange["response"])))
            details, messages = (
                karrio.Shipment.create(shipment_request(**LONDON_PAYLOAD))
                .from_(gateway)
                .parse()
            )

        self.assertIsNone(details)
        self.assertEqual(
            [(m.code, m.message) for m in messages][:-1], dhl_messages(exchange["response"])
        )
        self.assertEqual(messages[-1].code, units.SEPARATE_AGREEMENT_LANE)

    def test_lane_from_territory_and_access_point(self):
        request = booking_exchange(GB_REJECTIONS["109"])["request"]
        consignee_elsewhere = {
            **request,
            "parties": [
                {**party, "address": {**party["address"], "countryCode": "DK"}}
                if party["type"] == "Consignee"
                else party
                for party in request["parties"]
            ],
        }
        self.assertEqual(
            create.separate_agreement_lane(consignee_elsewhere), dict(product="109", country="GB")
        )

        isle_of_man = gateway.mapper.create_shipment_request(
            shipment_request(
                **{
                    **LONDON_PAYLOAD,
                    "service": "dhl_freight_sweden_parcel_connect_plus",
                    "recipient": {**LONDON_PAYLOAD["recipient"], "country_code": "IM", "postal_code": "IM1 1AA"},
                    "options": dict(dhl_freight_sweden_customs_handling_full_service=True),
                    "customs": {**LONDON_PAYLOAD["customs"], "incoterm": "DDP"},
                }
            )
        )
        self.assertEqual(
            (isle_of_man.ctx or {}).get("separate_agreement"), dict(product="112", country="GB")
        )

    def test_no_note_off_the_gb_lane_or_for_other_codes(self):
        gb_request = booking_exchange(GB_REJECTIONS["112"])["request"]
        gb_response = booking_exchange(GB_REJECTIONS["112"])["response"]
        access_point_103 = booking_exchange("rejection-22001-103-se-access-point-id-only.json")
        payer_code = booking_exchange("rejection-22020-112-se-pl-payer-code-1.json")
        cases = {
            "22026 on 103 within SE": (access_point_103["request"], access_point_103["response"]),
            "202 to GB": ({**gb_request, "productCode": "202"}, gb_response),
            "112 to GB rejected with 22020": (gb_request, payer_code["response"]),
        }

        for case, (request, response) in cases.items():
            with self.subTest(case):
                self.assertEqual(notes(parse(request, response)), [])


if __name__ == "__main__":
    unittest.main()
