"""DHL Freight (SE API Farm) excluded postal-code ranges per product.

Product manual v5.26 limits Parcel Connect Plus (112) delivery in FR to
mainland France and Corsica and excludes postal codes 97100-99999 (§5.3
p18). FR postal codes have five digits; a code that is not five digits
cannot be shown to lie outside the excluded range, so it is treated as
excluded.
"""

import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.sdk as karrio
from karrio.providers.dhl_freight_sweden import units
from karrio.providers.dhl_freight_sweden.shipment.create import (
    ExcludedDestinationError,
)

from .fixture import detail_keys, gateway, members, proxy_of, serialize_request
from .test_shipment import Customs, _payload, _recipient_se, _shipper


class TestDHLFreightPostalCodeExclusionTable(unittest.TestCase):
    def test_every_excluded_country_has_a_postal_code_format(self):
        for exclusion in units.POSTAL_CODE_EXCLUSIONS:
            with self.subTest(exclusion=exclusion):
                self.assertIn(exclusion.country, units.POSTAL_CODE_FORMATS)
                self.assertLessEqual(exclusion.low, exclusion.high)

    def test_exclusions_name_known_products_and_parties(self):
        products = {member.value for member in members(units.ShippingService)}

        for exclusion in units.POSTAL_CODE_EXCLUSIONS:
            with self.subTest(exclusion=exclusion):
                self.assertIn(exclusion.product, products)
                self.assertTrue(set(exclusion.parties) <= {"shipper", "recipient"})


    def test_pattern_exclusions_name_known_products_and_parties(self):
        products = {member.value for member in members(units.ShippingService)}

        for exclusion in units.POSTAL_CODE_PATTERN_EXCLUSIONS:
            with self.subTest(exclusion=exclusion):
                self.assertIn(exclusion.product, products)
                self.assertTrue(exclusion.patterns)
                self.assertTrue(set(exclusion.parties) <= {"shipper", "recipient"})

    def test_pattern_exclusions_do_not_repeat_a_manual_range_country(self):
        ranges = {(e.product, e.country) for e in units.POSTAL_CODE_EXCLUSIONS}

        for exclusion in units.POSTAL_CODE_PATTERN_EXCLUSIONS:
            with self.subTest(exclusion=exclusion):
                self.assertNotIn((exclusion.product, exclusion.country), ranges)


