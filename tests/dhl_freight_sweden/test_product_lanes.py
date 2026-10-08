"""DHL Freight (SE API Farm) product lanes from the manual's valid countries.

Product manual v5.26 lists each product's "Valid countries" in section 5
and classifies it as domestic or international in its overview (§5.1 p13).
The domestic products carry shipments within SE only; 109 and 112 carry
them from SE to their listed countries; 107 returns them from its listed
countries to the original sender in SE (§5.15 pp65-66); and 202, 205, 233,
SPI, and 601 are used "to and from Sweden" (§5.4 p22, §5.9 p41, §5.10 p46,
§5.11 p51, §5.19 p81), so SE in their lists is the Swedish end of a lane,
not a domestic lane.
"""

import typing
import unittest

import karrio.core.models as models
from karrio.providers.dhl_freight_sweden import units

from .fixture import gateway, members, proxy_of

Lane = typing.Tuple[str, str]

DOMESTIC = ["102", "103", "104", "118", "209", "210", "211", "212", "401", "402", "502"]

# Per product: lanes the manual allows, and lanes it excludes that the
# connector rated before this table existed.
LANES: typing.Dict[str, typing.Tuple[typing.List[Lane], typing.List[Lane]]] = {
    **{code: ([("SE", "SE")], [("PL", "SE"), ("DE", "SE")]) for code in DOMESTIC},
    "109": ([("SE", "DE"), ("SE", "NO"), ("SE", "GB")], [("DE", "PL"), ("NO", "DK")]),
    "112": ([("SE", "FR"), ("SE", "NO"), ("SE", "GB")], [("DE", "PL"), ("NO", "DK")]),
    "107": (
        [("DE", "SE"), ("NO", "SE"), ("FR", "SE")],
        [("SE", "SE"), ("CH", "SE"), ("GB", "SE"), ("US", "SE")],
    ),
    "202": (
        [("SE", "LI"), ("SE", "CH"), ("SE", "GR"), ("SE", "UA")],
        [("SE", "US"), ("SE", "IS"), ("DE", "PL")],
    ),
    "205": (
        [("SE", "LI"), ("SE", "CH"), ("SE", "MT")],
        [("SE", "US"), ("SE", "IS"), ("DE", "PL")],
    ),
    "SPI": (
        [("SE", "LI"), ("SE", "CH"), ("SE", "CY")],
        [("SE", "US"), ("SE", "IS"), ("DE", "PL")],
    ),
    "233": (
        [("SE", "LI"), ("SE", "CH"), ("SE", "GB"), ("SE", "NO")],
        [("SE", "GR"), ("SE", "CY"), ("SE", "MT"), ("SE", "UA"), ("DE", "PL")],
    ),
    "601": (
        [("SE", "CH"), ("SE", "GB"), ("SE", "GR"), ("SE", "NO")],
        [("SE", "LI"), ("SE", "CY"), ("SE", "MT"), ("SE", "UA"), ("DE", "PL")],
    ),
}

# The Swedish end of the to-and-from-Sweden products also serves imports,
# which the table allows although the rating mixin never rates them.
IMPORTS: typing.Dict[str, typing.List[Lane]] = {
    "202": [("LI", "SE"), ("UA", "SE")],
    "205": [("CH", "SE")],
    "SPI": [("GR", "SE")],
    "233": [("LI", "SE")],
    "601": [("CH", "SE")],
}

POSTAL_CODES = {
    "CH": "8001",
    "CY": "1010",
    "DE": "10115",
    "DK": "1620",
    "FR": "75004",
    "GB": "W1D 1AN",
    "GR": "10557",
    "IS": "101",
    "LI": "9490",
    "MT": "VLT 1010",
    "NO": "0154",
    "PL": "00-950",
    "SE": "11143",
    "UA": "01001",
    "US": "10001",
}


