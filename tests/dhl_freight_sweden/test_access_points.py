"""DHL Freight (SE API Farm) access-point eligibility tests.

AccessPoint parties are checked per product and destination country against
DHL Freight Sweden product manual v5.26: 103 to SE accepts parcelshops and
parcelstations (§5.12 p55-56), 109 follows Appendix C.3 (§10.4.2
p192-194), and 112 has no accessPoint party (§5.3 p19). The sandbox rejection 22015
"AccessPoint Party is not allowed for this product"
(fixtures/sandbox/rejection-22015-112-se-pl-access-point.json) is the
carrier-side failure these checks pre-empt.

The AccessPoint id differs per product: 103 sends a four-digit terminal id
(§10.14.2.1 p231), 109 the ServicePointLocator response's ``id`` field
(§10.14.2.2 p232), so the locator's ``servicePointId`` is refused for 109.
"""

import unittest

import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import (
    ExcludedDestinationError,
    ServicePointCountryError,
    ServicePointEligibilityError,
    ServicePointIdError,
    TerritoryPostalCodeError,
)

from .fixture import detail_keys, gateway, serialize_request
from .test_shipment import (
    Customs,
    _payload,
    _recipient_de,
    _recipient_gb,
    _recipient_no,
    _recipient_pl,
    _recipient_se,
)


