"""Sandbox segment ``booking-pudo``: service point lookup chained into a booking.

Each test finds the service points nearest the recipient, picks the first
candidate with an id and a complete address, and books it as the AccessPoint
party: 103 within SE, 109 from SE to PL (payer code 022, SENT free).
"""

import typing
import unittest

import karrio.lib as lib
import karrio.providers.dhl_freight_sweden.service_points as service_points
from . import booking, harness

SE_RECIPIENT = {
    "person_name": "Anna Andersson",
    "address_line1": "Drottninggatan 10",
    "city": "Stockholm",
    "postal_code": "11151",
    "country_code": "SE",
    "phone_number": "+46 70 123 45 67",
    "email": "anna.andersson@example.se",
    "residential": True,
}
PL_RECIPIENT = {
    "person_name": "Jan Kowalski",
    "address_line1": "ul. Królewska 10",
    "city": "Kraków",
    "postal_code": "30-079",
    "country_code": "PL",
    "phone_number": "+48 600 000 000",
    "email": "jan.kowalski@example.pl",
    "residential": True,
}
ADDRESS_FIELDS = ("street", "city", "postal_code", "country_code")


def service_point_options(point: dict) -> dict:
    address = point["address"]
    return {
        "dhl_freight_sweden_service_point": point["service_point_id"],
        "dhl_freight_sweden_service_point_type": (
            "ParcelStation" if point.get("type") == "locker" else "ParcelShop"
        ),
        "dhl_freight_sweden_service_point_name": point.get("name"),
        "dhl_freight_sweden_service_point_street": address["street"],
        "dhl_freight_sweden_service_point_city": address["city"],
        "dhl_freight_sweden_service_point_postal_code": address["postal_code"],
        "dhl_freight_sweden_service_point_country_code": address["country_code"],
    }


class TestSandboxBookingPudo(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment("booking-pudo")
        cls.gateway = cls.session.gateway()

    def setUp(self):
        self.maxDiff = None

    def nearest_point(self, label: str, recipient: dict) -> dict:
        request = service_points.service_points_request(
            dict(
                address=dict(
                    street=recipient["address_line1"],
                    city=recipient["city"],
                    postal_code=recipient["postal_code"],
                    country_code=recipient["country_code"],
                ),
                max_items=5,
                parcel=booking.PARCEL,
            ),
            harness.settings_of(self.gateway),
        )
        try:
            points, messages = service_points.parse_service_points_response(
                harness.proxy_of(self.gateway).find_service_points(request),
                harness.settings_of(self.gateway),
            )
        finally:
            self.session.capture(self.gateway, label)
        self.session.capture_parsed(
            label, dict(points=points, messages=lib.to_dict(messages))
        )

        self.assertEqual(lib.to_dict(messages), [])
        candidate: typing.Optional[dict] = next(
            (
                point
                for point in points
                if point.get("service_point_id")
                and all((point.get("address") or {}).get(f) for f in ADDRESS_FIELDS)
            ),
            None,
        )
        if candidate is None:
            self.fail(f"no complete service point candidate among {len(points)}")
        return candidate

    def test_book_103_service_point_se(self):
        booking.require_booking(self, self.session, "103", "SE")
        point = self.nearest_point("service-points-103-se", SE_RECIPIENT)

        booking.book(
            self,
            self.session,
            self.gateway,
            "103",
            dict(
                service="103",
                shipper=booking.SHIPPER,
                recipient=SE_RECIPIENT,
                parcels=[booking.PARCEL],
                options=service_point_options(point),
            ),
        )

    def test_book_109_service_point_pl(self):
        booking.require_booking(self, self.session, "109", "PL")
        point = self.nearest_point("service-points-109-pl", PL_RECIPIENT)

        booking.book(
            self,
            self.session,
            self.gateway,
            "109",
            dict(
                service="109",
                shipper=booking.SHIPPER,
                recipient=PL_RECIPIENT,
                parcels=[booking.PARCEL],
                options=dict(
                    **service_point_options(point),
                    dhl_freight_sweden_payer_code="022",
                ),
            ),
        )
