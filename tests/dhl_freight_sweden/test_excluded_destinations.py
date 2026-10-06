"""DHL Freight (SE API Farm) excluded postal-code ranges per product.

Product manual v5.26 limits Parcel Connect Plus (112) delivery in FR to
mainland France and Corsica and excludes postal codes 97100-99999 (§5.3
p18). FR postal codes have five digits; a code that is not five digits
cannot be shown to lie outside the excluded range, so it is treated as
excluded.
"""

import unittest

import karrio.core.models as models
import karrio.sdk as karrio
from karrio.providers.dhl_freight_sweden import units
from karrio.providers.dhl_freight_sweden.shipment.create import (
    ExcludedDestinationError,
)

from .fixture import detail_keys, gateway, members, serialize_request
from .test_shipment import _payload, _recipient_se


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
