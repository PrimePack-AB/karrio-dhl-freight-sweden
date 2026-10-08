"""DHL Freight address validation tests (PostalCodes API route lookup).

Route fixtures are PostalCodes API route responses
(GET /postalcodeapi/v1/postalcodes/SE/{pc}/route): 11120 Stockholm and
41103 Göteborg are generally bookable with home delivery, 98138 Kiruna is
bookable without home delivery (product 118 unavailable), and 99999
returns the PascalCase ``ErrorResult`` the live API emits where the
vendored spec declares camelCase
(fixtures/sandbox/lookup-postal-code-se-99999-16010.json).
"""

import typing
import unittest
from unittest.mock import patch
from .fixture import (
    address_validation_request,
    answers,
    as_list,
    gateway,
    http_error,
    settings_of,
)

import karrio.lib as lib
import karrio.sdk as karrio


class TestDHLFreightSwedenAddressValidation(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_create_address_validation_request(self):
        unscoped = gateway.mapper.create_address_validation_request(
            address_validation_request(**AddressValidationParams)
        )
        self.assertEqual(
            lib.to_dict(unscoped.serialize()),
            dict(country_code="SE", postal_code="11120"),
        )
        self.assertEqual(unscoped.ctx, dict(service=None))

        scoped = gateway.mapper.create_address_validation_request(
            address_validation_request(**ScopedAddressValidationParams)
        )
        self.assertEqual(
            lib.to_dict(scoped.serialize()),
            dict(country_code="SE", postal_code="98138", service="118"),
        )
        self.assertEqual(scoped.ctx, dict(service="118"))

    def test_validate_address(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = RouteResponseStockholm
            karrio.Address.validate(
                address_validation_request(**ScopedStockholmParams)
            ).from_(gateway)

        self.assertEqual(
            mock.call_args.kwargs["url"],
            f"{settings_of(gateway).postal_code_api_url}/postalcodes/SE/11120/route",
        )
        self.assertEqual(mock.call_args.kwargs["method"], "GET")
        self.assertEqual(
            mock.call_args.kwargs["headers"], {"client-key": "TEST_CLIENT_KEY"}
        )
        self.assertIs(mock.call_args.kwargs["on_error"], lib.error_decoder)

    def test_parse_address_validation_response(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = RouteResponseStockholm
            scoped = (
                karrio.Address.validate(
                    address_validation_request(**ScopedStockholmParams)
                )
                .from_(gateway)
                .parse()
            )

        self.assertListEqual(as_list(lib.to_dict(scoped)), ParsedStockholmScoped)

        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = RouteResponseKiruna
            unscoped = (
                karrio.Address.validate(
                    address_validation_request(**KirunaParams)
                )
                .from_(gateway)
                .parse()
            )
            scoped_not_servable = (
                karrio.Address.validate(
                    address_validation_request(**ScopedKirunaParams)
                )
                .from_(gateway)
                .parse()
            )

        # Unscoped reads the general bookable flag; the product-118 scope
        # reads homeDeliveryParcel, so the same Kiruna route is servable
        # unscoped and unservable scoped.
        self.assertListEqual(as_list(lib.to_dict(unscoped)), ParsedKirunaUnscoped)
        self.assertListEqual(as_list(lib.to_dict(scoped_not_servable)), ParsedKirunaScoped)

    def test_parse_error_response(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = RouteLookupErrorResponse
            parsed = (
                karrio.Address.validate(
                    address_validation_request(**NotFoundParams)
                )
                .from_(gateway)
                .parse()
            )

        self.assertListEqual(as_list(lib.to_dict(parsed)), ParsedErrorResponse)

    def _validate(self, response) -> typing.List[typing.Any]:
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.side_effect = answers(response)
            parsed = (
                karrio.Address.validate(address_validation_request(**ScopedStockholmParams))
                .from_(gateway)
                .parse()
            )

        return as_list(lib.to_dict(parsed))

    def test_parse_refusal_codes(self):
        for code in (16009, 16010, 16011, 16012):
            with self.subTest(code=code):
                details, messages = self._validate(
                    http_error(400, RouteLookupError % code)
                )

                self.assertIsNone(details)
                self.assertEqual([m["code"] for m in messages], [str(code)])

    def test_parse_api_unavailable(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self.assertListEqual(
                    self._validate(http_error(status, MissingClientKeyResponse)),
                    [None, [{**ApiUnavailableMessage, "details": {"http_status": status}}]],
                )

    def test_parse_unverified(self):
        cases = {
            "400 outside the refusal codes": http_error(400, RouteLookupError % 16001),
            "404 not JSON": http_error(404, "Not Found"),
            "500 error body": http_error(500, '{"error": "Internal Server Error"}'),
            "503 empty body": http_error(503),
            "200 not JSON": "<html>maintenance</html>",
            "connection error": ConnectionError("route API unreachable"),
        }
        for case, response in cases.items():
            with self.subTest(case=case):
                self.assertListEqual(
                    self._validate(response), [None, [UnverifiedMessage]]
                )


if __name__ == "__main__":
    unittest.main()


AddressValidationParams = {
    "address": {"postal_code": "11120", "country_code": "SE"},
}

ScopedAddressValidationParams = {
    "address": {"postal_code": "98138", "country_code": "SE"},
    "options": {"service": "dhl_freight_sweden_hemleverans_paket_b2c"},
}

ScopedStockholmParams = {
    "address": {"postal_code": "11120", "country_code": "SE"},
    "options": {"service": "118"},
}

KirunaParams = {
    "address": {"postal_code": "98138", "country_code": "SE"},
}

ScopedKirunaParams = {
    **KirunaParams,
    "options": {"service": "dhl_freight_sweden_hemleverans_paket_b2c"},
}

NotFoundParams = {
    "address": {"postal_code": "99999", "country_code": "SE"},
}

RouteResponseStockholm = """{
  "countryCode": "SE",
  "postalCode": "11120",
  "city": "STOCKHOLM",
  "lineHaul": "110",
  "terminalId": "4210",
  "deviating": "0",
  "updatedDate": "2006-01-11T00:00:00",
  "bookable": true,
  "homeDeliveryParcel": true
}"""

RouteResponseKiruna = """{
  "countryCode": "SE",
  "postalCode": "98138",
  "city": "KIRUNA",
  "lineHaul": "950",
  "terminalId": "4850",
  "deviating": "0",
  "updatedDate": "2026-07-02T22:00:03",
  "bookable": true,
  "homeDeliveryParcel": false
}"""

RouteLookupErrorResponse = """{"Status":400,"ErrorCode":16010,"UserMessage":"Post code '99999' not found."}"""

RouteLookupError = """{"Status":400,"ErrorCode":%d,"UserMessage":"Post code '11120' not served."}"""

# The sandbox body for a request without a client key (and, with
# "No valid application matching client key", for an unknown key); the
# body an application without PostalCode API access receives is not
# captured, so 401 and 403 are treated alike.
MissingClientKeyResponse = """{"error":"Missing client key"}"""

ApiUnavailableMessage = {
    "carrier_id": "dhl_freight_sweden",
    "carrier_name": "dhl_freight_sweden",
    "code": "postal_code_api_unavailable",
    "level": "warning",
    "message": (
        "Postal code location could not be verified: the PostalCode API "
        "is not available for this application"
    ),
}

UnverifiedMessage = {
    "carrier_id": "dhl_freight_sweden",
    "carrier_name": "dhl_freight_sweden",
    "code": "address_validation_unavailable",
    "level": "warning",
    "message": (
        "Postal code location could not be verified (address validation "
        "API error)"
    ),
}

ParsedStockholmScoped = [
    {
        "carrier_id": "dhl_freight_sweden",
        "carrier_name": "dhl_freight_sweden",
        "success": True,
        "complete_address": {
            "city": "STOCKHOLM",
            "postal_code": "11120",
            "country_code": "SE",
            "residential": False,
        },
    },
    [],
]

ParsedKirunaUnscoped = [
    {
        "carrier_id": "dhl_freight_sweden",
        "carrier_name": "dhl_freight_sweden",
        "success": True,
        "complete_address": {
            "city": "KIRUNA",
            "postal_code": "98138",
            "country_code": "SE",
            "residential": False,
        },
    },
    [],
]

ParsedKirunaScoped = [
    {
        "carrier_id": "dhl_freight_sweden",
        "carrier_name": "dhl_freight_sweden",
        "success": False,
        "complete_address": {
            "city": "KIRUNA",
            "postal_code": "98138",
            "country_code": "SE",
            "residential": False,
        },
    },
    [],
]

ParsedErrorResponse = [
    None,
    [
        {
            "carrier_id": "dhl_freight_sweden",
            "carrier_name": "dhl_freight_sweden",
            "code": "16010",
            "message": "Post code '99999' not found.",
            "details": {},
        }
    ],
]
