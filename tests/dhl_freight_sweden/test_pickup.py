"""Pickup scheduling over the PickupRequest API.

The request and parse expectations come from the committed sandbox
fixtures: pickup-421-2026-10-19-12.19.04.489334-102-se-se-no-consignee.json
is the request shape the connector sends (a Consignor and a Pickup party at
the pickup address, the customer number on the Pickup party, no Consignee),
which DHL accepted, and pickup-102-se-se-customer-number-unknown.json is a
rejection answered with status 1 and a Swedish message. The PickupRequest
API books pickups for the products of product manual v5.26 §10.14.12 p236,
and a booked pickup cannot be cancelled electronically (§5.2 p14).
"""

import copy
import json
import pathlib
import typing
import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
import karrio.mappers.dhl_freight_sweden.proxy as connector_proxy
import karrio.providers.dhl_freight_sweden.pickup as provider_pickup
import karrio.providers.dhl_freight_sweden.shipment.create as provider_create
import karrio.sdk as karrio

from .fixture import as_list, gateway, serialize_request, settings_of

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "sandbox"
AcceptedPickup = json.loads(
    (
        FIXTURES / "pickup-421-2026-10-19-12.19.04.489334-102-se-se-no-consignee.json"
    ).read_text()
)
RejectedPickup = json.loads(
    (FIXTURES / "pickup-102-se-se-customer-number-unknown.json").read_text()
)

PickupAddress = {
    "company_name": "Test Shipper AB",
    "person_name": "Sven Svensson",
    "address_line1": "Kungsgatan 1",
    "city": "Stockholm",
    "postal_code": "11143",
    "country_code": "SE",
    "phone_number": "+46 8 123 456",
    "email": "shipper@example.se",
}

PickupPayload = {
    "pickup_date": "2026-10-20",
    "ready_time": "10:00",
    "closing_time": "16:00",
    "instruction": "Sandbox test, no pickup needed",
    "address": PickupAddress,
    "parcels": [
        {
            "weight": 1.0,
            "weight_unit": "KG",
            "length": 30.0,
            "width": 20.0,
            "height": 10.0,
            "dimension_unit": "CM",
            "reference_number": "SANDBOX-TEST",
        }
    ],
    "options": {
        "dhl_freight_sweden_service": "dhl_freight_sweden_paket",
        "dhl_freight_sweden_payer_code": "1",
    },
}


DeliveryAddress = {
    "company_name": "Test Recipient AB",
    "address_line1": "Drottninggatan 2",
    "city": "Göteborg",
    "postal_code": "41103",
    "country_code": "SE",
}


def _pickup_request(**changes: typing.Any) -> models.PickupRequest:
    return models.PickupRequest(**{**copy.deepcopy(PickupPayload), **changes})


def _options(**changes: typing.Any) -> dict:
    return {**PickupPayload["options"], **changes}


def _fixture_request(fixture: dict, account_number: str) -> dict:
    """The fixture's request with the gateway's customer number on the Pickup party."""
    request = copy.deepcopy(fixture["exchanges"][0]["request"])
    for party in request["parties"]:
        if party["type"] == "Pickup":
            party["id"] = account_number
    return request


def _fixture_response(fixture: dict) -> str:
    return lib.to_json(fixture["exchanges"][0]["response"])