class TestDHLFreightExcludedDestinationRating(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _offered(self, recipient: dict, services: list) -> set:
        request = models.RateRequest(**_rate_payload(recipient, services))
        rates, _ = karrio.Rating.fetch(request).from_(gateway).parse()
        return {rate.service for rate in rates}

    def test_112_rates_to_mainland_fr_and_corsica(self):
        for postal_code in ["75004", "97099", "20000", "750 04"]:
            with self.subTest(postal_code=postal_code):
                offered = self._offered(_fr(postal_code), [])

                self.assertIn(ParcelConnectPlusService, offered)

    def test_112_does_not_rate_to_excluded_fr_postal_codes(self):
        for postal_code in ["97100", "97200", "98000", "99999"]:
            with self.subTest(postal_code=postal_code):
                offered = self._offered(_fr(postal_code), [])

                self.assertNotIn(ParcelConnectPlusService, offered)
                self.assertIn(RoadFreightDirectService, offered)

    def test_112_does_not_rate_to_malformed_fr_postal_codes(self):
        for postal_code in ["9720", "972000", "97 2A0", "ABCDE"]:
            with self.subTest(postal_code=postal_code):
                offered = self._offered(_fr(postal_code), [])

                self.assertNotIn(ParcelConnectPlusService, offered)

    def test_112_rates_to_fr_without_a_postal_code(self):
        for postal_code in [None, "", "  "]:
            with self.subTest(postal_code=postal_code):
                offered = self._offered(_fr(postal_code), [])

                self.assertIn(ParcelConnectPlusService, offered)

    def test_112_explicitly_requested_to_an_excluded_postal_code_reports_why(self):
        request = models.RateRequest(
            **_rate_payload(_fr("97200"), [ParcelConnectPlusService])
        )
        rates, messages = karrio.Rating.fetch(request).from_(gateway).parse()

        self.assertEqual(rates, [])
        self.assertEqual(
            [(message.code, message.details) for message in messages],
            [
                (
                    "destination_not_supported",
                    dict(
                        service=ParcelConnectPlusService,
                        party="recipient",
                        country_code="FR",
                        postal_code="97200",
                    ),
                )
            ],
        )
        self.assertIn("97100-99999", messages[0].message or "")

    def test_exclusion_is_keyed_by_country(self):
        offered = self._offered(
            {**_recipient_se, "city": "Berlin", "postal_code": "97200", "country_code": "DE"},
            [],
        )

        self.assertIn(ParcelConnectPlusService, offered)


class TestDHLFreightExcludedDestinationBooking(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _error(self, payload: dict) -> ExcludedDestinationError:
        with self.assertRaises(ExcludedDestinationError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def test_112_to_excluded_fr_postal_codes_fails(self):
        for postal_code in ["97100", "97200", "99999"]:
            with self.subTest(postal_code=postal_code):
                error = self._error(_payload(ParcelConnectPlusService, _fr(postal_code)))

                self.assertEqual(detail_keys(error), {"recipient.postal_code"})
                self.assertIn("97100-99999", str(error))

    def test_112_to_malformed_fr_postal_codes_fails(self):
        for postal_code in ["9720", "ABCDE", None, ""]:
            with self.subTest(postal_code=postal_code):
                error = self._error(_payload(ParcelConnectPlusService, _fr(postal_code)))

                self.assertEqual(detail_keys(error), {"recipient.postal_code"})
                self.assertIn("5-digit", str(error))

    def test_112_to_faroese_and_greenlandic_codes_names_the_excluded_area(self):
        for country, postal_code in [("DK", "100"), ("DK", "FO-1620"), ("FO", "100")]:
            with self.subTest(country=country, postal_code=postal_code):
                error = self._error(
                    _payload(
                        ParcelConnectPlusService,
                        {**_recipient_se, "country_code": country, "postal_code": postal_code},
                    )
                )

                self.assertIn(
                    "does not ship to DK postal codes 3800-3999 "
                    "(Greenland and the Faroe Islands)",
                    str(error),
                )
                self.assertEqual(
                    (error.details or {})["recipient.postal_code"]["code"], "invalid"
                )

    def test_112_to_mainland_fr_books(self):
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**_payload(ParcelConnectPlusService, _fr("75004")))
        )

        self.assertEqual(serialize_request(request)["productCode"], "112")

    def test_products_without_fr_ranges_are_not_checked(self):
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(
                **{
                    **_payload(
                        RoadFreightDirectService,
                        _fr("97200"),
                        {"dhl_freight_sweden_payer_code": "DAP"},
                    ),
                    "customs": Customs,
                }
            )
        )

        self.assertEqual(serialize_request(request)["productCode"], "205")


class ExclusionCases:
    """Booking and rating checks over a product's excluded and served postal codes."""

    product: str
    party = "recipient"
    excluded: typing.List[typing.Tuple[str, typing.Optional[str]]] = []
    served: typing.List[typing.Tuple[str, str]] = []
    malformed: typing.List[typing.Tuple[str, str]] = []
    # Booking rejects a missing postal code; rating still offers the product.
    missing: typing.List[typing.Tuple[str, typing.Optional[str]]] = []

    def test_excluded_and_malformed_postal_codes_fail_at_booking(self):
        test = typing.cast(unittest.TestCase, self)
        for country, postal_code in [*self.excluded, *self.malformed, *self.missing]:
            with test.subTest(country=country, postal_code=postal_code):
                with test.assertRaises(ExcludedDestinationError) as context:
                    _book(self.product, self.party, country, postal_code)

                test.assertEqual(
                    detail_keys(context.exception), {f"{self.party}.postal_code"}
                )

    def test_served_postal_codes_book(self):
        test = typing.cast(unittest.TestCase, self)
        for country, postal_code in self.served:
            with test.subTest(country=country, postal_code=postal_code):
                serialized = _book(self.product, self.party, country, postal_code)

                test.assertEqual(serialized["productCode"], self.product)

    def test_rating_offers_only_served_postal_codes(self):
        test = typing.cast(unittest.TestCase, self)
        if self.product in _FREIGHT_PRODUCTS and self.party == "shipper":
            test.skipTest(
                "the rating mixin classifies delivery into SE as domicile, so "
                "the international freight products never rate on import lanes"
            )
        service = units.ShippingService.map(self.product).name_or_key
        cases = [
            *((country, code, False) for country, code in [*self.excluded, *self.malformed]),
            *((country, code, True) for country, code in [*self.served, *self.missing]),
        ]

        for country, postal_code, offered in cases:
            with test.subTest(country=country, postal_code=postal_code):
                rates, _ = _rates(service, self.party, country, postal_code)

                test.assertEqual(service in {rate.service for rate in rates}, offered)


