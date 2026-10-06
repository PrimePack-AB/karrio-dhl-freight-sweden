"""DHL Freight (SE API Farm) EU VAT area classification tests."""

import unittest

from karrio.providers.dhl_freight_sweden import units


class TestDHLFreightEUVATArea(unittest.TestCase):
    def test_in_eu_vat_area(self):
        cases = [
            ("SE", "11143", True),
            ("PL", "00-001", True),
            ("GR", "10552", True),
            ("EL", "10552", True),
            ("DE", "10115", True),
            ("DE", "78266", False),
            ("DE", "27498", False),
            ("IT", "23041", False),
            ("IT", "22061", False),
            ("IT", "00100", True),
            ("FI", "22100", False),
            ("FI", "22 100", False),
            ("FI", "00100", True),
            ("AX", "22100", False),
            ("ES", "35001", False),
            ("ES", "38001", False),
            ("ES", "51001", False),
            ("ES", "52001", False),
            ("ES", "28001", True),
            ("IC", "35001", False),
            ("GP", "97110", False),
            ("GF", "97300", False),
            ("MQ", "97200", False),
            ("RE", "97400", False),
            ("YT", "97600", False),
            ("NO", "0154", False),
            ("GB", "SW1A 1AA", False),
            ("GB", "BT1 1AA", True),
            ("GB", "bt1 1aa", True),
            ("GB", "EC1A 1BB", False),
            ("MC", "98000", True),
            ("FR", "98000", True),
            ("FR", "75004", True),
            ("FR", "96999", True),
            ("FR", "97000", False),
            ("FR", "97110", False),
            ("FR", "97400", False),
            ("FR", "97999", False),
            ("DK", "1620", True),
            ("DK", "3799", True),
            ("DK", "3800", False),
            ("DK", "3900", False),
            ("DK", "3999", False),
            ("DK", "4000", True),
            ("FI", "FI-22100", False),
            ("FI", "fi-22100", False),
            ("FI", "FI-00100", True),
            ("DK", "DK-3900", False),
            ("DK", "DK-1620", True),
            ("ES", "ES-35001", False),
            ("FR", "FR-97200", False),
            ("GB", "GB-BT1 1AA", True),
            ("SE", "SE-111 43", True),
            ("FR", "98600", False),
            ("FR", "98899", False),
            ("FR", "98900", True),
            ("EL", "63086", False),
            ("EL", "630 86", False),
            ("EL", "10552", True),
            ("FI", "fi 22100", False),
            ("FI", "FI22100", False),
            ("FI", "FI 22 100", False),
            ("FI", "AX-22100", False),
            ("FI", " FI-22100 ", False),
            ("DK", "DK 3800", False),
            ("DK", "GL 3900", False),
            ("GB", "JE2 3AB", False),
            ("MT", "MTF 1234", True),
            ("GR", "630 86", False),
            ("CH", "8001", False),
            (None, None, False),
        ]

        for country_code, postal_code, expected in cases:
            with self.subTest(country_code=country_code, postal_code=postal_code):
                self.assertEqual(
                    units.in_eu_vat_area(country_code, postal_code), expected
                )

    def test_tables_match_nordic_conventions(self):
        self.assertEqual(
            units.NON_EU_VAT_POSTAL_RANGES,
            (
                ("FI", 22000, 22999),
                ("ES", 35000, 35999),
                ("ES", 38000, 38999),
                ("ES", 51000, 51999),
                ("ES", 52000, 52999),
                ("DE", 78266, 78266),
                ("DE", 27498, 27498),
                ("GR", 63086, 63086),
                ("IT", 23041, 23041),
                ("IT", 22061, 22061),
                ("FR", 97000, 97999),
                ("DK", 3800, 3999),
                ("FR", 98600, 98899),
                ("EL", 63086, 63086),
            ),
        )
        self.assertEqual(units.EU_VAT_POSTAL_PREFIXES, (("GB", "BT"),))
        self.assertEqual(
            units.NUMERIC_POSTAL_TERRITORY_PARENTS,
            {"AX": "FI", "FO": "DK", "GL": "DK", "IC": "ES", "EA": "ES"},
        )
        self.assertEqual(units.UK_POSTCODE_AREA_CODES, frozenset({"JE", "GY", "IM", "BT"}))


class TestDHLFreightPostalCodeNormalisation(unittest.TestCase):
    """The postcode rule shared with nordic_conventions territories.py."""

    def test_normalized_postal_code(self):
        cases = [
            ("FI", "FI-22100", "22100"),
            ("FI", "fi 22100", "22100"),
            ("FI", "FI22100", "22100"),
            ("FI", "FI 22 100", "22100"),
            ("FI", "AX-22100", "22100"),
            ("FI", "  22100 ", "22100"),
            ("DK", "DK 3800", "3800"),
            ("DK", "FO 100", "100"),
            ("DK", "GL-3900", "3900"),
            ("ES", "IC 35001", "35001"),
            ("ES", "EA51001", "51001"),
            ("PT", "PT-9000-001", "9000-001"),
            ("SE", "SE-111 43", "11143"),
            ("GB", "GB-BT1 1AA", "BT11AA"),
            ("GB", "GB BT1 1AA", "BT11AA"),
            ("GB", "BT1 1AA", "BT11AA"),
            ("GB", "JE2 3AB", "JE23AB"),
            ("GB", "GY1 1AA", "GY11AA"),
            ("GB", "IM1 1AA", "IM11AA"),
            ("GB", "GB1 2AB", "GB12AB"),
            ("JE", "JE2 3AB", "JE23AB"),
            ("MT", "MTF 1234", "MTF1234"),
            ("SE", "AX-22100", "AX-22100"),
            ("SE", None, ""),
        ]

        for country_code, postal_code, expected in cases:
            with self.subTest(country_code=country_code, postal_code=postal_code):
                self.assertEqual(
                    units.normalized_postal_code(country_code, postal_code), expected
                )


if __name__ == "__main__":
    unittest.main()
