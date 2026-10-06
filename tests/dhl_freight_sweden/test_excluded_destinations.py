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
from .test_shipment import _payload, _recipient_se, _shipper


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
                self.assertIn(ParcelConnectService, offered)

    def test_112_does_not_rate_to_malformed_fr_postal_codes(self):
        for postal_code in ["9720", "972000", "97 2A0", "ABCDE", None]:
            with self.subTest(postal_code=postal_code):
                offered = self._offered(_fr(postal_code), [])

                self.assertNotIn(ParcelConnectPlusService, offered)

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
        for postal_code in ["9720", "ABCDE", None]:
            with self.subTest(postal_code=postal_code):
                error = self._error(_payload(ParcelConnectPlusService, _fr(postal_code)))

                self.assertEqual(detail_keys(error), {"recipient.postal_code"})
                self.assertIn("5-digit", str(error))

    def test_112_to_mainland_fr_books(self):
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**_payload(ParcelConnectPlusService, _fr("75004")))
        )

        self.assertEqual(serialize_request(request)["productCode"], "112")

    def test_other_products_to_excluded_fr_postal_codes_are_not_checked(self):
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**_payload(ParcelConnectService, _fr("97200")))
        )

        self.assertEqual(serialize_request(request)["productCode"], "109")


class ExclusionCases:
    """Booking and rating checks over a product's excluded and served postal codes."""

    product: str
    party = "recipient"
    excluded: typing.List[typing.Tuple[str, str]] = []
    served: typing.List[typing.Tuple[str, str]] = []
    malformed: typing.List[typing.Tuple[str, typing.Optional[str]]] = []

    def test_excluded_and_malformed_postal_codes_fail_at_booking(self):
        test = typing.cast(unittest.TestCase, self)
        for country, postal_code in [*self.excluded, *self.malformed]:
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
        service = units.ShippingService.map(self.product).name_or_key
        cases = [
            *((country, code, False) for country, code in [*self.excluded, *self.malformed]),
            *((country, code, True) for country, code in self.served),
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
    ]
    malformed = [
        ("DK", "38000"),
        ("ES", "3500"),
        ("IT", "4020"),
        ("NO", "815"),
        ("PT", "10001"),
        ("PT", "1000-01"),
        ("PT", None),
    ]


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
            {"dhl_freight_sweden_payer_code": _PAYER_CODES.get(product)},
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


_PAYER_CODES = {"202": "DAP", "205": "DAP", "SPI": "DAP"}
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
ParcelConnectService = "dhl_freight_sweden_parcel_connect_b2c"


if __name__ == "__main__":
    unittest.main()
