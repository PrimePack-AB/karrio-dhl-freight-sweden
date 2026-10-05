"""DHL Freight service point locator tests (connector-local capability).

``ServicePointsResponse`` holds the parcelshop 8005-PL-4516440 and the
parcelstation 8005-PL-4599334, trimmed to the fields the normalizer
consumes; both appear with these values in the unfiltered Warszawa 00-251
lookup of fixtures/sandbox/lookup-service-points-pl-capacity-too-large.json.
``ErrorResponse`` is
constructed to the spec's in-band ``status``/``errorMessage`` shape (the
endpoint declares no 4xx responses).
"""

import unittest
from unittest.mock import patch
from .fixture import as_list, gateway, proxy_of, serialize_request, settings_of

import karrio.lib as lib
import karrio.core.errors as errors
import karrio.providers.dhl_freight_sweden.service_points as service_points


class TestDHLFreightSwedenServicePoints(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_create_service_points_request(self):
        request = service_points.service_points_request(
            ServicePointsParams, settings_of(gateway)
        )
        self.assertEqual(serialize_request(request), ServicePointsRequest)

    def test_create_service_points_unexpected_keys(self):
        for key, value in (("parcels", [{"weight": 25}]), ("piece", {"weight": 25})):
            with self.subTest(key=key):
                with self.assertRaises(errors.ShippingSDKDetailedError) as context:
                    service_points.service_points_request(
                        {**ServicePointsParams, key: value},
                        settings_of(gateway),
                    )

                exception = context.exception
                self.assertEqual(exception.code, "SHIPPING_SDK_FIELD_ERROR")
                self.assertIn(key, str(exception))
                self.assertEqual(
                    exception.details,
                    {key: dict(code="unexpected", message="unexpected payload key")},
                )

    def test_create_service_points_request_converts_lb_in_parcel(self):
        request = service_points.service_points_request(
            {**ServicePointsParams, "parcel": ImperialParcel},
            settings_of(gateway),
        )
        self.assertEqual(
            serialize_request(request)["piece"],
            {"width": 25.4, "height": 25.4, "length": 25.4, "weight": 2.27},
        )

    def test_create_service_points_request_tolerates_parcel_fields(self):
        request = service_points.service_points_request(
            {**ServicePointsParams, "parcel": FullKarrioParcel},
            settings_of(gateway),
        )
        self.assertEqual(
            serialize_request(request)["piece"],
            {"width": 40, "height": 40, "length": 60, "weight": 25},
        )

    def test_find_service_points(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = "{}"
            request = service_points.service_points_request(
                ServicePointsParams, settings_of(gateway)
            )
            proxy_of(gateway).find_service_points(request)
            url = mock.call_args.kwargs["url"]
        self.assertIn(
            "/servicepointlocatorapi/v1/servicepoint/findnearestservicepoints", url
        )
        self.assertEqual(mock.call_args.kwargs["method"], "POST")
        self.assertEqual(
            mock.call_args.kwargs["headers"],
            {
                "Content-Type": "application/json",
                "client-key": "TEST_CLIENT_KEY",
            },
        )
        self.assertEqual(
            lib.to_dict(mock.call_args.kwargs["data"]), ServicePointsRequest
        )

    def test_parse_service_points_response(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = ServicePointsResponse
            request = service_points.service_points_request(
                ServicePointsParams, settings_of(gateway)
            )
            parsed = service_points.parse_service_points_response(
                proxy_of(gateway).find_service_points(request), settings_of(gateway)
            )
            self.assertListEqual(as_list(lib.to_dict(parsed)), ParsedServicePoints)

    def test_parse_service_points_error(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = ErrorResponse
            request = service_points.service_points_request(
                ServicePointsParams, settings_of(gateway)
            )
            parsed = service_points.parse_service_points_response(
                proxy_of(gateway).find_service_points(request), settings_of(gateway)
            )
            self.assertListEqual(as_list(lib.to_dict(parsed)), ParsedErrorResponse)

    def test_parse_service_points_non_object_response(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.return_value = "[]"
            request = service_points.service_points_request(
                ServicePointsParams, settings_of(gateway)
            )
            parsed = service_points.parse_service_points_response(
                proxy_of(gateway).find_service_points(request), settings_of(gateway)
            )
            self.assertListEqual(as_list(lib.to_dict(parsed)), ParsedNonObjectResponse)


ServicePointsParams = {
    "address": {
        "street": "Nowogrodzka",
        "street_number": "31",
        "city": "Warszawa",
        "postal_code": "00-251",
        "country_code": "PL",
    },
    "location_types": ["locker"],
    "max_items": 2,
    "distance": {"value": 10, "unit": "km"},
    "parcel": {"length": 60, "width": 40, "height": 40, "weight": 25},
}

ImperialParcel = {
    "weight": 5,
    "weight_unit": "LB",
    "length": 10,
    "width": 10,
    "height": 10,
    "dimension_unit": "IN",
}

FullKarrioParcel = {
    "id": "parcel_1",
    "weight": 25,
    "length": 60,
    "width": 40,
    "height": 40,
    "packaging_type": "small_box",
    "description": "Books",
    "reference_number": "REF-1",
    "options": {"insurance": 100},
    "items": [{"title": "Book", "quantity": 1, "weight": 25, "weight_unit": "KG"}],
}

ServicePointsRequest = {
    "address": {
        "street": "Nowogrodzka",
        "streetNumber": "31",
        "cityName": "Warszawa",
        "postalCode": "00-251",
        "countryCode": "PL",
    },
    "locationTypes": ["locker"],
    "maxNumberOfItems": 2,
    "distance": 10,
    "distanceUnit": "km",
    "piece": {"width": 40, "height": 40, "length": 60, "weight": 25},
}

ServicePointsResponse = """{
  "status": "OK",
  "servicePoints": [
    {
      "id": "101",
      "servicePointId": "8005-PL-4516440",
      "street": "SENATORSKA 2",
      "name": "DHL Parcelshop",
      "shopName": "ŻABKA",
      "cityName": "WARSZAWA",
      "postalCode": "00-075",
      "countryCode": "PL",
      "distance": 0.06,
      "distanceUnit": "km",
      "locationType": "servicepoint",
      "serviceTypes": [
        "parcel:pick-up",
        "cash-on-delivery",
        "parcel:drop-off"
      ],
      "latitude": 52.246463,
      "longitude": 21.012219
    },
    {
      "id": "501",
      "servicePointId": "8005-PL-4599334",
      "street": "Plac Bankowy 2",
      "name": "DHL Parcelstation",
      "shopName": "Automat DHL BOX 24/7",
      "cityName": "Warszawa",
      "postalCode": "00-095",
      "countryCode": "PL",
      "distance": 0.66,
      "distanceUnit": "km",
      "locationType": "locker",
      "serviceTypes": [
        "parcel:drop-off-unregistered",
        "cash-on-delivery",
        "parcel:pick-up-unregistered"
      ],
      "latitude": 52.244046,
      "longitude": 21.00276
    }
  ]
}"""

ParsedServicePoints = [
    [
        {
            "id": "101",
            "service_point_id": "8005-PL-4516440",
            "name": "DHL Parcelshop",
            "shop_name": "ŻABKA",
            "type": "servicepoint",
            "address": {
                "street": "SENATORSKA 2",
                "city": "WARSZAWA",
                "postal_code": "00-075",
                "country_code": "PL",
            },
            "coordinates": {"latitude": 52.246463, "longitude": 21.012219},
            "distance": 0.06,
            "distance_unit": "km",
            "service_types": [
                "parcel:pick-up",
                "cash-on-delivery",
                "parcel:drop-off",
            ],
        },
        {
            "id": "501",
            "service_point_id": "8005-PL-4599334",
            "name": "DHL Parcelstation",
            "shop_name": "Automat DHL BOX 24/7",
            "type": "locker",
            "address": {
                "street": "Plac Bankowy 2",
                "city": "Warszawa",
                "postal_code": "00-095",
                "country_code": "PL",
            },
            "coordinates": {"latitude": 52.244046, "longitude": 21.00276},
            "distance": 0.66,
            "distance_unit": "km",
            "service_types": [
                "parcel:drop-off-unregistered",
                "cash-on-delivery",
                "parcel:pick-up-unregistered",
            ],
        },
    ],
    [],
]

ErrorResponse = """{
  "status": "Error",
  "errorMessage": "No servicepoints found for the given address",
  "servicePoints": []
}"""

ParsedErrorResponse = [
    [],
    [
        {
            "carrier_id": "dhl_freight_sweden",
            "carrier_name": "dhl_freight_sweden",
            "code": "Error",
            "message": "No servicepoints found for the given address",
            "details": {},
        }
    ],
]


ParsedNonObjectResponse = [
    [],
    [
        {
            "carrier_id": "dhl_freight_sweden",
            "carrier_name": "dhl_freight_sweden",
            "code": "SHIPPING_SDK_INTERNAL_ERROR",
            "message": "Unexpected service point locator response: expected a JSON object",
        }
    ],
]


if __name__ == "__main__":
    unittest.main()
