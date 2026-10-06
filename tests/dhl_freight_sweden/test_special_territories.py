"""DHL Freight (SE API Farm) special territories under their own country codes.

Product matches answered no product for AX 22100, JE JE2 3AB, GG GY1 1AA,
and FO 100, while FI 22100 and GB JE2 3AB matched products
(tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ax-22100.json,
lookup-product-matches-se-fi-22100.json, lookup-product-matches-se-je-je23ab.json,
lookup-product-matches-se-gb-je23ab.json), so territory codes are sent and
checked as their parent country, with the postal code kept as given.
"""

import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
from karrio.providers.dhl_freight_sweden import product_matches, service_points, units

from karrio.providers.dhl_freight_sweden.shipment.create import AlandCustomsServiceError

from .fixture import as_dict, detail_keys, gateway, proxy_of, serialize_request, settings_of
from .test_shipment import Customs, _payload, _recipient_se

PARENTS = {
    "AX": "FI",
    "JE": "GB",
    "GG": "GB",
    "IM": "GB",
    "FO": "DK",
    "GL": "DK",
    "IC": "ES",
    "EA": "ES",
    "XI": "GB",
}
ROAD_FREIGHT_DIRECT = "dhl_freight_sweden_road_freight_direct"


def _recipient(country: str, postal_code: typing.Optional[str]) -> dict:
    return {**_recipient_se, "city": "City", "country_code": country, "postal_code": postal_code}


def _booked(service: str, recipient: dict, customs: typing.Optional[dict] = None) -> dict:
    payload = {
        **_payload(service, recipient, {"dhl_freight_sweden_payer_code": "DAP"}),
        **({"customs": customs} if customs else {}),
    }
    return serialize_request(
        gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
    )


def _consignee(serialized: dict) -> dict:
    return next(
        party["address"] for party in serialized["parties"] if party["type"] == "Consignee"
    )


def _rate_payload(recipient: dict) -> dict:
    return dict(
        shipper={**_recipient_se, "city": "Stockholm", "postal_code": "11143"},
        recipient=recipient,
        parcels=[{"weight": 1.0, "weight_unit": "KG"}],
        services=[],
    )


def _rated(recipient: dict) -> typing.Set[str]:
    request = gateway.mapper.create_rate_request(
        models.RateRequest(**_rate_payload(recipient))
    )
    rates, _ = gateway.mapper.parse_rate_response(proxy_of(gateway).get_rates(request))
    return {units.ShippingService.map(rate.service).value_or_key for rate in rates}


class TestDHLFreightTerritoryParents(unittest.TestCase):
    def test_territory_codes_name_their_parent_country(self):
        self.assertEqual(units.TERRITORY_PARENTS, PARENTS)
        for territory, parent in PARENTS.items():
            with self.subTest(territory=territory):
                self.assertEqual(units.parent_country(territory), parent)
                self.assertEqual(units.parent_country(territory.lower()), parent)

    def test_other_country_codes_pass_through(self):
        for country in ["SE", "FI", "GB", "NL", "BQ", "CW", "AW", "SX", None]:
            with self.subTest(country=country):
                self.assertEqual(units.parent_country(country), country)