class TestDHLFreightParcelConnectPlusExclusions(ExclusionCases, unittest.TestCase):
    """112 excluded regions/areas, product manual v5.26 §5.3 p18."""

    product = "112"
    excluded = [
        ("DK", "3800"),
        ("DK", "3999"),
        ("ES", "35000"),
        ("ES", "35999"),
        ("ES", "38000"),
        ("ES", "38999"),
        ("ES", "51080"),
        ("ES", "52080"),
        ("IT", "22061"),
        ("IT", "23041"),
        ("IT", "23030"),
        ("IT", "47890"),
        ("IT", "47899"),
        ("IT", "04020"),
        ("IT", "04027"),
        ("IT", "25080"),
        ("IT", "28838"),
        ("IT", "58012"),
        ("NO", "8099"),
        ("NO", "9170"),
        ("NO", "9179"),
        ("PT", "9000-001"),
        ("PT", "9999-999"),
        ("PT", "9500100"),
        ("PT", "9500"),
        ("DK", "DK-3900"),
        ("PT", "PT-9000-001"),
        ("DK", "100"),
        ("DK", "FO-100"),
        ("DK", "FO-1620"),
        ("DK", "GL 3900"),
        ("FO", "100"),
        ("GL", "3900"),
    ]
    served = [
        ("DK", "3799"),
        ("DK", "4000"),
        ("ES", "28001"),
        ("ES", "51001"),
        ("IT", "00184"),
        ("IT", "47900"),
        ("NO", "0154"),
        ("NO", "9180"),
        ("PT", "1000-001"),
        ("PT", "8999-999"),
        ("DK", "DK-4000"),
        ("NO", "no-0154"),
    ]
    malformed = [
        ("DK", "38000"),
        ("ES", "3500"),
        ("IT", "4020"),
        ("NO", "815"),
        ("PT", "10001"),
        ("PT", "1000-01"),
    ]
    missing = [("PT", None), ("DK", "")]


class TestDHLFreightParcelConnectExclusions(ExclusionCases, unittest.TestCase):
    """109 excluded regions/areas, product manual v5.26 §5.14 p63."""

    product = "109"
    excluded = [
        ("DK", "970"),
        ("DK", "FO 100"),
        ("FO", "100"),
        ("DK", "3800"),
        ("DK", "3999"),
        ("ES", "35000"),
        ("ES", "38999"),
        ("ES", "51080"),
        ("ES", "52080"),
        ("FR", "97100"),
        ("FR", "99999"),
        ("IT", "00120"),
        ("IT", "22061"),
        ("IT", "23041"),
        ("IT", "47890"),
        ("IT", "47899"),
        ("NO", "8099"),
        ("NO", "9170"),
        ("NO", "9179"),
        ("PT", "9000-001"),
        ("PT", "9999-999"),
    ]
    served = [
        ("DK", "1620"),
        ("ES", "28001"),
        ("FR", "75004"),
        ("FR", "97099"),
        ("IT", "00184"),
        ("IT", "04020"),
        ("IT", "23030"),
        ("NO", "0154"),
        ("PT", "1000-001"),
    ]
    malformed = [
        ("FR", "9720"),
        ("IT", "120"),
        ("DK", "16200"),
    ]
    missing = [("FR", None), ("FR", "")]


class TestDHLFreightParcelReturnConnectExclusions(ExclusionCases, unittest.TestCase):
    """107 excluded regions/areas, product manual v5.26 §5.15 p66.

    107 returns a parcel from the listed countries to the original sender,
    and the manual's FR entry reads "Delivery only from France mainland and
    Corsica", so the ranges apply to the shipper.
    """

    product = "107"
    party = "shipper"
    excluded = [
        ("DK", "3800"),
        ("DK", "100"),
        ("DK", "GL-1234"),
        ("ES", "35500"),
        ("ES", "51080"),
        ("IT", "00120"),
        ("IT", "47895"),
        ("NO", "9171"),
        ("PT", "9500-100"),
    ]
    served = [
        ("DK", "1620"),
        ("ES", "28001"),
        ("IT", "00184"),
        ("NO", "0154"),
        ("PT", "1000-001"),
        ("FR", "97200"),
    ]
    malformed = [
        ("PT", "95001"),
    ]
    missing = [("IT", None), ("NO", "")]

    def test_recipient_postal_code_is_not_checked(self):
        serialized = _book(self.product, "recipient", "SE", "11143")

        self.assertEqual(serialized["productCode"], "107")


