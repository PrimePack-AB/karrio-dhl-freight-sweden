"""DHL Freight (SE API Farm) access-point eligibility tests.

AccessPoint parties are checked per product and destination country against
DHL Freight Sweden product manual v5.23: 103 to SE accepts parcelshops and
parcelstations (§5.14 p59-60), 109 follows Appendix B.3 (§10.3.2 p196-197),
and 112 has no accessPoint party (§5.3 p14). Live sandbox booking 22015
"AccessPoint Party is not allowed for this product" (2026-10-05) is the
carrier-side failure these checks pre-empt.
"""

import unittest

import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import (
    ServicePointEligibilityError,
)

from .fixture import detail_keys, gateway, serialize_request
from .test_shipment import _payload, _recipient_de, _recipient_pl, _recipient_se


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
                _service_point("8005-PL-4507446", "ParcelShop", "PL"),
            )
        )

        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_service_point"})
        self.assertIn("no access point", str(error))

    def test_parcel_connect_to_de_rejects_parcel_station(self):
        error = self._error(
            _payload(
                "dhl_freight_sweden_parcel_connect_b2c",
                _recipient_de,
                _service_point("8003-4012345", "ParcelStation", "DE"),
            )
        )

        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_service_point_type"})
        self.assertIn("only ParcelShop", str(error))

    def test_parcel_connect_to_de_accepts_parcel_shop(self):
        access_point = self._access_point(
            _payload(
                "dhl_freight_sweden_parcel_connect_b2c",
                _recipient_de,
                _service_point("8003-4012345", "ParcelShop", "DE"),
            )
        )

        self.assertEqual(access_point["subType"], "ParcelShop")

    def test_parcel_connect_to_pl_accepts_parcel_station(self):
        access_point = self._access_point(
            _payload(
                "dhl_freight_sweden_parcel_connect_b2c",
                _recipient_pl,
                {
                    **_service_point("8005-PL-4507446", "ParcelStation", "PL"),
                    "dhl_freight_sweden_sent_free": True,
                },
            )
        )

        self.assertEqual(access_point["subType"], "ParcelStation")

    def test_parcel_connect_to_ie_rejects_access_point(self):
        error = self._error(
            _payload(
                "dhl_freight_sweden_parcel_connect_b2c",
                _recipient_ie,
                _service_point("8006-IE-1", "ParcelShop", "IE"),
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
                    **_service_point("8003-4012345", "ParcelShop", "DE"),
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


def _service_point(service_point_id: str, sub_type: str, country_code: str) -> dict:
    return {
        "dhl_freight_sweden_service_point": service_point_id,
        "dhl_freight_sweden_service_point_type": sub_type,
        "dhl_freight_sweden_service_point_name": "DHL Parcelshop",
        "dhl_freight_sweden_service_point_street": "Main Street 1",
        "dhl_freight_sweden_service_point_city": "City",
        "dhl_freight_sweden_service_point_postal_code": "10001",
        "dhl_freight_sweden_service_point_country_code": country_code,
    }


_recipient_ie = {
    **_recipient_se,
    "city": "Dublin",
    "postal_code": "D02 X285",
    "country_code": "IE",
}


if __name__ == "__main__":
    unittest.main()
