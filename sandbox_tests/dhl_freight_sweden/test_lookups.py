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
SMALL_PARCEL = {
    "weight": 2,
    "weight_unit": "KG",
    "length": 30,
    "width": 20,
    "height": 15,
    "dimension_unit": "CM",
}
HEAVY_PARCEL = {**SMALL_PARCEL, "weight": 20}
CH_ADDRESS = {
    "street": "Bahnhofstrasse 1",
    "city": "Zürich",
    "postal_code": "8001",
    "country_code": "CH",
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

    def validate(
        self, label: str, postal_code: str, options: dict = {}, country_code: str = "SE"
    ):
        try:
            details, messages = karrio.Address.validate(
                dict(
                    address=dict(postal_code=postal_code, country_code=country_code),
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

    def match(self, label: str, recipient: dict, parcel: dict = PARCEL):
        request = product_matches.product_matches_request(
            dict(
                shipper=dict(postal_code="11143", country_code="SE"),
                recipient=recipient,
                parcels=[parcel],
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

        self.assertIsNone(details)
        self.assertIn("16010", [message.code for message in messages])

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

    def territory(self, country_code: str, postal_code: str):
        """Record the products matched to a special territory, whatever they are.

        The recipient is sent with the country code and postal code as given,
        so the capture shows how DHL answers a territory code (AX, JE, GG,
        FO) and a territory postal code under its parent country. An empty
        match list is an answer, not a failure.
        """
        label = f"product-matches-se-{country_code.lower()}-{postal_code.lower().replace(' ', '')}"
        _, messages = self.match(
            label, dict(postal_code=postal_code, country_code=country_code)
        )

        self.assertEqual(lib.to_dict(messages), [])

    def test_product_matches_territory_fi_22100(self):
        self.territory("FI", "22100")

    def test_product_matches_territory_ax_22100(self):
        self.territory("AX", "22100")

    def test_product_matches_territory_fi_00100(self):
        self.territory("FI", "00100")

    def test_product_matches_territory_gb_je2_3ab(self):
        self.territory("GB", "JE2 3AB")

    def test_product_matches_territory_gb_gy1_1aa(self):
        self.territory("GB", "GY1 1AA")

    def test_product_matches_territory_gb_bt1_1aa(self):
        self.territory("GB", "BT1 1AA")

    def test_product_matches_territory_gb_im1_1aa(self):
        self.territory("GB", "IM1 1AA")

    def test_product_matches_territory_gb_w1d_1an(self):
        self.territory("GB", "W1D 1AN")

    def test_product_matches_territory_je_je2_3ab(self):
        self.territory("JE", "JE2 3AB")

    def test_product_matches_territory_gg_gy1_1aa(self):
        self.territory("GG", "GY1 1AA")

    def test_product_matches_territory_dk_3900(self):
        self.territory("DK", "3900")

    def test_product_matches_territory_fo_100(self):
        self.territory("FO", "100")

    def test_product_matches_territory_es_35001(self):
        self.territory("ES", "35001")

    def swiss_customs_area(
        self, country_code: str, postal_code: str, parcel: dict = SMALL_PARCEL, suffix: str = ""
    ):
        """Record the products matched from SE to the Swiss customs area, whatever they are.

        CH and LI lie outside the EU VAT area, and the connector offers
        neither 109, 112, nor 107 there, so the capture shows which products
        DHL matches for a consumer parcel. An empty match list is an answer,
        not a failure.
        """
        label = f"product-matches-se-{country_code.lower()}-{postal_code}{suffix}"
        _, messages = self.match(
            label, dict(postal_code=postal_code, country_code=country_code), parcel
        )

        self.assertEqual(lib.to_dict(messages), [])

    def test_product_matches_ch_8001(self):
        self.swiss_customs_area("CH", "8001")

    def test_product_matches_ch_1201(self):
        self.swiss_customs_area("CH", "1201")

    def test_product_matches_ch_3011(self):
        self.swiss_customs_area("CH", "3011")

    def test_product_matches_ch_6900(self):
        self.swiss_customs_area("CH", "6900")

    def test_product_matches_ch_8001_20kg(self):
        self.swiss_customs_area("CH", "8001", HEAVY_PARCEL, "-20kg")

    def test_product_matches_li_9490(self):
        self.swiss_customs_area("LI", "9490")

    def test_postal_code_route_ch_8001(self):
        details, messages = self.validate("postal-code-ch-8001", "8001", country_code="CH")

        self.assertIsNone(details)
        self.assertIn("16009", [message.code for message in messages])

    def test_service_points_ch(self):
        """Record the service points near Zürich; an empty list is an answer."""
        self.nearest(
            "service-points-ch", dict(address=CH_ADDRESS, max_items=5, parcel=SMALL_PARCEL)
        )

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

        The SE sandbox returned the same points for both parcels
        (tests/dhl_freight_sweden/fixtures/sandbox/
        lookup-service-points-se-capacity-not-applied.json), so the capacity
        filter is exercised against PL.
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