class CrimeaExclusionCases(ExclusionCases):
    """202 (§5.4 p23), 205 (§5.9 p43), and SPI (§5.11 p52) exclude the
    Crimea/Sebastopol region, UA postal codes starting with 95 to 99. The
    products are used to and from SE, so the range applies to both parties.
    """

    excluded = [("UA", "95000"), ("UA", "97500"), ("UA", "99999")]
    served = [("UA", "01001"), ("UA", "94999")]
    malformed = [("UA", "9500"), ("UA", "950000")]
    missing = [("UA", None), ("UA", "")]


class TestDHLFreightRoadFreightStandardToCrimea(CrimeaExclusionCases, unittest.TestCase):
    product = "202"


class TestDHLFreightRoadFreightStandardFromCrimea(CrimeaExclusionCases, unittest.TestCase):
    product = "202"
    party = "shipper"


class TestDHLFreightRoadFreightDirectToCrimea(CrimeaExclusionCases, unittest.TestCase):
    product = "205"


class TestDHLFreightRoadFreightDirectFromCrimea(CrimeaExclusionCases, unittest.TestCase):
    product = "205"
    party = "shipper"


class TestDHLFreightStandardPalletToCrimea(CrimeaExclusionCases, unittest.TestCase):
    product = "SPI"


class TestDHLFreightStandardPalletFromCrimea(CrimeaExclusionCases, unittest.TestCase):
    product = "SPI"
    party = "shipper"


class TestDHLFreightParcelConnectPlusAreaExclusions(ExclusionCases, unittest.TestCase):
    """112 excluded GB and NL areas without postal code ranges, §5.3 p18.

    GB Jersey (JE), Guernsey (GY), and Northern Ireland (BT) are matched by
    postcode prefix, also under the territory codes JE, GG, and XI, which
    are checked as GB. The NL Caribbean islands have no postal codes in the
    manual, so their own country codes are excluded whatever the code.
    """

    product = "112"
    excluded = [
        ("GB", "JE2 3AB"),
        ("GB", "je2 3ab"),
        ("GB", "GY1 1AA"),
        ("GB", "BT1 1AA"),
        ("GB", "GB-BT1 1AA"),
        ("JE", "JE2 3AB"),
        ("GG", "GY1 1AA"),
        ("XI", "BT1 1AA"),
        ("BQ", "1234"),
        ("CW", "A1"),
        ("AW", None),
        ("SX", ""),
    ]
    served = [("GB", "W1D 1AN"), ("GB", "IM1 1AA"), ("IM", "IM1 1AA")]
    missing = [("GB", None)]


class TestDHLFreightParcelConnectAreaExclusions(TestDHLFreightParcelConnectPlusAreaExclusions):
    """109 excluded GB and NL areas without postal code ranges, §5.14 p63."""

    product = "109"


class TestDHLFreightParcelReturnConnectAreaExclusions(ExclusionCases, unittest.TestCase):
    """107 excluded NL Caribbean islands, §5.15 p66, applied to the shipper."""

    product = "107"
    party = "shipper"
    excluded = [("BQ", "1234"), ("CW", None), ("AW", ""), ("SX", "A1")]


class CatalogExclusionCases(ExclusionCases):
    """Product API catalog postalCodeExcludes of a product the manual gives no
    excluded areas for, as listed in the 2026-10-06 product matches answers
    (tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-fi-00100.json).
    """

    excluded = [
        ("DK", "3900"),
        ("DK", "3999"),
        ("DK", "100"),
        ("FO", "100"),
        ("GL", "3900"),
        ("ES", "35001"),
        ("ES", "38001"),
        ("ES", "51001"),
        ("ES", "52080"),
        ("IC", "35001"),
        ("NO", "9171"),
        ("NO", "8099"),
        ("PT", "9000-001"),
        ("PT", "PT-9500-100"),
    ]
    served = [
        ("DK", "3800"),
        ("DK", "1620"),
        ("ES", "28001"),
        ("NO", "0154"),
        ("NO", "9180"),
        ("PT", "1000-001"),
        ("GB", "W1D 1AN"),
        ("GB", "BT1 1AA"),
        ("GB", "IM1 1AA"),
    ]
    missing = [("DK", None), ("NO", "")]