class TestPickupRequest(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_request_matches_the_accepted_sandbox_request(self):
        request = gateway.mapper.create_pickup_request(_pickup_request())

        self.assertEqual(
            serialize_request(request),
            _fixture_request(AcceptedPickup, str(settings_of(gateway).account_number)),
        )

    def test_product_code_option_is_accepted(self):
        request = gateway.mapper.create_pickup_request(
            _pickup_request(options=_options(dhl_freight_sweden_service="102"))
        )

        self.assertEqual(serialize_request(request)["productCode"], "102")

    def test_closing_time_is_not_sent(self):
        serialized = serialize_request(
            gateway.mapper.create_pickup_request(_pickup_request())
        )

        self.assertNotIn("additionalServices", serialized)
        self.assertEqual(serialized["pickupDate"], "2026-10-20T10:00:00")

    def test_package_location_follows_the_instruction(self):
        serialized = serialize_request(
            gateway.mapper.create_pickup_request(
                _pickup_request(package_location="Loading dock 2")
            )
        )

        self.assertEqual(
            serialized["pickupInstruction"],
            "Sandbox test, no pickup needed; Loading dock 2",
        )

    def test_totals_sum_every_parcel(self):
        parcel = PickupPayload["parcels"][0]
        serialized = serialize_request(
            gateway.mapper.create_pickup_request(
                _pickup_request(parcels=[parcel, {**parcel, "weight": 2.5}])
            )
        )

        self.assertEqual(serialized["totalNumberOfPieces"], 2)
        self.assertEqual(serialized["totalWeight"], 3.5)
        self.assertEqual(serialized["totalVolume"], 0.012)
        self.assertEqual(len(serialized["pieces"]), 2)

    def test_total_volume_is_omitted_when_a_parcel_lacks_dimensions(self):
        parcel = PickupPayload["parcels"][0]
        serialized = serialize_request(
            gateway.mapper.create_pickup_request(
                _pickup_request(parcels=[parcel, {"weight": 2.0, "weight_unit": "KG"}])
            )
        )

        self.assertNotIn("totalVolume", serialized)
        self.assertEqual(serialized["totalWeight"], 3.0)

    def test_every_listed_product_is_accepted(self):
        for code in ("102", "112", "209", "210", "211", "212", "103", "109", "118", "401"):
            payer = "023" if code == "112" else "022" if code == "109" else "1"
            with self.subTest(code=code):
                serialized = serialize_request(
                    gateway.mapper.create_pickup_request(
                        _pickup_request(
                            options=_options(
                                dhl_freight_sweden_service=code,
                                dhl_freight_sweden_payer_code=payer,
                                dhl_freight_sweden_delivery_address=DeliveryAddress,
                            )
                        )
                    )
                )
                self.assertEqual(serialized["productCode"], code)
                self.assertEqual(serialized["payerCode"], {"code": payer})


class TestPickupRefusals(unittest.TestCase):
    def test_missing_product_is_refused(self):
        options = _options()
        options.pop("dhl_freight_sweden_service")

        with self.assertRaises(provider_pickup.PickupServiceError) as raised:
            gateway.mapper.create_pickup_request(_pickup_request(options=options))

        self.assertEqual(
            raised.exception.details,
            {
                "dhl_freight_sweden_service": dict(
                    code="required",
                    message="one of 102, 112, 209, 210, 211, 212, 103, 109, 118, 401 is required",
                )
            },
        )

    def test_product_outside_the_manual_list_is_refused(self):
        for service in ("202", "dhl_freight_sweden_service_point_c2b", "999"):
            with self.subTest(service=service):
                with self.assertRaises(provider_pickup.PickupServiceError) as raised:
                    gateway.mapper.create_pickup_request(
                        _pickup_request(
                            options=_options(dhl_freight_sweden_service=service)
                        )
                    )

                self.assertIn("§10.14.12 p236", str(raised.exception))
                self.assertEqual(
                    set(raised.exception.details or {}), {"dhl_freight_sweden_service"}
                )

    def test_missing_payer_code_is_refused(self):
        options = _options()
        options.pop("dhl_freight_sweden_payer_code")

        with self.assertRaises(provider_create.PayerCodeError) as raised:
            gateway.mapper.create_pickup_request(_pickup_request(options=options))

        self.assertEqual(
            raised.exception.details,
            {
                "dhl_freight_sweden_payer_code": dict(
                    code="required", message="one of 1, 3, 4 is required"
                )
            },
        )

    def test_payer_code_outside_the_product_codes_is_refused(self):
        with self.assertRaises(provider_create.PayerCodeError) as raised:
            gateway.mapper.create_pickup_request(
                _pickup_request(
                    options=_options(
                        dhl_freight_sweden_service="112",
                        dhl_freight_sweden_payer_code="1",
                    )
                )
            )

        self.assertEqual(
            set(raised.exception.details or {}), {"dhl_freight_sweden_payer_code"}
        )

    def test_parcel_without_weight_is_refused(self):
        with self.assertRaises(provider_pickup.PickupParcelError) as raised:
            gateway.mapper.create_pickup_request(
                _pickup_request(parcels=[{"weight": 0, "weight_unit": "KG"}])
            )

        self.assertEqual(set(raised.exception.details or {}), {"parcels[0].weight"})

    def test_pickup_without_parcels_is_refused(self):
        with self.assertRaises(provider_pickup.PickupParcelError) as raised:
            gateway.mapper.create_pickup_request(_pickup_request(parcels=[]))

        self.assertEqual(set(raised.exception.details or {}), {"parcels"})

    def test_missing_pickup_date_or_ready_time_is_refused(self):
        for field in ("pickup_date", "ready_time"):
            with self.subTest(field=field):
                with self.assertRaises(provider_pickup.PickupDateError) as raised:
                    gateway.mapper.create_pickup_request(_pickup_request(**{field: None}))

                self.assertEqual(set(raised.exception.details or {}), {field})


class TestPickup212(unittest.TestCase):
    """212 pickups carry the delivery place and the freight payer (§5.8 p38).

    The manual makes a 212 pickup request carry at least the address, postal
    code, and city of the physical delivery place and the freight payer party
    with the paying DHL account number; the manual's 212 party table sends
    the delivery address as CN and adds DP only when it differs (§5.8 p39).
    """

    def setUp(self):
        self.maxDiff = None

    def _options(self, **changes: typing.Any) -> dict:
        return _options(
            **{
                "dhl_freight_sweden_service": "212",
                "dhl_freight_sweden_delivery_address": DeliveryAddress,
                **changes,
            }
        )

    def test_212_sends_the_delivery_place_and_the_freight_payer(self):
        account_number = str(settings_of(gateway).account_number)
        serialized = serialize_request(
            gateway.mapper.create_pickup_request(
                _pickup_request(options=self._options())
            )
        )
        parties = {party["type"]: party for party in serialized["parties"]}

        self.assertEqual(
            [party["type"] for party in serialized["parties"]],
            ["Consignor", "Pickup", "Consignee", "FreightPayer"],
        )
        self.assertNotIn("id", parties["Consignor"])
        self.assertEqual(parties["Pickup"]["id"], account_number)
        self.assertEqual(
            parties["Consignee"],
            {
                "type": "Consignee",
                "name": "Test Recipient AB",
                "contactName": "Test Recipient AB",
                "address": {
                    "street": "Drottninggatan 2",
                    "cityName": "Göteborg",
                    "postalCode": "41103",
                    "countryCode": "SE",
                },
            },
        )
        self.assertEqual(
            parties["FreightPayer"],
            {**parties["Consignor"], "type": "FreightPayer", "id": account_number},
        )

    def test_delivery_place_may_be_a_json_object_string(self):
        serialized = serialize_request(
            gateway.mapper.create_pickup_request(
                _pickup_request(
                    options=self._options(
                        dhl_freight_sweden_delivery_address=json.dumps(DeliveryAddress)
                    )
                )
            )
        )

        self.assertIn("Consignee", [party["type"] for party in serialized["parties"]])

    def test_other_products_ignore_the_delivery_place(self):
        serialized = serialize_request(
            gateway.mapper.create_pickup_request(
                _pickup_request(
                    options=_options(dhl_freight_sweden_delivery_address=DeliveryAddress)
                )
            )
        )

        self.assertEqual(
            [party["type"] for party in serialized["parties"]], ["Consignor", "Pickup"]
        )

    def test_212_without_the_delivery_place_is_refused(self):
        options = self._options()
        options.pop("dhl_freight_sweden_delivery_address")

        with self.assertRaises(provider_pickup.PickupDeliveryAddressError) as raised:
            gateway.mapper.create_pickup_request(_pickup_request(options=options))

        self.assertIn("§5.8 p38", str(raised.exception))
        self.assertEqual(
            raised.exception.details,
            {
                "dhl_freight_sweden_delivery_address": dict(
                    code="required",
                    message="the delivery place's address_line1, postal_code, "
                    "city, and country_code are required",
                )
            },
        )

    def test_212_delivery_place_missing_fields_is_refused(self):
        partial = {"address_line1": "Drottninggatan 2", "country_code": "SE"}

        with self.assertRaises(provider_pickup.PickupDeliveryAddressError) as raised:
            gateway.mapper.create_pickup_request(
                _pickup_request(
                    options=self._options(dhl_freight_sweden_delivery_address=partial)
                )
            )

        self.assertIn("§5.8 p38", str(raised.exception))
        self.assertEqual(
            raised.exception.details,
            {
                "dhl_freight_sweden_delivery_address": dict(
                    code="required", message="missing postal_code, city"
                )
            },
        )

    def test_212_delivery_place_that_is_not_an_address_is_refused(self):
        for value in ("Göteborg", ["Drottninggatan 2"], {**DeliveryAddress, "street": "x"}):
            with self.subTest(value=value):
                with self.assertRaises(
                    provider_pickup.PickupDeliveryAddressError
                ) as raised:
                    gateway.mapper.create_pickup_request(
                        _pickup_request(
                            options=self._options(
                                dhl_freight_sweden_delivery_address=value
                            )
                        )
                    )

                self.assertEqual(
                    raised.exception.details["dhl_freight_sweden_delivery_address"]["code"],  # type: ignore[index]
                    "invalid",
                )


class TestPickupProxy(unittest.TestCase):
    def test_posts_to_the_pickup_request_endpoint(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = _fixture_response(AcceptedPickup)
            karrio.Pickup.schedule(_pickup_request()).from_(gateway)

            self.assertEqual(
                mock.call_args[1]["url"],
                "https://test-api.freight-logistics.dhl.com"
                "/pickuprequestapi/v1/pickuprequest/pickuprequest",
            )
            self.assertEqual(
                mock.call_args[1]["headers"]["client-key"], "TEST_CLIENT_KEY"
            )

    def test_no_pickup_update_or_cancel(self):
        self.assertNotIn("cancel_pickup", vars(connector_proxy.Proxy))
        self.assertNotIn("modify_pickup", vars(connector_proxy.Proxy))


class TestPickupResponse(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_accepted_pickup(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = _fixture_response(AcceptedPickup)
            parsed = karrio.Pickup.schedule(_pickup_request()).from_(gateway).parse()

        self.assertListEqual(
            as_list(lib.to_dict(parsed)),
            [
                {
                    "carrier_id": "dhl_freight_sweden",
                    "carrier_name": "dhl_freight_sweden",
                    "confirmation_number": "421-2026-10-19-12.19.04.489334",
                    "pickup_date": "2026-10-20",
                    "ready_time": "10:00",
                    "meta": {
                        "message": "Bekräftad! Din bokning  ' VARIOUS' har bokningsnummer "
                        "421-2026-10-19-12.19.04.489334",
                    },
                },
                [],
            ],
        )

    def test_rejected_pickup(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = _fixture_response(RejectedPickup)
            parsed = karrio.Pickup.schedule(_pickup_request()).from_(gateway).parse()

        self.assertListEqual(
            as_list(lib.to_dict(parsed)),
            [
                None,
                [
                    {
                        "carrier_id": "dhl_freight_sweden",
                        "carrier_name": "dhl_freight_sweden",
                        "code": "Rejected",
                        "message": "Ej accepterad! Din bokning  '11151 Stockholm' har inte "
                        "accepterats. \r\nAngivet kundnr 999999 är okänt.",
                        "details": {"status": 1},
                    }
                ],
            ],
        )

    def test_accepted_status_without_booking_number_is_not_a_pickup(self):
        body = {**AcceptedPickup["exchanges"][0]["response"], "bookingNumber": ""}
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = lib.to_json(body)
            details, messages = (
                karrio.Pickup.schedule(_pickup_request()).from_(gateway).parse()
            )

        self.assertIsNone(details)
        self.assertEqual(len(messages), 1)

    def test_accepted_pickup_without_pickup_date_time_has_no_date_or_time(self):
        body = {
            key: value
            for key, value in AcceptedPickup["exchanges"][0]["response"].items()
            if key != "pickupDateTime"
        }
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = lib.to_json(body)
            details, messages = (
                karrio.Pickup.schedule(_pickup_request()).from_(gateway).parse()
            )

        self.assertEqual(messages, [])
        assert details is not None
        self.assertEqual(details.confirmation_number, "421-2026-10-19-12.19.04.489334")
        self.assertIsNone(details.pickup_date)
        self.assertIsNone(details.ready_time)

    def test_error_response_body(self):
        body = {
            "status": "ERROR",
            "errorMessage": "One or more validation errors occurred.",
            "validationErrors": [
                {"field": "productCode", "errorCode": 100, "message": "Invalid."}
            ],
        }
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = lib.to_json(body)
            details, messages = (
                karrio.Pickup.schedule(_pickup_request()).from_(gateway).parse()
            )

        self.assertIsNone(details)
        self.assertTrue(messages)
        self.assertTrue(all(message.message for message in messages))


if __name__ == "__main__":
    unittest.main()
