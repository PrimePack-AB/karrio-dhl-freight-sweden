"""Sandbox segment ``booking-export``: export products from SE to a destination matrix.

Each test books 109 (Parcel Connect B2C, to a service point) or 112 (Parcel
Connect Plus, home delivery) from SE to PL, RO, HU, or NO, 109 to a DK
ParcelShop, and 112 to FR and GB, which product manual v5.26 adds for 112,
GB only according to a separate agreement. Åland (FI 22100) is booked with
109, customs data, and no customs handling service; the connector's refusals
of 112 with a customs handling service and of 109 without customs data are
asserted without booking. Northern Ireland (GB BT1 1AA), inside the EU VAT
area for goods, is booked with 202 without customs data. The freight products 202, 205,
and 233 book to DK inside the EU VAT area, and 202, 205, 233, and 601 to NO
with customs handling full service, each with the explicit DAP payer code,
and 112 and 109 book to NO with customs handling Standard and a made-up
EORI number. 601 books to CH with customs handling full service and a
commercial invoice carrying a declared value.
Before spending a booking it checks for free that product matches offer the
product for the lane and, for 109, that a service point near the recipient
accepts it, and skips otherwise. Lanes to PL declare SENT free explicitly.

NO and GB are outside the EU VAT area, so their bookings carry customs data
when they carry any: one commodity, a commercial invoice number, and DHL
customs handling full service, the customs service that needs no
registration identifier. The Incoterm sets the payer
code through the Combiterm translation: DAP gives 022 for 109, which avoids
the joint customs declaration that 023 requires on 109, and DDP gives 112's
default 023. The freight products 202, 205, 233, and 601 map to DAP, and each
freight case also passes that Incoterm as its explicit payer code, because the
freight products have no default payer code.
"""

import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.dhl_freight_sweden.shipment.create as create

import karrio.providers.dhl_freight_sweden.units as provider_units
from . import booking, harness

INCOTERMS = {"109": "DAP", "112": "DDP", "202": "DAP", "205": "DAP", "233": "DAP", "601": "DAP"}
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


CONSUMER_PARCEL = {**booking.PARCEL, "weight": 2.0, "height": 15.0}
# The connector would derive the same 200 SEK from COMMODITY; the explicit
# declared value keeps the request booked as 2906762477 reproducible.
DECLARED_VALUE = {"duty": {"paid_by": "recipient", "currency": "SEK", "declared_value": 200}}


# The Posti ParcelShop booking 2906761917 used in Mariehamn (tests/dhl_freight_sweden/
# fixtures/sandbox/booking-2906761917-109-se-fi-aland.json); the refusal
# case needs no live service point lookup.
ALAND_PARCEL_SHOP = {
    "dhl_freight_sweden_service_point": "8011-221003201",
    "dhl_freight_sweden_service_point_type": "ParcelShop",
    "dhl_freight_sweden_service_point_name": "c/o Posti",
    "dhl_freight_sweden_service_point_street": "Nygatan 6",
    "dhl_freight_sweden_service_point_city": "Mariehamn",
    "dhl_freight_sweden_service_point_postal_code": "22100",
    "dhl_freight_sweden_service_point_country_code": "FI",
}


# Customs handling - Standard requires the EORI number; the suite's is made up.
SANDBOX_EORI = "SE0000000000"


def export_customs(
    product: str, recipient: dict, standard: bool = False
) -> typing.Tuple[dict, dict]:
    """Customs payload and options for a lane, both empty within the EU VAT area.

    The customs service is full service, or with ``standard`` Customs
    handling - Standard with ``SANDBOX_EORI``.
    """
    if provider_units.in_eu_vat_area(recipient["country_code"], recipient["postal_code"]):
        return {}, {}

    return (
        dict(
            customs=dict(
                incoterm=INCOTERMS[product],
                invoice="SANDBOX-INV-1",
                content_type="merchandise",
                commercial_invoice=True,
                commodities=[COMMODITY],
                **(dict(options=dict(eori_number=SANDBOX_EORI)) if standard else {}),
            )
        ),
        lib.identity(
            dict(dhl_freight_sweden_customs_handling_standard=True)
            if standard
            else dict(dhl_freight_sweden_customs_handling_full_service=True)
        ),
    )


