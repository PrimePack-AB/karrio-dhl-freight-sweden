"""Sandbox segment ``lookups``: PostalCode, product matches, service points.

No call in this segment books a shipment.
"""

import typing
import unittest
import unittest.mock
import urllib.parse

import karrio.core.models as models
import karrio.core.utils.helpers as helpers
import karrio.lib as lib
import karrio.sdk as karrio
import karrio.providers.dhl_freight_sweden.address as provider_address
import karrio.providers.dhl_freight_sweden.product_matches as product_matches
import karrio.providers.dhl_freight_sweden.service_points as service_points
from . import booking, harness

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
# A client key no DHL application holds. The all-zeros UUID is not used:
# the sandbox accepts it.
FAKE_CLIENT_KEY = "not-a-real-key"
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
        self,
        label: str,
        postal_code: str,
        options: dict = {},
        country_code: str = "SE",
        gateway=None,
    ):
        gateway = gateway or self.gateway
        try:
            details, messages = karrio.Address.validate(
                dict(
                    address=dict(postal_code=postal_code, country_code=country_code),
                    options=options,
                )
            ).from_(gateway).parse()
        finally:
            self.session.capture(gateway, label)
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
        assert details.complete_address is not None
        self.assertEqual(
            (
                details.complete_address.city,
                details.complete_address.postal_code,
                details.complete_address.country_code,
            ),
            ("STOCKHOLM", "11151", "SE"),
        )

    def test_postal_code_route_kiruna_bookable_without_home_delivery(self):
        """Kiruna 98138 is bookable, but its homeDeliveryParcel flag is false.

        The unscoped lookup reports ``bookable`` and the 118-scoped lookup
        reports ``homeDeliveryParcel``, so the same route answers both ways.
        """
        unscoped, unscoped_messages = self.validate("postal-code-se-98138", "98138")
        scoped, scoped_messages = self.validate(
            "postal-code-se-98138-118", "98138", dict(service="118")
        )

        self.assertEqual(lib.to_dict(unscoped_messages), [])
        self.assertEqual(lib.to_dict(scoped_messages), [])
        assert isinstance(unscoped, models.AddressValidationDetails)
        assert isinstance(scoped, models.AddressValidationDetails)
        self.assertTrue(unscoped.success)
        self.assertFalse(scoped.success)
        assert scoped.complete_address is not None
        self.assertEqual(scoped.complete_address.city, "KIRUNA")

    def test_postal_code_route_invalid(self):
        details, messages = self.validate("postal-code-se-99999", "99999")

        self.assertIsNone(details)
        self.assertIn("16010", [message.code for message in messages])

    def test_postal_code_route_not_supported(self):
        """A known SE code DHL does not serve answers 16012."""
        details, messages = self.validate("postal-code-se-98060", "98060")

        self.assertIsNone(details)
        self.assertIn("16012", [message.code for message in messages])

    def test_postal_code_route_rural_not_supported(self):
        """A rural (Landsbygd) SE code DHL does not serve answers 16011."""
        details, messages = self.validate("postal-code-se-84094", "84094")

        self.assertIsNone(details)
        self.assertIn("16011", [message.code for message in messages])

    def test_postal_code_route_without_api_access(self):
        """A client key without PostalCode API access leaves the location unverified.

        The sandbox answers an unknown key with 401; how it answers the key
        of an application without the PostalCode API is not captured.
        """
        details, messages = self.validate(
            "postal-code-se-11151-118-fake-key",
            "11151",
            dict(service="118"),
            gateway=self.session.gateway(client_key=FAKE_CLIENT_KEY),
        )

        self.assertIsNone(details)
        self.assertEqual(
            [message.code for message in messages], ["postal_code_api_unavailable"]
        )

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


class TestSandboxPreflight(unittest.TestCase):
    """The ``enforce`` pre-flight refuses a 118 booking before it is sent.

    Each case looks up the route only; a booking call raises inside the
    test, on top of the harness budget guard, so no shipment is booked.
    """

    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment("lookups")
        if not cls.session.config.account_number:
            raise unittest.SkipTest("KARRIO_DHL_FREIGHT_SWEDEN_ACCOUNT_NUMBER is not set")
        cls.gateway = cls.session.gateway(dict(address_validation="enforce"))

    def refuse(
        self,
        label: str,
        postal_code: str,
        city: str,
        gateway=None,
        error: typing.Type[Exception] = provider_address.PostalCodeNotServableError,
    ) -> str:
        gateway = gateway or self.gateway
        payload: dict = dict(
            service="118",
            shipper=booking.SHIPPER,
            recipient={**booking.RECIPIENTS["SE"], "postal_code": postal_code, "city": city},
            parcels=[booking.PARCEL],
        )
        request = gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        urlopen = helpers.urlopen
        paths: list = []

        def no_booking(call, *args, **kwargs):
            url = call.full_url if hasattr(call, "full_url") else str(call)
            path = urllib.parse.urlparse(url).path
            paths.append(path)
            if path.endswith(harness.BOOKING_PATH):
                raise AssertionError("the pre-flight let a booking call through")
            return urlopen(call, *args, **kwargs)

        try:
            with unittest.mock.patch.object(helpers, "urlopen", no_booking):
                with self.assertRaises(error) as raised:
                    harness.proxy_of(gateway).create_shipment(request)
        finally:
            self.session.capture(gateway, label)
        self.session.capture_parsed(
            label, dict(error=str(raised.exception), paths=paths)
        )

        self.assertEqual(
            paths, [f"/postalcodeapi/v1/postalcodes/SE/{postal_code}/route"]
        )
        return str(raised.exception)

    def test_enforce_refuses_unknown_postal_code(self):
        message = self.refuse("preflight-118-se-99999", "99999", "Stockholm")

        self.assertIn("99999", message)

    def test_enforce_refuses_without_home_delivery(self):
        message = self.refuse("preflight-118-se-98138", "98138", "Kiruna")

        self.assertIn("homeDeliveryParcel is false", message)

    def test_enforce_refuses_without_api_access(self):
        message = self.refuse(
            "preflight-118-se-11151-fake-key",
            "11151",
            "Stockholm",
            gateway=self.session.gateway(
                dict(address_validation="enforce"), client_key=FAKE_CLIENT_KEY
            ),
            error=provider_address.PostalCodeApiUnavailableError,
        )

        self.assertIn("PostalCode API not available", message)