class TestDHLFreightAccessPoints(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _access_point(self, payload: dict) -> dict:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        return next(
            party
            for party in serialize_request(request)["parties"]
            if party["type"] == "AccessPoint"
        )

    def _error(self, payload: dict) -> ServicePointEligibilityError:
        with self.assertRaises(ServicePointEligibilityError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def test_parcel_connect_plus_rejects_access_point(self):
        error = self._error(
            _payload(
                "dhl_freight_sweden_parcel_connect_plus",
                _recipient_pl,
                _service_point("101", "ParcelShop", "PL"),
            )
        )

        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_service_point"})
        self.assertIn("no access point", str(error))

    def test_parcel_connect_to_de_rejects_parcel_station(self):
        error = self._error(
            _payload(
                "dhl_freight_sweden_parcel_connect_b2c",
                _recipient_de,
                _service_point("4012345", "ParcelStation", "DE"),
            )
        )

        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_service_point_type"})
        self.assertIn("only ParcelShop", str(error))

    def test_parcel_connect_to_de_accepts_parcel_shop(self):
        access_point = self._access_point(
            _payload(
                "dhl_freight_sweden_parcel_connect_b2c",
                _recipient_de,
                _service_point("4012345", "ParcelShop", "DE"),
            )
        )

        self.assertEqual(access_point["subType"], "ParcelShop")

    def test_parcel_connect_to_gb_accepts_only_parcel_shop(self):
        # Appendix C.3 p193: GB residential and Parcelshop addressing, no
        # Parcelstation.
        access_point = self._access_point(
            {
                **_payload(
                    "dhl_freight_sweden_parcel_connect_b2c",
                    _recipient_gb,
                    _service_point("123456", "ParcelShop", "GB"),
                ),
                "customs": Customs,
            }
        )
        error = self._error(
            _payload(
                "dhl_freight_sweden_parcel_connect_b2c",
                _recipient_gb,
                _service_point("123456", "ParcelStation", "GB"),
            )
        )

        self.assertEqual(access_point["subType"], "ParcelShop")
        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_service_point_type"})

    def test_parcel_connect_to_pl_accepts_parcel_station(self):
        # 101 is a committed PL lookup id, shared by several shops
        # (fixtures/sandbox/booking-2906769613-109-se-pl-without-sent.json).
        access_point = self._access_point(
            _payload(
                "dhl_freight_sweden_parcel_connect_b2c",
                _recipient_pl,
                {
                    **_service_point("101", "ParcelStation", "PL"),
                    "dhl_freight_sweden_sent_free": True,
                },
            )
        )

        self.assertEqual(access_point["subType"], "ParcelStation")

    def test_parcel_connect_to_it_accepts_parcel_station(self):
        access_point = self._access_point(
            _payload(
                "dhl_freight_sweden_parcel_connect_b2c",
                _recipient_it,
                _service_point("123456", "ParcelStation", "IT"),
            )
        )

        self.assertEqual(access_point["subType"], "ParcelStation")

    def test_parcel_connect_to_ie_rejects_access_point(self):
        error = self._error(
            _payload(
                "dhl_freight_sweden_parcel_connect_b2c",
                _recipient_ie,
                _service_point("123456", "ParcelShop", "IE"),
            )
        )

        self.assertIn("no access point", str(error))

    def test_service_point_b2c_accepts_parcel_station(self):
        access_point = self._access_point(
            _payload(
                "dhl_freight_sweden_service_point_b2c",
                _recipient_se,
                _service_point("SE-230500", "ParcelStation", "SE"),
            )
        )

        self.assertEqual(access_point["subType"], "ParcelStation")

    def test_service_point_b2c_rejects_unknown_sub_type(self):
        error = self._error(
            _payload(
                "dhl_freight_sweden_service_point_b2c",
                _recipient_se,
                _service_point("SE-230500", "locker", "SE"),
            )
        )

        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_service_point_type"})

    def test_freight_product_rejects_access_point(self):
        error = self._error(
            _payload(
                "dhl_freight_sweden_road_freight_standard",
                _recipient_de,
                {
                    **_service_point("4012345", "ParcelShop", "DE"),
                    "dhl_freight_sweden_payer_code": "DAP",
                },
            )
        )

        self.assertIn("no access point", str(error))

    def test_type_name_as_service_point_id_fails(self):
        type_names = ["ParcelShop", "parcelstation", "servicepoint", "Locker", "postoffice"]

        for type_name in type_names:
            with self.subTest(type_name=type_name):
                error = self._error(
                    _payload(
                        "dhl_freight_sweden_parcel_connect_b2c",
                        _recipient_pl,
                        _service_point(type_name, "ParcelShop", "PL"),
                    )
                )

                self.assertEqual(
                    detail_keys(error), {"dhl_freight_sweden_service_point"}
                )
                self.assertIn("dhl_freight_sweden_service_point_type", str(error))


class TestDHLFreightServicePointTerminalId(unittest.TestCase):
    """103 sends only the four-digit terminal id nnnn of a SE-nnnn00 id.

    Product manual v5.26 §10.14.2.1 p231 and IFTMIN v3.7 Appendix A p59:
    the id SE-651400 from the ServicePointLocator API is sent as 6514.
    """

    def _access_point_id(self, product: str, recipient: dict, options: dict) -> str:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**_payload(product, recipient, options))
        )
        return next(
            party["id"]
            for party in serialize_request(request)["parties"]
            if party["type"] == "AccessPoint"
        )

    def test_service_point_b2c_sends_the_terminal_id(self):
        cases = {"SE-651400": "6514", "SE-982000": "9820", " SE-230500 ": "2305"}

        for service_point_id, terminal_id in cases.items():
            with self.subTest(service_point_id=service_point_id):
                self.assertEqual(
                    self._access_point_id(
                        "dhl_freight_sweden_service_point_b2c",
                        _recipient_se,
                        _service_point(service_point_id, "ParcelShop", "SE"),
                    ),
                    terminal_id,
                )

    def test_service_point_b2c_accepts_a_lowercase_country_prefix(self):
        cases = {"se-651400": "6514", "Se-982000": "9820"}

        for service_point_id, terminal_id in cases.items():
            with self.subTest(service_point_id=service_point_id):
                self.assertEqual(
                    self._access_point_id(
                        "dhl_freight_sweden_service_point_b2c",
                        _recipient_se,
                        _service_point(service_point_id, "ParcelShop", "SE"),
                    ),
                    terminal_id,
                )

    def test_service_point_b2c_keeps_a_terminal_id(self):
        self.assertEqual(
            self._access_point_id(
                "dhl_freight_sweden_service_point_b2c",
                _recipient_se,
                _service_point("6514", "ParcelShop", "SE"),
            ),
            "6514",
        )

    def test_parcel_connect_keeps_other_ids_verbatim(self):
        self.assertEqual(
            self._access_point_id(
                "dhl_freight_sweden_parcel_connect_b2c",
                _recipient_pl,
                {
                    **_service_point("PL-651400", "ParcelShop", "PL"),
                    "dhl_freight_sweden_sent_free": True,
                },
            ),
            "PL-651400",
        )

    def test_service_point_b2c_refuses_ids_without_a_terminal_id(self):
        service_point_ids = [
            "SE-651401",
            "SE-65140",
            "SE-6514000",
            "SE-ABCD00",
            "DK-651400",
            "dk-651400",
            "pl-651400",
            "se-651401",
            "651400",
            "651",
            "8009-591371",
        ]

        for service_point_id in service_point_ids:
            with self.subTest(service_point_id=service_point_id):
                with self.assertRaises(ServicePointIdError) as context:
                    gateway.mapper.create_shipment_request(
                        models.ShipmentRequest(
                            **_payload(
                                "dhl_freight_sweden_service_point_b2c",
                                _recipient_se,
                                _service_point(service_point_id, "ParcelShop", "SE"),
                            )
                        )
                    )

                self.assertEqual(
                    detail_keys(context.exception),
                    {"dhl_freight_sweden_service_point"},
                )
                self.assertIn(repr(service_point_id), str(context.exception))
                self.assertIn("SE-nnnn00", str(context.exception))