class TestDHLFreightRoadFreightStandardCatalogExclusions(CatalogExclusionCases, unittest.TestCase):
    product = "202"
    excluded = [
        *CatalogExclusionCases.excluded,
        ("DK", "2412"),
        ("FR", "97400"),
        ("GB", "JE2 3AB"),
        ("GB", "GY1 1AA"),
        ("JE", "JE2 3AB"),
    ]
    served = [*CatalogExclusionCases.served, ("DK", "2142"), ("FR", "75004"), ("FR", "98000")]


class TestDHLFreightRoadFreightPriorityCatalogExclusions(CatalogExclusionCases, unittest.TestCase):
    product = "233"
    excluded = [*CatalogExclusionCases.excluded, ("DK", "2412")]
    served = [*CatalogExclusionCases.served, ("FR", "97400"), ("GB", "JE2 3AB"), ("GB", "GY1 1AA")]


class TestDHLFreightHomeDeliveryInternationalCatalogExclusions(CatalogExclusionCases, unittest.TestCase):
    product = "601"
    excluded = [
        *CatalogExclusionCases.excluded,
        ("DK", "2412"),
        ("FR", "97400"),
        ("GB", "JE2 3AB"),
        ("GB", "GY1 1AA"),
    ]
    served = [*CatalogExclusionCases.served, ("DK", "2142"), ("FR", "75004")]


def _address(country: str, postal_code: typing.Optional[str]) -> dict:
    return {
        **_recipient_se,
        "city": "City",
        "postal_code": postal_code,
        "country_code": country,
    }


def _lane(party: str, country: str, postal_code: typing.Optional[str]) -> dict:
    """Shipper and recipient with ``party`` at the address and the other in SE."""
    address = _address(country, postal_code)
    return lib.identity(
        dict(shipper=_shipper, recipient=address)
        if party == "recipient"
        else dict(shipper=address, recipient=_recipient_se)
    )


def _book(product: str, party: str, country: str, postal_code: typing.Optional[str]) -> dict:
    lane = _lane(party, country, postal_code)
    outside_eu_vat_area = not all(
        units.in_eu_vat_area(address["country_code"], address["postal_code"])
        for address in lane.values()
    )
    payload = {
        **_payload(
            units.ShippingService.map(product).name_or_key,
            lane["recipient"],
            {
                "dhl_freight_sweden_payer_code": lib.identity(
                    "EXW" if party == "shipper" else "DAP"
                )
                if product in _FREIGHT_PRODUCTS
                else None
            },
        ),
        "shipper": lane["shipper"],
        **({"customs": _CUSTOMS} if outside_eu_vat_area else {}),
    }
    request = gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
    return serialize_request(request)


def _rates(service: str, party: str, country: str, postal_code: typing.Optional[str]):
    # karrio.Rating.fetch rejects a shipper outside the account country, so
    # the gateway's own rate pipeline is driven directly.
    request = gateway.mapper.create_rate_request(
        models.RateRequest(
            **{**_rate_payload(_recipient_se, [service]), **_lane(party, country, postal_code)}
        )
    )
    return gateway.mapper.parse_rate_response(proxy_of(gateway).get_rates(request))


_FREIGHT_PRODUCTS = ("202", "205", "233", "SPI", "601")
_CUSTOMS = {
    "commodities": [
        {
            "description": "Cotton T-shirt",
            "quantity": 1,
            "weight": 0.5,
            "value_amount": 20.0,
            "value_currency": "EUR",
            "origin_country": "SE",
            "hs_code": "610910",
        }
    ],
    "incoterm": "DAP",
    "invoice": "INV-2026-001",
    "commercial_invoice": True,
}


def _fr(postal_code) -> dict:
    return {
        **_recipient_se,
        "company_name": "Test Recipient SARL",
        "city": "Paris",
        "postal_code": postal_code,
        "country_code": "FR",
    }


def _rate_payload(recipient: dict, services: list) -> dict:
    return {
        "shipper": {**_recipient_se, "city": "Stockholm", "postal_code": "11143"},
        "recipient": recipient,
        "parcels": [{"weight": 5.0, "weight_unit": "KG"}],
        "services": services,
        "options": {},
    }


ParcelConnectPlusService = "dhl_freight_sweden_parcel_connect_plus"
RoadFreightStandardService = "dhl_freight_sweden_road_freight_standard"
RoadFreightDirectService = "dhl_freight_sweden_road_freight_direct"


if __name__ == "__main__":
    unittest.main()
