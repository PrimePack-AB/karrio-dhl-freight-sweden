"""Booking guard against DHL Product API product matches.

Before a booking is sent, the connector asks product matches for the
booking's Consignor and Consignee postal codes and pieces, and refuses the
booking when the product is not among the matched codes. Production booked
109 to GB SE16 2BE while product matches offered HDI, 202, 601 and 233 for
the lane, the same answer as the sandbox exchange in
fixtures/sandbox/rejection-22005-109-se-gb.json. A lookup that fails leaves
availability unverified and the booking proceeds with a warning.
"""

import json
import pathlib
import typing
import unittest
import urllib.error
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio
from karrio.providers.dhl_freight_sweden import units
from karrio.providers.dhl_freight_sweden.product_matches import ProductNotOfferedError

from .fixture import _gateway, as_dict, http_error, proxy_of
from .test_separate_agreement import LONDON_PAYLOAD
from .test_shipment import _payload, _recipient_se

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "sandbox"
MATCHES_PATH = "/productapi/v1/productmatches"
TI_PATH = "/transportinstruction/sendtransportinstruction"

enforce_gateway = _gateway({"product_matches": "enforce"})
warn_gateway = _gateway({"product_matches": "warn"})
# A connection that never set product_matches, unlike the shared offline
# test gateways, which turn the guard off.
unset_gateway = karrio.gateway["dhl_freight_sweden"].create(
    dict(
        test_mode=True,
        carrier_id="dhl_freight_sweden",
        client_key="TEST_CLIENT_KEY",
        account_number="1234567",
        international_account_number="123456",
    )
)


