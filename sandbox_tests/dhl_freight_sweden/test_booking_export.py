"""Sandbox segment ``booking-export``: Parcel Connect from SE to a destination matrix.

Each test books 109 (Parcel Connect B2C, to a service point) or 112 (Parcel
Connect Plus, home delivery) from SE to PL, RO, HU, or NO, and 109 to a DK
ParcelShop. Before spending a booking it checks for free that product
matches offer the product for the lane and, for 109, that a service point
near the recipient accepts it, and skips otherwise. Lanes to PL declare SENT
free explicitly.

NO is outside the EU VAT area, so its bookings carry one commodity, a
proforma invoice number, and DHL customs handling full service, the customs
service that needs no registration identifier. The Incoterm sets the payer
code through the Combiterm translation: DAP gives 022 for 109, which avoids
the joint customs declaration that 023 requires on 109, and DDP gives 112's
default 023.
"""

import typing
import unittest

import karrio.providers.dhl_freight_sweden.units as provider_units
from . import booking, harness

INCOTERMS = {"109": "DAP", "112": "DDP"}
COMMODITY = {
    "title": "Cotton T-shirt",
    "description": "Cotton T-shirt",
    "quantity": 1,
    "weight": 0.5,
    "weight_unit": "KG",
    "value_amount": 200,
    "value_currency": "SEK",
    "origin_country": "SE",
    "hs_code": "610910",
}


def export_customs(product: str, recipient: dict) -> typing.Tuple[dict, dict]:
    """Customs payload and options for a lane, both empty within the EU VAT area."""
    if provider_units.in_eu_vat_area(recipient["country_code"], recipient["postal_code"]):
        return {}, {}

    return (
        dict(
            customs=dict(
                incoterm=INCOTERMS[product],
                invoice="SANDBOX-INV-1",
                content_type="merchandise",
                commodities=[COMMODITY],
            )
        ),
        dict(dhl_freight_sweden_customs_handling_full_service=True),
    )


class TestSandboxBookingExport(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment("booking-export")
        cls.gateway = cls.session.gateway()

    def setUp(self):
        self.maxDiff = None

    def export(
        self,
        product: str,
        country: str,
        sub_types: typing.Optional[typing.AbstractSet[str]] = None,
    ):
        booking.require_booking(self, self.session, product, country)
        recipient = booking.RECIPIENTS[country]
        lane = f"{product}-{country.lower()}"

        codes, messages = booking.offered_products(
            self.session, self.gateway, f"product-matches-{lane}", recipient
        )
        if messages:
            self.skipTest(
                f"product matches pre-check for SE to {country} failed: "
                f"{[message.message for message in messages]}"
            )
        if product not in codes:
            self.skipTest(f"product matches do not offer {product} from SE to {country}")

        options: dict = {}
        if product == "109":
            point, messages = booking.nearest_service_point(
                self.session, self.gateway, f"service-points-{lane}", product, recipient, sub_types
            )
            if point is None:
                self.skipTest(
                    f"no {'/'.join(sorted(sub_types)) if sub_types else 'service point'} "
                    f"near {recipient['city']} accepts {product}: "
                    f"{[message.message for message in messages]}"
                )
            options.update(booking.service_point_options(point))

        customs, customs_options = export_customs(product, recipient)
        booking.book(
            self,
            self.session,
            self.gateway,
            product,
            dict(
                service=product,
                shipper=booking.SHIPPER,
                recipient=recipient,
                parcels=[booking.PARCEL],
                options={
                    **options,
                    **customs_options,
                    **booking.declaration_options(recipient),
                },
                **customs,
            ),
        )

    def test_book_109_pl(self):
        self.export("109", "PL")

    def test_book_112_pl(self):
        self.export("112", "PL")

    def test_book_109_ro(self):
        self.export("109", "RO")

    def test_book_112_ro(self):
        self.export("112", "RO")

    def test_book_109_hu(self):
        self.export("109", "HU")

    def test_book_112_hu(self):
        self.export("112", "HU")

    def test_book_109_no(self):
        self.export("109", "NO")

    def test_book_112_no(self):
        self.export("112", "NO")

    def test_book_109_dk_parcel_shop(self):
        self.export("109", "DK", frozenset({provider_units.PartySubType.ParcelShop.value}))