class TestDHLFreightParcelConnectLookupId(unittest.TestCase):
    """109 books the AccessPoint party by the lookup response's ``id`` field.

    Manual v5.26 §10.14.2.2 p232 names ``id`` as the AccessPoint party id,
    and DHL's 2026-10-13 clarification says the short id is the lookup
    response's ``id`` field, not its ``servicePointId``. Booking 2906785361
    sent the lookup's id 115191 and was accepted with the same routing code
    as the earlier ``servicePointId`` booking 2906761354
    (fixtures/sandbox/booking-2906785361-109-se-dk-lookup-id.json).
    """

    def setUp(self):
        self.maxDiff = None

    def _access_point_id(self, options: dict) -> str:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(
                **_payload(
                    "dhl_freight_sweden_parcel_connect_b2c", _recipient_dk, options
                )
            )
        )
        return next(
            party["id"]
            for party in serialize_request(request)["parties"]
            if party["type"] == "AccessPoint"
        )

    def test_sends_the_lookup_id_verbatim(self):
        # Lookup ids observed in committed fixtures: 115191 (DK), free text
        # with spaces and dashes (HU), 101 (PL), and Åland's shared 3201.
        lookup_ids = ["115191", "373CSA-BP", "BP-5 POSTA", "101", "3201"]

        for lookup_id in lookup_ids:
            with self.subTest(lookup_id=lookup_id):
                self.assertEqual(
                    self._access_point_id(
                        _service_point(lookup_id, "ParcelShop", "DK")
                    ),
                    lookup_id,
                )

    def test_refuses_service_point_locator_service_point_ids(self):
        service_point_ids = [
            "8009-115191",
            "8005-PL-4507446",
            "8005-pl-4507446",
            "8013-118530",
            "8055-ES-0005858",
            " 8009-115191 ",
        ]

        for service_point_id in service_point_ids:
            with self.subTest(service_point_id=service_point_id):
                with self.assertRaises(ServicePointIdError) as context:
                    gateway.mapper.create_shipment_request(
                        models.ShipmentRequest(
                            **_payload(
                                "dhl_freight_sweden_parcel_connect_b2c",
                                _recipient_dk,
                                _service_point(service_point_id, "ParcelShop", "DK"),
                            )
                        )
                    )

                self.assertEqual(
                    detail_keys(context.exception),
                    {"dhl_freight_sweden_service_point"},
                )
                self.assertIn(repr(service_point_id), str(context.exception))
                self.assertIn("servicePointId", str(context.exception))


