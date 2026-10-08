"""DHL Freight (SE API Farm) territory codes and their postal codes.

The connector books a territory code under its parent country
(``units.TERRITORY_PARENTS``). For the territories that lie in a postal-code
range of the parent, a missing code or one outside the range would be booked
as the parent's mainland, inside the EU VAT area, with the customs data
dropped, so booking refuses it before the lane, EU VAT area, and customs
checks. JE, GG, IM, and XI have no numeric range and are not checked.
"""

import typing
import unittest

import karrio.core.models as models
from karrio.providers.dhl_freight_sweden import units
from karrio.providers.dhl_freight_sweden.shipment.create import TerritoryPostalCodeError

from .fixture import detail_keys, gateway, serialize_request
from .test_shipment import Customs, _payload, _recipient_se, _shipper

ROAD_FREIGHT_DIRECT = "dhl_freight_sweden_road_freight_direct"


def _address(country: str, postal_code: typing.Optional[str]) -> dict:
    return {**_recipient_se, "city": "City", "country_code": country, "postal_code": postal_code}


def _book(
    recipient: dict,
    shipper: typing.Optional[dict] = None,
    service: str = ROAD_FREIGHT_DIRECT,
    payer_code: str = "DAP",
) -> dict:
    payload = {
        **_payload(service, recipient, {"dhl_freight_sweden_payer_code": payer_code}),
        "shipper": shipper or _shipper,
        "customs": Customs,
    }
    return serialize_request(gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload)))


def _consignee(serialized: dict) -> dict:
    return next(party["address"] for party in serialized["parties"] if party["type"] == "Consignee")


class TestDHLFreightTerritoryPostalCodes(unittest.TestCase):
    def test_codes_in_the_territory_range_book_under_the_parent(self):
        cases = [
            ("AX", "22100", "FI"),
            ("AX", "AX-22100", "FI"),
            ("AX", "FI 22 100", "FI"),
            ("IC", "35001", "ES"),
            ("IC", "38001", "ES"),
            ("EA", "51001", "ES"),
            ("EA", "52001", "ES"),
            ("FO", "100", "DK"),
            ("FO", "FO-100", "DK"),
            ("FO", "3800", "DK"),
            ("GL", "3900", "DK"),
            ("GL", "GL-3900", "DK"),
        ]
        for country, postal_code, parent in cases:
            with self.subTest(country=country, postal_code=postal_code):
                serialized = _book(_address(country, postal_code))

                self.assertEqual(_consignee(serialized)["countryCode"], parent)
                self.assertIn("customsInformation", serialized)

    def test_codes_outside_the_territory_range_fail(self):
        cases = [
            ("AX", "00100", "Country code AX (Åland) is booked as FI and needs an FI postal code in 22000-22999; got recipient postal code '00100'"),
            ("AX", "FI-23000", "Country code AX (Åland) is booked as FI and needs an FI postal code in 22000-22999; got recipient postal code 'FI-23000'"),
            ("IC", "28001", "Country code IC (Canary Islands) is booked as ES and needs an ES postal code in 35000-35999 or 38000-38999; got recipient postal code '28001'"),
            ("EA", "35001", "Country code EA (Ceuta and Melilla) is booked as ES and needs an ES postal code in 51000-51999 or 52000-52999; got recipient postal code '35001'"),
            ("FO", "2100", "Country code FO (Faroe Islands) is booked as DK and needs a DK postal code in 3800-3999 or of three digits; got recipient postal code '2100'"),
            ("GL", "100", "Country code GL (Greenland) is booked as DK and needs a DK postal code in 3800-3999; got recipient postal code '100'"),
            ("AX", "Mariehamn", "Country code AX (Åland) is booked as FI and needs an FI postal code in 22000-22999; got recipient postal code 'Mariehamn'"),
        ]
        for country, postal_code, message in cases:
            with self.subTest(country=country, postal_code=postal_code):
                with self.assertRaises(TerritoryPostalCodeError) as context:
                    _book(_address(country, postal_code))

                self.assertEqual(str(context.exception), message)
                self.assertEqual(detail_keys(context.exception), {"recipient.postal_code"})

    def test_missing_codes_fail(self):
        for postal_code in [None, "", " "]:
            with self.subTest(postal_code=postal_code):
                with self.assertRaises(TerritoryPostalCodeError) as context:
                    _book(_address("AX", postal_code))

                self.assertEqual(detail_keys(context.exception), {"recipient.postal_code"})
                self.assertIn("got no recipient postal code", str(context.exception))

    def test_shipper_territory_code_is_checked(self):
        with self.assertRaises(TerritoryPostalCodeError) as context:
            _book(_recipient_se, shipper=_address("AX", "00100"), payer_code="EXW")

        self.assertEqual(detail_keys(context.exception), {"shipper.postal_code"})

    def test_check_precedes_the_lane_check(self):
        # 102 serves no lane to FI, but the territory postal code fails first.
        with self.assertRaises(TerritoryPostalCodeError):
            _book(_address("AX", "00100"), service="dhl_freight_sweden_paket", payer_code="1")

    def test_territories_without_a_numeric_range_are_not_checked(self):
        for country in ["JE", "GG", "IM", "XI"]:
            with self.subTest(country=country):
                serialized = _book(_address(country, "SW1A 1AA"))

                self.assertEqual(_consignee(serialized)["countryCode"], "GB")

    def test_parent_country_codes_are_not_checked(self):
        serialized = _book(_address("FI", "00100"))

        self.assertEqual(_consignee(serialized)["countryCode"], "FI")



class TestDHLFreightTerritoryPostalCodeDescription(unittest.TestCase):
    def test_describe_names_any_digit_count(self):
        cases = [
            (3, "a DK postal code in 3800-3999 or of three digits"),
            (4, "a DK postal code in 3800-3999 or of 4 digits"),
            (None, "a DK postal code in 3800-3999"),
        ]
        for digits, description in cases:
            with self.subTest(digits=digits):
                territory = units.TerritoryPostalCodes("Test", "DK", ((3800, 3999),), digits)

                self.assertEqual(territory.describe(), description)


if __name__ == "__main__":
    unittest.main()