class TestDHLFreightTerritoryBooking(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_consignee_is_sent_under_the_parent_country(self):
        cases = [
            ("AX", "22100", True),
            ("AX", "AX-22100", True),
            ("JE", "JE2 3AB", True),
            ("GG", "GY1 1AA", True),
            ("IM", "IM1 1AA", True),
            ("GL", "3900", True),
            ("IC", "35001", True),
            ("EA", "51001", True),
            ("XI", "BT1 1AA", False),
        ]

        for territory, postal_code, keeps_customs in cases:
            with self.subTest(territory=territory, postal_code=postal_code):
                serialized = _booked(
                    ROAD_FREIGHT_DIRECT, _recipient(territory, postal_code), Customs
                )

                self.assertEqual(
                    _consignee(serialized),
                    {**_consignee(serialized), "countryCode": PARENTS[territory], "postalCode": postal_code},
                )
                self.assertEqual("customsInformation" in serialized, keeps_customs)

    def test_faroe_islands_are_sent_as_dk_with_customs(self):
        for postal_code in ["100", "FO-100"]:
            with self.subTest(postal_code=postal_code):
                serialized = _booked(
                    ROAD_FREIGHT_DIRECT, _recipient("FO", postal_code), Customs
                )

                self.assertEqual(_consignee(serialized)["countryCode"], "DK")
                self.assertEqual(_consignee(serialized)["postalCode"], postal_code)
                self.assertIn("customsInformation", serialized)

    def test_caribbean_netherlands_codes_pass_through_on_freight_products(self):
        for country in ["BQ", "CW", "AW", "SX"]:
            with self.subTest(country=country):
                serialized = _booked(ROAD_FREIGHT_DIRECT, _recipient(country, "1234"), Customs)

                self.assertEqual(_consignee(serialized)["countryCode"], country)


class TestDHLFreightAlandCustomsServices(unittest.TestCase):
    """DHL rejected customs handling full service and standard for SE to FI 22100
    with 24003 (tests/dhl_freight_sweden/fixtures/sandbox/
    rejection-24003-112-se-fi-aland.json, rejection-24003-112-se-fi-aland-standard.json).
    """

    SERVICES = {
        "dhl_freight_sweden_customs_handling_full_service": "customsHandlingFullService",
        "dhl_freight_sweden_customs_handling_standard": "customsHandlingStandard",
    }

    def _payload(self, recipient: dict, options: dict, shipper: typing.Optional[dict] = None) -> dict:
        payload = {
            **_payload(ROAD_FREIGHT_DIRECT, recipient, {"dhl_freight_sweden_payer_code": "DAP", **options}),
            "customs": {**Customs, "options": {"eori_number": "SE0000000000"}},
        }
        return {**payload, **({"shipper": shipper} if shipper else {})}

    def test_customs_handling_services_to_aland_fail_before_booking(self):
        for country, postal_code in [("FI", "22100"), ("AX", "22100"), ("FI", "FI-22100"), ("AX", "AX-22999"), ("FI", "22000")]:
            for option, service in self.SERVICES.items():
                with self.subTest(country=country, postal_code=postal_code, option=option):
                    with self.assertRaises(AlandCustomsServiceError) as context:
                        gateway.mapper.create_shipment_request(
                            models.ShipmentRequest(
                                **self._payload(_recipient(country, postal_code), {option: True})
                            )
                        )

                    self.assertEqual(detail_keys(context.exception), {option})
                    self.assertIn("24003", str(context.exception))
                    self.assertIn(f"{option} ({service})", str(context.exception))
                    self.assertIn("rejection-24003-112-se-fi-aland.json", str(context.exception))
                    self.assertIn(
                        "rejection-24003-112-se-fi-aland-standard.json", str(context.exception)
                    )

    def test_customs_handling_services_from_aland_fail_before_booking(self):
        with self.assertRaises(AlandCustomsServiceError):
            gateway.mapper.create_shipment_request(
                models.ShipmentRequest(
                    **self._payload(
                        _recipient("NO", "0154"),
                        {"dhl_freight_sweden_customs_handling_standard": True},
                        shipper=_recipient("AX", "22100"),
                    )
                )
            )

    def test_aland_without_customs_services_books(self):
        serialized = serialize_request(
            gateway.mapper.create_shipment_request(
                models.ShipmentRequest(**self._payload(_recipient("AX", "22100"), {}))
            )
        )

        self.assertIn("customsInformation", serialized)
        self.assertNotIn("customsHandlingStandard", serialized.get("additionalServices") or {})

    def test_customs_handling_services_outside_aland_book(self):
        for country, postal_code in [("FI", "21999"), ("FI", "23000"), ("NO", "0154")]:
            with self.subTest(country=country, postal_code=postal_code):
                serialized = serialize_request(
                    gateway.mapper.create_shipment_request(
                        models.ShipmentRequest(
                            **self._payload(
                                _recipient(country, postal_code),
                                {"dhl_freight_sweden_customs_handling_full_service": True},
                            )
                        )
                    )
                )

                self.assertEqual(
                    "customsHandlingFullService" in (serialized.get("additionalServices") or {}),
                    country == "NO",
                )

    def test_rating_to_aland_is_unaffected(self):
        self.assertTrue({"109", "112"} <= _rated(_recipient("AX", "22100")))


class TestDHLFreightTerritoryRating(unittest.TestCase):
    def test_aland_rates_as_finland(self):
        offered = _rated(_recipient("AX", "22100"))

        self.assertTrue({"109", "112", "202"} <= offered)

    def test_jersey_rates_freight_as_gb(self):
        self.assertIn("233", _rated(_recipient("JE", "JE2 3AB")))


class TestDHLFreightTerritoryProductMatches(unittest.TestCase):
    def test_territory_recipient_is_matched_under_its_parent(self):
        request = product_matches.product_matches_request(
            dict(
                shipper=dict(postal_code="11143", country_code="SE"),
                recipient=dict(postal_code="22100", country_code="AX"),
            ),
            settings_of(gateway),
        )

        consignee = as_dict(lib.to_dict(request.serialize()))["parties"][1]["address"]
        self.assertEqual(consignee, {"countryCode": "FI", "postalCode": "22100"})



class TestDHLFreightTerritoryServicePoints(unittest.TestCase):
    def test_territory_address_is_looked_up_under_its_parent(self):
        for territory, postal_code in [("AX", "22100"), ("JE", "JE2 3AB"), ("FO", "100")]:
            with self.subTest(territory=territory):
                request = service_points.service_points_request(
                    dict(
                        address=dict(
                            city="City", postal_code=postal_code, country_code=territory
                        )
                    ),
                    settings_of(gateway),
                )

                address = as_dict(lib.to_dict(request.serialize()))["address"]
                self.assertEqual(address["countryCode"], PARENTS[territory])
                self.assertEqual(address["postalCode"], postal_code)

    def test_other_country_codes_are_looked_up_as_given(self):
        request = service_points.service_points_request(
            dict(address=dict(city="Kralendijk", postal_code="1234", country_code="BQ")),
            settings_of(gateway),
        )

        address = as_dict(lib.to_dict(request.serialize()))["address"]
        self.assertEqual(address["countryCode"], "BQ")


if __name__ == "__main__":
    unittest.main()