class TestDHLFreightAccessPointCountry(unittest.TestCase):
    """The AccessPoint party country is checked after territory mapping.

    103 is valid for SE only and its DP party is the service point
    (manual v5.26 §5.12 p56).
    109 requires CN and DP in the same country for shipments from or to a
    country outside the EU (§5.14 p63); EU-to-EU differences are left to DHL.
    """

    def setUp(self):
        self.maxDiff = None

    def _access_point(self, payload: dict) -> dict:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        return next(
            party
            for party in serialize_request(request)["parties"]
            if party["type"] == "AccessPoint"
        )

    def _error(self, payload: dict) -> ServicePointCountryError:
        with self.assertRaises(ServicePointCountryError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def test_service_point_b2c_refuses_a_service_point_outside_se(self):
        error = self._error(
            _payload(
                "dhl_freight_sweden_service_point_b2c",
                _recipient_se,
                _service_point("SE-230500", "ParcelShop", "DK"),
            )
        )

        self.assertEqual(
            detail_keys(error), {"dhl_freight_sweden_service_point_country_code"}
        )
        self.assertEqual(
            str(error),
            "Product 103 delivers to a service point in SE; "
            "the service point country DK is not SE",
        )

    def test_parcel_connect_refuses_a_mismatch_to_a_country_outside_the_eu(self):
        cases = [
            (_recipient_gb, "DK", "GB"),
            (_recipient_no, "SE", "NO"),
            (_recipient_dk, "NO", "DK"),
            (_recipient_dk, "GB", "DK"),
        ]

        for recipient, point_country, recipient_country in cases:
            with self.subTest(point=point_country, recipient=recipient_country):
                error = self._error(
                    {
                        **_payload(
                            "dhl_freight_sweden_parcel_connect_b2c",
                            recipient,
                            _service_point("123456", "ParcelShop", point_country),
                        ),
                        "customs": Customs,
                    }
                )

                self.assertEqual(
                    detail_keys(error),
                    {"dhl_freight_sweden_service_point_country_code"},
                )
                self.assertEqual(
                    str(error),
                    "Product 109 from or to a country outside the EU delivers "
                    "to a service point in the consignee's country; the service "
                    f"point country {point_country} differs from the recipient "
                    f"country {recipient_country}",
                )

    def test_parcel_connect_leaves_eu_mismatches_to_dhl(self):
        access_point = self._access_point(
            _payload(
                "dhl_freight_sweden_parcel_connect_b2c",
                _recipient_dk,
                _service_point("123456", "ParcelShop", "DE"),
            )
        )

        self.assertEqual(access_point["address"]["countryCode"], "DE")

    def test_parcel_connect_sends_a_territory_service_point_as_its_parent(self):
        cases = [
            (_recipient_gb, "IM", "GB"),
            ({**_recipient_gb, "country_code": "IM", "postal_code": "IM1 1AA"}, "GB", "GB"),
            (_recipient_fi, "AX", "FI"),
        ]

        for recipient, point_country, sent_country in cases:
            with self.subTest(point=point_country, recipient=recipient["country_code"]):
                access_point = self._access_point(
                    {
                        **_payload(
                            "dhl_freight_sweden_parcel_connect_b2c",
                            recipient,
                            _service_point("123456", "ParcelShop", point_country),
                        ),
                        "customs": Customs,
                    }
                )

                self.assertEqual(access_point["address"]["countryCode"], sent_country)

    def test_service_point_b2c_accepts_a_service_point_in_se(self):
        access_point = self._access_point(
            _payload(
                "dhl_freight_sweden_service_point_b2c",
                _recipient_se,
                _service_point("SE-230500", "ParcelShop", "se"),
            )
        )

        self.assertEqual(access_point["address"]["countryCode"], "SE")


class TestDHLFreightAccessPointPostalCode(unittest.TestCase):
    """The service point postal code meets the recipient's excluded regions.

    The service point is the delivery address (DP), so the manual's excluded
    regions of 109, Jersey, Guernsey, Northern Ireland, Greenland, and the
    Faroe Islands among them (§5.14 p63), apply to it as to the recipient,
    and a territory code needs a postal code of the territory.
    """

    def setUp(self):
        self.maxDiff = None

    def _book(self, recipient: dict, point_country: str, postal_code: str):
        return gateway.mapper.create_shipment_request(
            models.ShipmentRequest(
                **{
                    **_payload(
                        "dhl_freight_sweden_parcel_connect_b2c",
                        recipient,
                        {
                            **_service_point("123456", "ParcelShop", point_country),
                            "dhl_freight_sweden_service_point_postal_code": postal_code,
                        },
                    ),
                    "customs": Customs,
                }
            )
        )

    def test_refuses_an_excluded_service_point(self):
        cases = [
            (_recipient_gb, "JE", "JE2 3AB", "GB postal codes JE*, GY*, BT* (Jersey, Guernsey, and Northern Ireland)"),
            (_recipient_gb, "GB", "GY1 1AA", "GB postal codes JE*, GY*, BT* (Jersey, Guernsey, and Northern Ireland)"),
            (_recipient_dk, "DK", "3900", "DK postal codes 3800-3999 (Greenland and the Faroe Islands)"),
            (_recipient_dk, "FO", "100", "DK postal codes 3800-3999 (Greenland and the Faroe Islands)"),
        ]

        for recipient, point_country, postal_code, excluded in cases:
            with self.subTest(point=point_country, postal_code=postal_code):
                with self.assertRaises(ExcludedDestinationError) as context:
                    self._book(recipient, point_country, postal_code)

                self.assertEqual(
                    detail_keys(context.exception),
                    {"dhl_freight_sweden_service_point_postal_code"},
                )
                self.assertEqual(
                    str(context.exception),
                    f"Product 109 does not ship to {excluded}; "
                    f"got service point postal code {postal_code}",
                )

    def test_accepts_a_served_service_point(self):
        cases = [
            (_recipient_gb, "GB", "SE16 2BE", "GB"),
            (_recipient_dk, "DK", "1620", "DK"),
            (_recipient_fi, "AX", "22100", "FI"),
        ]

        for recipient, point_country, postal_code, sent_country in cases:
            with self.subTest(point=point_country, postal_code=postal_code):
                access_point = next(
                    party
                    for party in serialize_request(
                        self._book(recipient, point_country, postal_code)
                    )["parties"]
                    if party["type"] == "AccessPoint"
                )

                self.assertEqual(
                    access_point["address"],
                    {**access_point["address"], "countryCode": sent_country, "postalCode": postal_code},
                )

    def test_refuses_a_territory_service_point_outside_the_territory(self):
        with self.assertRaises(TerritoryPostalCodeError) as context:
            self._book(_recipient_fi, "AX", "00100")

        self.assertEqual(
            detail_keys(context.exception),
            {"dhl_freight_sweden_service_point_postal_code"},
        )
        self.assertEqual(
            str(context.exception),
            "Country code AX (Åland) is booked as FI and needs an FI postal code "
            "in 22000-22999; got service point postal code '00100'",
        )


def _service_point(service_point_id: str, sub_type: str, country_code: str) -> dict:
    return {
        "dhl_freight_sweden_service_point": service_point_id,
        "dhl_freight_sweden_service_point_type": sub_type,
        "dhl_freight_sweden_service_point_name": "DHL Parcelshop",
        "dhl_freight_sweden_service_point_street": "Main Street 1",
        "dhl_freight_sweden_service_point_city": "City",
        "dhl_freight_sweden_service_point_postal_code": _POSTAL_CODES.get(
            country_code.upper(), "10001"
        ),
        "dhl_freight_sweden_service_point_country_code": country_code,
    }


_POSTAL_CODES = {
    "AX": "22100",
    "DK": "1620",
    "GB": "SE16 2BE",
    "IM": "IM1 1AA",
    "NO": "0154",
    "SE": "11143",
}


_recipient_dk = {
    **_recipient_se,
    "city": "København V",
    "postal_code": "1620",
    "country_code": "DK",
}

_recipient_ie = {
    **_recipient_se,
    "city": "Dublin",
    "postal_code": "D02 X285",
    "country_code": "IE",
}

_recipient_it = {
    **_recipient_se,
    "city": "Roma",
    "postal_code": "00184",
    "country_code": "IT",
}


if __name__ == "__main__":
    unittest.main()

_recipient_fi = {
    **_recipient_se,
    "city": "Helsinki",
    "postal_code": "00100",
    "country_code": "FI",
}
