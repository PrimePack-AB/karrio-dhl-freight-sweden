"""Sandbox segment ``booking-declarations``: SENT, EKAER, and UIT declarations on 601.

Each test books 601 (payer code DAP) from SE to PL, HU, or RO. Two cases declare
a transport declaration that is not free: to HU with an EKAER number, which
sends ``EKAER_FREE`` "false" and ``EKAER_NUMBER``, and to RO with
``dhl_freight_sweden_uit_free`` false and no number, which sends
``UIT_FREE`` "false" alone. Two cases carry placeholder identifiers: to PL
with a SENT reference and carrier key, which sends ``SENT_FREE`` "false",
``SENT_REF``, and ``SENT_CARKEY``, and to RO with a UIT number, which sends
``UIT_FREE`` "false" and ``UIT_NUMBER``. Three cases set no declaration
option, so the connector's default applies and sends ``SENT_FREE`` "true",
or below 500 kg ``EKAER_FREE`` "true" or ``UIT_FREE`` "true", alone. Every
case asserts the serialized request before booking. Before spending a
booking each test checks for free that product matches offer 601 for the
lane, and skips otherwise.
"""

import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib

from . import booking, harness

PRODUCT = "601"
# Sandbox-only placeholder within the EKAER number format (AN..20); it is
# not issued by the Hungarian tax authority.
EKAER_NUMBER = "E0000SANDBOX0001"
# Sandbox-only placeholders within the SENT reference and carrier key
# (AN..20) and UIT code (AN..19) formats of product manual v5.26 §5.19 p82;
# none is issued by the Polish or Romanian tax authority.
SENT_REF = "SENT20261008000001"
SENT_CARKEY = "SANDBOXCARKEY0001"
UIT_NUMBER = "0000-0000-0000-0001"
DECLARATIONS = {
    "HU": {"dhl_freight_sweden_ekaer_number": EKAER_NUMBER},
    "RO": {"dhl_freight_sweden_uit_free": False},
}
DECLARATION_INFORMATION = {
    "HU": [
        {"code": "EKAER_FREE", "stringValue": "false"},
        {"code": "EKAER_NUMBER", "stringValue": EKAER_NUMBER},
    ],
    "RO": [{"code": "UIT_FREE", "stringValue": "false"}],
}
IDENTIFIERS = {
    "PL": {
        "dhl_freight_sweden_sent_ref": SENT_REF,
        "dhl_freight_sweden_sent_carkey": SENT_CARKEY,
    },
    "RO": {"dhl_freight_sweden_uit_number": UIT_NUMBER},
}
IDENTIFIER_INFORMATION = {
    "PL": [
        {"code": "SENT_FREE", "stringValue": "false"},
        {"code": "SENT_REF", "stringValue": SENT_REF},
        {"code": "SENT_CARKEY", "stringValue": SENT_CARKEY},
    ],
    "RO": [
        {"code": "UIT_FREE", "stringValue": "false"},
        {"code": "UIT_NUMBER", "stringValue": UIT_NUMBER},
    ],
}
DEFAULT_INFORMATION = {
    "PL": [{"code": "SENT_FREE", "stringValue": "true"}],
    "HU": [{"code": "EKAER_FREE", "stringValue": "true"}],
    "RO": [{"code": "UIT_FREE", "stringValue": "true"}],
}


def payload(country: str, declaration: typing.Mapping[str, typing.Any]) -> dict:
    """A 601 booking from ``SHIPPER`` to ``country`` with payer code DAP and ``declaration``."""
    return dict(
        service=PRODUCT,
        shipper=booking.SHIPPER,
        recipient=booking.RECIPIENTS[country],
        parcels=[booking.PARCEL],
        options={"dhl_freight_sweden_payer_code": "DAP", **declaration},
    )


class TestSandboxBookingDeclarations(unittest.TestCase):
    session: harness.Session

    @classmethod
    def setUpClass(cls):
        cls.session = harness.require_segment("booking-declarations")
        cls.gateway = cls.session.gateway()

    def setUp(self):
        self.maxDiff = None

    def declare(
        self,
        country: str,
        declaration: typing.Mapping[str, typing.Any],
        expected_information: typing.List[dict],
    ):
        booking.require_booking(self, self.session, PRODUCT, country)
        shipment = payload(country, declaration)

        serialized = lib.to_dict(
            self.gateway.mapper.create_shipment_request(
                models.ShipmentRequest(**shipment)
            ).serialize()
        )
        assert isinstance(serialized, dict)
        self.assertEqual(serialized.get("additionalInformation"), expected_information)

        codes, messages = booking.offered_products(
            self.session,
            self.gateway,
            f"product-matches-{PRODUCT}-{country.lower()}",
            booking.RECIPIENTS[country],
        )
        if messages:
            self.skipTest(
                f"product matches pre-check for SE to {country} failed: "
                f"{[message.message for message in messages]}"
            )
        if PRODUCT not in codes:
            self.skipTest(f"product matches do not offer {PRODUCT} from SE to {country}")

        booking.book(self, self.session, self.gateway, PRODUCT, shipment)

    def test_book_601_hu_with_ekaer_number(self):
        self.declare("HU", DECLARATIONS["HU"], DECLARATION_INFORMATION["HU"])

    def test_book_601_ro_not_uit_free_without_number(self):
        self.declare("RO", DECLARATIONS["RO"], DECLARATION_INFORMATION["RO"])

    def test_book_601_hu_default_ekaer_free(self):
        self.declare("HU", {}, DEFAULT_INFORMATION["HU"])

    def test_book_601_ro_default_uit_free(self):
        self.declare("RO", {}, DEFAULT_INFORMATION["RO"])

    def test_book_601_pl_default_sent_free(self):
        self.declare("PL", {}, DEFAULT_INFORMATION["PL"])

    def test_book_601_pl_sent_identifiers(self):
        self.declare("PL", IDENTIFIERS["PL"], IDENTIFIER_INFORMATION["PL"])

    def test_book_601_ro_uit_number(self):
        self.declare("RO", IDENTIFIERS["RO"], IDENTIFIER_INFORMATION["RO"])