def export_payload(
    product: str,
    recipient: dict,
    options: dict,
    extra_options: typing.Optional[dict] = None,
    with_customs: bool = True,
    customs_service: bool = True,
    standard_customs: bool = False,
    parcel: dict = booking.PARCEL,
    extra_customs: typing.Optional[dict] = None,
) -> dict:
    """Shipment payload for ``product`` from ``booking.SHIPPER`` to ``recipient``.

    ``options`` carries the service point, and ``extra_options``, such as a
    case's explicit payer code, override every other option.
    ``customs_service`` False sends the customs data without a customs
    handling service.
    """
    customs, customs_options = (
        export_customs(product, recipient, standard_customs) if with_customs else ({}, {})
    )
    if customs and extra_customs:
        customs["customs"].update(extra_customs)
    return dict(
        service=product,
        shipper=booking.SHIPPER,
        recipient=recipient,
        parcels=[parcel],
        options={
            **options,
            **(customs_options if customs_service else {}),
            **booking.declaration_options(recipient),
            **(extra_options or {}),
        },
        **customs,
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
        require_product_match: bool = True,
        recipient: typing.Optional[dict] = None,
        with_customs: bool = True,
        customs_service: bool = True,
        extra_options: typing.Optional[dict] = None,
        standard_customs: bool = False,
        parcel: dict = booking.PARCEL,
        extra_customs: typing.Optional[dict] = None,
    ):
        """Book ``product`` from SE to ``country``.

        ``require_product_match`` False still records the product matches
        lookup but books even when it does not offer the product, so DHL's
        answer to the booking itself is captured. ``recipient`` replaces the
        country's default recipient, and ``with_customs`` False books
        without customs data, and ``customs_service`` False without a
        customs handling service. ``extra_customs`` is merged into the
        customs payload when there is one.
        """
        booking.require_booking(self, self.session, product, country)
        lane = f"{product}-{country.lower()}"
        if recipient is None:
            recipient = booking.RECIPIENTS[country]
        else:
            lane = f"{lane}-{recipient['postal_code'].lower().replace(' ', '')}"

        codes, messages = booking.offered_products(
            self.session, self.gateway, f"product-matches-{lane}", recipient
        )
        if messages:
            self.skipTest(
                f"product matches pre-check for SE to {country} failed: "
                f"{[message.message for message in messages]}"
            )
        if product not in codes and require_product_match:
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

        booking.book(
            self,
            self.session,
            self.gateway,
            product,
            export_payload(
                product,
                recipient,
                options,
                extra_options,
                with_customs=with_customs,
                customs_service=customs_service,
                standard_customs=standard_customs,
                parcel=parcel,
                extra_customs=extra_customs,
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

    def test_book_112_fr(self):
        self.export("112", "FR")

    def test_book_112_gb(self):
        # Product matches did not offer 112 to GB (fixtures/sandbox/
        # lookup-product-matches-se-gb.json); the booking records DHL's answer.
        self.export("112", "GB", require_product_match=False)

    def test_book_112_no_customs_standard(self):
        self.export("112", "NO", standard_customs=True)

    def test_book_109_no_customs_standard(self):
        self.export("109", "NO", standard_customs=True)

    def test_book_202_dk(self):
        self.export(
            "202", "DK", with_customs=False,
            extra_options={"dhl_freight_sweden_payer_code": "DAP"},
        )

    def test_book_202_no_customs_full(self):
        self.export(
            "202", "NO", extra_options={"dhl_freight_sweden_payer_code": "DAP"}
        )

    def test_book_205_dk(self):
        self.export(
            "205", "DK", with_customs=False,
            extra_options={"dhl_freight_sweden_payer_code": "DAP"},
        )

    def test_book_205_no_customs_full(self):
        self.export(
            "205", "NO", extra_options={"dhl_freight_sweden_payer_code": "DAP"}
        )

    def test_book_233_dk(self):
        self.export(
            "233", "DK", with_customs=False,
            extra_options={"dhl_freight_sweden_payer_code": "DAP"},
        )

    def test_book_233_no_customs_full(self):
        self.export(
            "233", "NO", extra_options={"dhl_freight_sweden_payer_code": "DAP"}
        )

    def test_book_601_no_customs_full(self):
        self.export(
            "601", "NO", extra_options={"dhl_freight_sweden_payer_code": "DAP"}
        )

    def test_book_601_ch_customs_full_commercial_invoice(self):
        # A B2C sale to CH: product matches offered 601 but not 109 or 112
        # (tests/dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-8001.json).
        self.export(
            "601",
            "CH",
            extra_options={"dhl_freight_sweden_payer_code": "DAP"},
            parcel=CONSUMER_PARCEL,
            extra_customs=DECLARED_VALUE,
        )

    def test_book_109_dk_parcel_shop(self):
        self.export("109", "DK", frozenset({provider_units.PartySubType.ParcelShop.value}))

    def refused_to_aland(self, standard: bool) -> None:
        """The connector refuses a customs handling service to Åland before booking.

        DHL rejected both services with 24003 when these cases booked
        (tests/dhl_freight_sweden/fixtures/sandbox/rejection-24003-112-se-fi-aland.json,
        rejection-24003-112-se-fi-aland-standard.json), so they no longer
        spend a booking.
        """
        customs, customs_options = export_customs("112", booking.ALAND, standard)
        payload: dict = dict(
            service="112",
            shipper=booking.SHIPPER,
            recipient=booking.ALAND,
            parcels=[booking.PARCEL],
            options=customs_options,
            **customs,
        )
        with self.assertRaises(create.AlandCustomsServiceError):
            self.gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))

    def test_book_112_fi_aland(self):
        self.refused_to_aland(standard=False)

    def test_book_112_fi_aland_standard_customs(self):
        # Product manual v5.26 lists "NO and Åland Islands (FI 22)" as the
        # valid countries of Customs handling - Standard (§6.6 p94).
        self.refused_to_aland(standard=True)

    def test_book_109_fi_aland_without_customs(self):
        # DHL booked this case before the connector required customs data
        # outside the EU VAT area (tests/dhl_freight_sweden/fixtures/sandbox/
        # booking-2906761917-109-se-fi-aland.json); it no longer spends a booking.
        payload = export_payload("109", booking.ALAND, ALAND_PARCEL_SHOP, with_customs=False)
        with self.assertRaises(create.CustomsInformationRequiredError):
            self.gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))

    def test_book_109_fi_aland_customs_without_service(self):
        # Product manual v5.26 makes customs proceedings mandatory for Åland
        # (§7.4 p162), and the connector refuses both customs handling
        # services there, so this sends the customs data alone.
        self.export("109", "FI", recipient=booking.ALAND, customs_service=False)

    def test_book_202_gb_northern_ireland_without_customs(self):
        self.export(
            "202",
            "GB",
            recipient=booking.BELFAST,
            with_customs=False,
            extra_options={"dhl_freight_sweden_payer_code": "DAP"},
        )

    def test_book_205_no_forced(self):
        # No probe has ever matched 205 (docs/concepts/destinations.md,
        # excluded postal codes);
        # like the 112 GB case, this books past the matches check to record
        # DHL's answer.
        self.export(
            "205",
            "NO",
            require_product_match=False,
            extra_options={"dhl_freight_sweden_payer_code": "DAP"},
        )