def _evidence(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _exchange(name: str, endpoint: str) -> dict:
    return next(
        exchange
        for exchange in _evidence(name)["exchanges"]
        if exchange["endpoint"].endswith(endpoint)
    )


GB_MATCHES = _exchange("rejection-22005-109-se-gb.json", MATCHES_PATH)
SE_MATCHES = _exchange("lookup-product-matches-se-se.json", MATCHES_PATH)
DOMESTIC_BOOKING = [
    lib.to_json(exchange["response"])
    for exchange in _evidence("booking-2906761222-102-se-se.json")["exchanges"]
]
DOMESTIC_PAYLOAD = _payload("dhl_freight_sweden_paket", _recipient_se)
LONDON = {**LONDON_PAYLOAD, "reference": "GUARD-TEST"}

REFUSAL_109_GB = (
    "Product 109 (dhl_freight_sweden_parcel_connect_b2c) is not offered from "
    "SE 11143 to GB SE16 2BE by DHL product matches; offered for this lane: "
    "202 (dhl_freight_sweden_road_freight_standard), "
    "601 (dhl_freight_sweden_home_delivery_international_b2c), "
    "233 (dhl_freight_sweden_road_freight_priority), "
    "and HDI, which the connector does not support. "
    + units.separate_agreement_message("109", "GB")
)


def _book(gateway_, payload: dict, *responses: typing.Any):
    with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
        mock.side_effect = _answers(*responses)
        result = (
            karrio.Shipment.create(models.ShipmentRequest(**payload))
            .from_(gateway_)
            .parse()
        )
    return result, [call.kwargs["url"] for call in mock.call_args_list], mock


def _answers(*responses: typing.Any) -> typing.Callable[..., typing.Any]:
    pending = list(responses)

    def side_effect(**kwargs: typing.Any) -> typing.Any:
        response = pending.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response(**kwargs) if callable(response) else response

    return side_effect


class TestProductMatchGuard(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_default_mode_is_enforce(self):
        self.assertEqual(
            str(enforce_gateway.settings.connection_config.product_matches.state),
            "enforce",
        )
        self.assertEqual(
            str(_gateway({}).settings.connection_config.product_matches.state),
            "off",
            "the shared offline test gateway turns the guard off",
        )
        self.assertEqual(
            str(unset_gateway.settings.connection_config.product_matches.state),
            "enforce",
        )

    def test_offered_product_books_after_the_lookup(self):
        for service in ("102", "dhl_freight_sweden_paket"):
            with self.subTest(service=service):
                (details, messages), urls, mock = _book(
                    enforce_gateway,
                    {**DOMESTIC_PAYLOAD, "service": service},
                    lib.to_json(SE_MATCHES["response"]),
                    *DOMESTIC_BOOKING,
                )

                self.assertIsNotNone(details)
                self.assertEqual(messages, [])
                self.assertTrue(urls[0].endswith(MATCHES_PATH))
                self.assertTrue(urls[1].endswith(TI_PATH))
                self.assertEqual(
                    lib.to_dict(mock.call_args_list[0].kwargs["data"]),
                    {
                        "parties": [
                            {"type": "Consignor", "address": {"countryCode": "SE", "postalCode": "11143"}},
                            {"type": "Consignee", "address": {"countryCode": "SE", "postalCode": "41103"}},
                        ],
                        "pieces": [
                            {"weight": 5.0, "length": 30.0, "width": 20.0, "height": 15.0, "volume": 0.01}
                        ],
                    },
                )

    def test_not_offered_product_is_refused_before_booking(self):
        for service in ("109", "dhl_freight_sweden_parcel_connect_b2c"):
            with self.subTest(service=service):
                request = enforce_gateway.mapper.create_shipment_request(
                    models.ShipmentRequest(**{**LONDON, "service": service})
                )
                with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
                    mock.side_effect = _answers(lib.to_json(GB_MATCHES["response"]))
                    with self.assertRaises(ProductNotOfferedError) as context:
                        proxy_of(enforce_gateway).create_shipment(request)

                self.assertEqual(mock.call_count, 1)
                self.assertTrue(mock.call_args.kwargs["url"].endswith(MATCHES_PATH))
                sent = as_dict(lib.to_dict(mock.call_args.kwargs["data"]))
                self.assertEqual(sent["parties"], GB_MATCHES["request"]["parties"])
                self.assertEqual(
                    sent["pieces"],
                    [{"weight": 1.0, "length": 30.0, "width": 20.0, "height": 10.0, "volume": 0.01}],
                    "the booking's own piece measurements, as its transport instruction sends them",
                )
                self.assertEqual(str(context.exception), REFUSAL_109_GB)
                self.assertEqual(context.exception.code, "SHIPPING_SDK_FIELD_ERROR")
                self.assertEqual(
                    context.exception.details,
                    {
                        "service": dict(
                            code="product_not_offered", message=REFUSAL_109_GB
                        )
                    },
                )

    def test_empty_match_list_refuses(self):
        request = enforce_gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**DOMESTIC_PAYLOAD)
        )
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.side_effect = _answers("[]")
            with self.assertRaises(ProductNotOfferedError) as context:
                proxy_of(enforce_gateway).create_shipment(request)

        self.assertEqual(
            str(context.exception),
            "Product 102 (dhl_freight_sweden_paket) is not offered from SE 11143 "
            "to SE 41103 by DHL product matches; no product is offered for this lane.",
        )

    def test_unset_mode_refuses_like_enforce(self):
        (details, messages), urls, _ = _book(
            unset_gateway, LONDON, lib.to_json(GB_MATCHES["response"])
        )

        self.assertIsNone(details)
        self.assertEqual(len(urls), 1)
        self.assertEqual(
            [(m.code, m.message) for m in messages],
            [("SHIPPING_SDK_FIELD_ERROR", REFUSAL_109_GB)],
        )

    def test_warn_mode_books_and_warns(self):
        rejection = _exchange("rejection-22005-109-se-gb.json", TI_PATH)["response"]
        (details, messages), urls, _ = _book(
            warn_gateway,
            LONDON,
            lib.to_json(GB_MATCHES["response"]),
            http_error(400, json.dumps(rejection)),
        )

        self.assertIsNone(details)
        self.assertTrue(urls[1].endswith(TI_PATH))
        warning = next(m for m in messages if m.code == "product_not_offered")
        self.assertEqual(warning.level, "warning")
        self.assertEqual(warning.message, REFUSAL_109_GB)

    def test_off_mode_sends_no_lookup(self):
        (details, messages), urls, _ = _book(
            _gateway({"product_matches": "off"}), DOMESTIC_PAYLOAD, *DOMESTIC_BOOKING
        )

        self.assertIsNotNone(details)
        self.assertEqual(messages, [])
        self.assertFalse(any(url.endswith(MATCHES_PATH) for url in urls))

    def test_failed_lookup_books_with_unverified_warning(self):
        cases = {
            "unknown client key": (
                http_error(401, '{"error": "No valid application matching client key"}'),
                "No valid application matching client key",
            ),
            "validation error": (
                json.dumps(
                    {
                        "error": "One or more validation errors occurred.",
                        "errors": [{"errorCode": 22001, "message": "The Consignee address postal code is required"}],
                    }
                ),
                "The Consignee address postal code is required",
            ),
            "unrecognized body": ('{"message": "Gateway timeout"}', "expected a JSON array"),
            "non-JSON HTTP error": (http_error(502, "<html>Bad Gateway</html>"), "HTTP 502"),
            "network error": (urllib.error.URLError("connection refused"), "connection refused"),
        }
        for mode, gateway_ in (("enforce", enforce_gateway), ("warn", warn_gateway)):
            for case, (answer, text) in cases.items():
                with self.subTest(mode=mode, case=case):
                    (details, messages), urls, _ = _book(
                        gateway_, DOMESTIC_PAYLOAD, answer, *DOMESTIC_BOOKING
                    )

                    self.assertIsNotNone(details)
                    self.assertTrue(urls[1].endswith(TI_PATH))
                    (warning,) = messages
                    self.assertEqual(warning.code, "product_availability_unverified")
                    self.assertEqual(warning.level, "warning")
                    self.assertTrue(
                        warning.message.startswith(
                            "Product availability was not verified (product matches lookup failed: "
                        ),
                        warning.message,
                    )
                    self.assertIn(text, warning.message)
                    self.assertTrue(
                        warning.message.endswith(
                            "); the booking proceeded without the check"
                        )
                    )

    def test_products_never_listed_are_not_guarded(self):
        self.assertEqual(
            units.PRODUCT_MATCH_UNGUARDED,
            frozenset({"205", "209", "210", "212", "SPI", "107"}),
        )
        payload = {
            **_payload("dhl_freight_sweden_pall", _recipient_se),
        }
        (details, _), urls, _ = _book(enforce_gateway, payload, *DOMESTIC_BOOKING)

        self.assertIsNotNone(details)
        self.assertFalse(any(url.endswith(MATCHES_PATH) for url in urls))

    def test_territory_recipient_is_matched_as_parent_country(self):
        isle_of_man = {
            **LONDON,
            "service": "dhl_freight_sweden_road_freight_standard",
            "recipient": {**LONDON["recipient"], "country_code": "IM", "postal_code": "IM1 1AA"},
            "options": dict(
                dhl_freight_sweden_customs_handling_full_service=True,
                dhl_freight_sweden_payer_code="DAP",
            ),
        }
        request = enforce_gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**isle_of_man)
        )
        matches = _exchange("lookup-product-matches-se-gb-im11aa.json", MATCHES_PATH)
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.side_effect = _answers(
                lib.to_json(matches["response"]), *DOMESTIC_BOOKING
            )
            proxy_of(enforce_gateway).create_shipment(request)

        consignee = as_dict(lib.to_dict(mock.call_args_list[0].kwargs["data"]))["parties"][1]
        self.assertEqual(consignee["address"], {"countryCode": "GB", "postalCode": "IM1 1AA"})


if __name__ == "__main__":
    unittest.main()