class TestDHLFreightProductLaneTable(unittest.TestCase):
    def test_every_product_has_lanes(self):
        products = {member.value for member in members(units.ShippingService)}

        self.assertEqual(set(units.PRODUCT_LANES), products)
        self.assertEqual(set(units.PRODUCT_LANE_CITATIONS), products)

    def test_allowed_and_excluded_lanes(self):
        for product, (allowed, excluded) in LANES.items():
            for origin, destination in allowed + IMPORTS.get(product, []):
                with self.subTest(product=product, lane=(origin, destination)):
                    self.assertTrue(units.lane_served(product, origin, destination))
            for origin, destination in excluded:
                with self.subTest(product=product, lane=(origin, destination)):
                    self.assertFalse(units.lane_served(product, origin, destination))

    def test_no_international_product_serves_a_domestic_lane(self):
        for product in ["107", "109", "112", "202", "205", "233", "SPI", "601"]:
            with self.subTest(product=product):
                self.assertFalse(units.lane_served(product, "SE", "SE"))

    def test_manual_country_lists(self):
        road_freight = set(
            "AD AL AM AT AZ BA BE BG CH CY CZ DE DK EE ES FI FR GB GE GI GR HR HU IE "
            "IT KG KZ LI LT LU LV MA MC MD ME MK MT NL NO PL PT RO RS SE SI SK SM TJ "
            "TR UA UZ XK".split()
        )
        priority = set(
            "AT BE BG CH CZ DE DK EE ES FI FR GB HR HU IE IT LI LT LU LV NL NO PL PT "
            "RO SE SI SK".split()
        )
        home_delivery_international = set(
            "AT BE BG CH CZ DE DK EE ES FI FR GB GR HR HU IE IT LT LU LV NL NO PL PT "
            "RO SE SI SK".split()
        )
        parcel_return = set(
            "AT BE BG CZ DE DK EE ES FI FR HR HU IE IT LT LU LV NL NO PL PT RO SI SK".split()
        )
        parcel_connect = parcel_return | {"GB"}

        self.assertEqual(set(units.ROAD_FREIGHT_COUNTRIES), road_freight)
        self.assertEqual(set(units.ROAD_FREIGHT_PRIORITY_COUNTRIES), priority)
        self.assertEqual(
            set(units.HOME_DELIVERY_INTERNATIONAL_COUNTRIES), home_delivery_international
        )
        self.assertEqual(set(units.PARCEL_RETURN_CONNECT_COUNTRIES), parcel_return)
        self.assertEqual(set(units.PARCEL_CONNECT_B2C_COUNTRIES), parcel_connect)
        self.assertEqual(set(units.PARCEL_CONNECT_PLUS_COUNTRIES), parcel_connect)


class TestDHLFreightProductLaneRating(unittest.TestCase):
    def test_rating_offers_allowed_lanes(self):
        for product, (allowed, _) in LANES.items():
            for origin, destination in allowed:
                with self.subTest(product=product, lane=(origin, destination)):
                    rates, messages = _rates(product, origin, destination)

                    self.assertEqual(
                        [rate.meta["carrier_service_code"] for rate in rates], [product]
                    )
                    self.assertEqual(messages, [])

    def test_rating_refuses_excluded_lanes(self):
        for product, (_, excluded) in LANES.items():
            for origin, destination in excluded:
                with self.subTest(product=product, lane=(origin, destination)):
                    rates, messages = _rates(product, origin, destination)

                    self.assertEqual(rates, [])
                    self.assertEqual(
                        [message.code for message in messages],
                        ["destination_not_supported"],
                    )

    def test_domestic_lane_of_an_export_product_reports_one_message(self):
        _, messages = _rates("109", "SE", "SE")

        self.assertEqual(
            [message.message for message in messages],
            ["Product 109 does not ship from SE to SE (product manual v5.26 §5.14 p63)"],
        )

    def test_unserved_lane_message_names_the_lane_and_citation(self):
        _, messages = _rates("107", "CH", "SE")

        self.assertIn(
            "Product 107 does not ship from CH to SE (product manual v5.26 §5.15 p66)",
            [message.message for message in messages],
        )

    def test_unrequested_products_on_an_unserved_lane_are_dropped_silently(self):
        rates, messages = _rates(None, "PL", "SE")

        self.assertEqual(
            [rate.meta["carrier_service_code"] for rate in rates], ["107"]
        )
        self.assertEqual(messages, [])

    def test_territory_codes_are_checked_as_their_parent_country(self):
        # Åland (AX) is rated as FI, which 109 serves.
        rates, _ = _rates("109", "SE", "AX", postal_code="22100")

        self.assertEqual([rate.meta["carrier_service_code"] for rate in rates], ["109"])


def _rates(
    product: typing.Optional[str],
    origin: str,
    destination: str,
    postal_code: typing.Optional[str] = None,
):
    # karrio.Rating.fetch rejects a shipper outside the account country, so
    # the gateway's own rate pipeline is driven directly.
    services = [units.ShippingService.map(product).name_or_key] if product else []
    request = gateway.mapper.create_rate_request(
        models.RateRequest(
            shipper=_address(origin, POSTAL_CODES[origin]),
            recipient=_address(destination, postal_code or POSTAL_CODES[destination]),
            parcels=[models.Parcel(weight=5.0, weight_unit="KG")],
            services=services,
        )
    )
    return gateway.mapper.parse_rate_response(proxy_of(gateway).get_rates(request))


def _address(country: str, postal_code: str) -> models.Address:
    return models.Address(
        company_name="Test Party",
        address_line1="Street 1",
        city="City",
        postal_code=postal_code,
        country_code=country,
    )


if __name__ == "__main__":
    unittest.main()
