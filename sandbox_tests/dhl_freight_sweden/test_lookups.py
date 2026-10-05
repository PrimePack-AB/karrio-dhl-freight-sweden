"""Sandbox segment ``lookups``: PostalCode, product matches, service points.

No call in this segment books a shipment.
"""

import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio
import karrio.providers.dhl_freight_sweden.product_matches as product_matches
import karrio.providers.dhl_freight_sweden.service_points as service_points
from . import harness

SE_ADDRESS = {
    "street": "Kungsgatan 1",
    "city": "Stockholm",
    "postal_code": "11143",
    "country_code": "SE",
}
PL_ADDRESS = {
    "street": "Nowogrodzka 31",
    "city": "Warszawa",
    "postal_code": "00-251",
    "country_code": "PL",
}
PARCEL = {
    "weight": 2.5,
    "weight_unit": "KG",
    "length": 40,
    "width": 30,
    "height": 15,
    "dimension_unit": "CM",
}
OVERSIZED_PARCEL = {
    "weight": 500,
    "weight_unit": "KG",
    "length": 300,
    "width": 200,
    "height": 200,
    "dimension_unit": "CM",
}


class TestSandboxLookups(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment("lookups")
        cls.gateway = cls.session.gateway()

    def setUp(self):
        self.maxDiff = None

    def validate(self, label: str, postal_code: str, options: dict = {}):
        try:
            details, messages = karrio.Address.validate(
                dict(
                    address=dict(postal_code=postal_code, country_code="SE"),
                    options=options,
                )
            ).from_(self.gateway).parse()
        finally:
            self.session.capture(self.gateway, label)
        self.session.capture_parsed(
            label,
            dict(details=lib.to_dict(details), messages=lib.to_dict(messages)),
        )
        return details, messages

    def match(self, label: str, recipient: dict):
        request = product_matches.product_matches_request(
            dict(
                shipper=dict(postal_code="11143", country_code="SE"),
                recipient=recipient,
                parcels=[PARCEL],
            ),
            harness.settings_of(self.gateway),
        )
        try:
            products, messages = product_matches.parse_product_matches_response(
                harness.proxy_of(self.gateway).find_product_matches(request),
                harness.settings_of(self.gateway),
            )
        finally:
            self.session.capture(self.gateway, label)
        self.session.capture_parsed(
            label,
            dict(
                codes=[product.get("code") for product in products],
                messages=lib.to_dict(messages),
            ),
        )
        return products, messages

    def nearest(self, label: str, payload: dict):
        request = service_points.service_points_request(payload, harness.settings_of(self.gateway))
        try:
            points, messages = service_points.parse_service_points_response(
                harness.proxy_of(self.gateway).find_service_points(request),
                harness.settings_of(self.gateway),
            )
        finally:
            self.session.capture(self.gateway, label)
        self.session.capture_parsed(
            label,
            dict(points=points, messages=lib.to_dict(messages)),
        )
        return points, messages

    def test_postal_code_route_se(self):
        details, messages = self.validate("postal-code-se-11143", "11143")

        self.assertEqual(lib.to_dict(messages), [])
        assert isinstance(details, models.AddressValidationDetails)
        self.assertTrue(details.success)
        self.assertTrue(details.complete_address and details.complete_address.city)

    def test_postal_code_route_home_delivery_118(self):
        details, messages = self.validate(
            "postal-code-se-11151-118", "11151", dict(service="118")
        )

        self.assertEqual(lib.to_dict(messages), [])
        assert isinstance(details, models.AddressValidationDetails)
        self.assertTrue(details.success)

    def test_postal_code_route_invalid(self):
        details, messages = self.validate("postal-code-se-99999", "99999")

        self.assertFalse(details and details.success)
        self.assertTrue(messages)

    def test_product_matches_se_to_se(self):
        products, messages = self.match(
            "product-matches-se-se", dict(postal_code="41101", country_code="SE")
        )

        self.assertEqual(lib.to_dict(messages), [])
        self.assertIn("102", [product.get("code") for product in products])

    def test_product_matches_se_to_pl(self):
        products, messages = self.match(
            "product-matches-se-pl", dict(postal_code="00-251", country_code="PL")
        )

        self.assertEqual(lib.to_dict(messages), [])
        self.assertIn("109", [product.get("code") for product in products])

    def test_service_points_se(self):
        points, messages = self.nearest(
            "service-points-se", dict(address=SE_ADDRESS, max_items=5)
        )

        self.assertEqual(lib.to_dict(messages), [])
        self.assertTrue(points)
        for point in points:
            self.assertTrue(point.get("service_point_id"))
            self.assertEqual(point["address"]["country_code"], "SE")

    def test_service_points_pl(self):
        points, messages = self.nearest(
            "service-points-pl", dict(address=PL_ADDRESS, max_items=5)
        )

        self.assertEqual(lib.to_dict(messages), [])
        self.assertTrue(points)
        for point in points:
            self.assertTrue(point.get("service_point_id"))
            self.assertEqual(point["address"]["country_code"], "PL")

    def test_service_points_parcel_capacity(self):
        """An oversized parcel empties the PL result with an in-band 400.

        The SE sandbox returned the same points for both parcels on
        2026-10-05, so the capacity filter is exercised against PL.
        """
        fitting, fitting_messages = self.nearest(
            "service-points-pl-parcel",
            dict(address=PL_ADDRESS, max_items=10, parcel=PARCEL),
        )
        oversized, oversized_messages = self.nearest(
            "service-points-pl-oversized",
            dict(address=PL_ADDRESS, max_items=10, parcel=OVERSIZED_PARCEL),
        )

        self.assertEqual(lib.to_dict(fitting_messages), [])
        self.assertTrue(fitting)
        self.assertEqual(oversized, [])
        self.assertIn(
            "dimensions are too large",
            " ".join(str(message.message) for message in oversized_messages),
        )

    def test_service_points_location_types(self):
        points, messages = self.nearest(
            "service-points-pl-locker",
            dict(address=PL_ADDRESS, max_items=5, location_types=["locker"]),
        )

        self.assertEqual(lib.to_dict(messages), [])
        self.assertTrue(points)
        self.assertEqual({point.get("type") for point in points}, {"locker"})
