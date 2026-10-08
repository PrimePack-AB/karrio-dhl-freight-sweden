"""DHL Freight (SE API Farm) service-level seeding tests.

``DEFAULT_SERVICES`` seeds the rate-sheet catalog consumed by universal
rating (the dashboard presents these as the carrier's shippable services).
These tests keep it aligned with the ``ShippingService`` product enum and
guard the zone invariants the rating mixin depends on.
"""

import unittest

from karrio.providers.dhl_freight_sweden import units
from karrio.mappers.dhl_freight_sweden.proxy import Proxy
from karrio.references import detect_proxy_methods, get_carrier_capabilities

from .fixture import members


class TestDHLFreightServiceLevels(unittest.TestCase):
    def setUp(self):
        self.levels = {s.service_code: s for s in units.DEFAULT_SERVICES}

    def test_service_codes_prefixed_with_carrier_id(self):
        for member in members(units.ShippingService):
            self.assertTrue(
                member.name.startswith("dhl_freight_sweden_"),
                f"{member.name} breaks the carrier-id naming convention",
            )

    def test_option_codes_prefixed_with_carrier_id(self):
        unified_aliases = {"email_notification", "insurance"}
        for member in units.ShippingOption:
            self.assertTrue(
                member.name.startswith("dhl_freight_sweden_")
                or member.name in unified_aliases,
                f"{member.name} breaks the carrier-id naming convention",
            )

    def test_service_levels_cover_product_enum(self):
        self.assertEqual(
            set(self.levels.keys()),
            {member.name for member in members(units.ShippingService)},
        )

    def test_carrier_service_codes_match_enum_values(self):
        for member in members(units.ShippingService):
            self.assertEqual(
                self.levels[member.name].carrier_service_code,
                member.value,
                f"carrier_service_code mismatch for {member.name}",
            )

    def test_every_service_has_a_zone(self):
        # The universal rating mixin drops services without a matching zone,
        # so a zoneless service silently never rates.
        for code, level in self.levels.items():
            self.assertTrue(
                level.zones,
                f"{code} has no zone and would never produce a rate",
            )

    def test_zone_partition(self):
        domestic = {
            "118",
            "401",
            "402",
            "502",
            "210",
            "102",
            "212",
            "103",
            "104",
            "209",
            "211",
        }
        # Recipient footprints from product manual v5.26: 109 and 112 cover
        # the same 25 from-SE countries, GB included, which needs a separate
        # agreement (§5.3 p18, §5.14 p63); 107 is the reverse lane
        # (EU -> SE), gated on the recipient, so Sweden only; the freight
        # products list their valid countries other than SE (§5.4 p23,
        # §5.9 p43, §5.10 p47, §5.11 p52, §5.19 p82).
        europe = {
            "109": ParcelConnectB2CCountries,
            "112": ParcelConnectPlusCountries,
        }
        return_lane = {"107"}
        international = {
            "202": RoadFreightCountries,
            "205": RoadFreightCountries,
            "SPI": RoadFreightCountries,
            "233": RoadFreightPriorityCountries,
            "601": HomeDeliveryInternationalCountries,
        }

        for _, level in self.levels.items():
            code = level.carrier_service_code
            self.assertEqual(level.currency, "SEK")

            if code in domestic:
                self.assertTrue(level.domicile)
                self.assertFalse(level.international)
                self.assertEqual(
                    [c for z in level.zones for c in (z.country_codes or [])],
                    ["SE"],
                )
            elif code in europe:
                self.assertFalse(level.domicile)
                self.assertTrue(level.international)
                self.assertEqual(
                    [z.label for z in level.zones],
                    ["Europe"],
                )
                self.assertEqual(
                    [c for z in level.zones for c in (z.country_codes or [])],
                    europe[code],
                )
            elif code in return_lane:
                self.assertTrue(level.domicile)
                self.assertTrue(level.international)
                self.assertEqual(
                    [(z.label, z.country_codes) for z in level.zones],
                    [("Sweden", ["SE"])],
                )
            elif code in international:
                self.assertFalse(level.domicile)
                self.assertTrue(level.international)
                self.assertEqual(
                    [c for z in level.zones for c in (z.country_codes or [])],
                    sorted(set(international[code]) - {"SE"}),
                )
            else:  # pragma: no cover
                self.fail(f"unclassified product code: {code}")

    def test_capabilities_unchanged_by_lookup_methods(self):
        # The connector-local lookups are duck-typed proxy methods: they must
        # not register capabilities (the server derives connection
        # capabilities from this same detection path). ``validate_address``
        # maps onto the existing "shipping" capability (units.map_capability
        # routes any *address* method there), so the set is stable.
        self.assertEqual(
            set(get_carrier_capabilities("dhl_freight_sweden")),
            {"shipping", "rating"},
        )

    def test_validate_address_registered_on_proxy(self):
        self.assertIn("validate_address", detect_proxy_methods(Proxy))


# Catalog mirrors (deliberately not imported from ``units`` so a typo in
# either side fails this suite rather than propagating).
ParcelConnectB2CCountries = [
    "AT",
    "BE",
    "BG",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GB",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "NL",
    "NO",
    "PL",
    "PT",
    "RO",
    "SI",
    "SK",
]
ParcelConnectPlusCountries = [
    "AT",
    "BE",
    "BG",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GB",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "NL",
    "NO",
    "PL",
    "PT",
    "RO",
    "SI",
    "SK",
]

RoadFreightCountries = (
    "AD AL AM AT AZ BA BE BG CH CY CZ DE DK EE ES FI FR GB GE GI GR HR HU IE "
    "IT KG KZ LI LT LU LV MA MC MD ME MK MT NL NO PL PT RO RS SE SI SK SM TJ "
    "TR UA UZ XK"
).split()
RoadFreightPriorityCountries = (
    "AT BE BG CH CZ DE DK EE ES FI FR GB HR HU IE IT LI LT LU LV NL NO PL PT "
    "RO SE SI SK"
).split()
HomeDeliveryInternationalCountries = (
    "AT BE BG CH CZ DE DK EE ES FI FR GB GR HR HU IE IT LT LU LV NL NO PL PT "
    "RO SE SI SK"
).split()


if __name__ == "__main__":
    unittest.main()
