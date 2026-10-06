"""Shared sandbox booking step: budget, live booking, capture, and assertions."""

import typing
import unittest

import karrio.core.models as models
import karrio.lib as lib
import karrio.providers.dhl_freight_sweden.product_matches as product_matches
import karrio.providers.dhl_freight_sweden.service_points as service_points
import karrio.providers.dhl_freight_sweden.units as provider_units
import karrio.sdk as karrio
from . import harness

SHIPPER = {
    "company_name": "Test Shipper AB",
    "person_name": "Sven Svensson",
    "address_line1": "Kungsgatan 1",
    "city": "Stockholm",
    "postal_code": "11143",
    "country_code": "SE",
    "phone_number": "+46 8 123 456",
    "email": "shipper@example.se",
}

PARCEL = {
    "weight": 1.0,
    "length": 30.0,
    "width": 20.0,
    "height": 10.0,
    "weight_unit": "KG",
    "dimension_unit": "CM",
    "reference_number": "SANDBOX-TEST",
}


RECIPIENTS = {
    "SE": {
        "person_name": "Anna Andersson",
        "address_line1": "Drottninggatan 10",
        "city": "Stockholm",
        "postal_code": "11151",
        "country_code": "SE",
        "phone_number": "+46 70 123 45 67",
        "email": "anna.andersson@example.se",
        "residential": True,
    },
    "DK": {
        "person_name": "Mette Hansen",
        "address_line1": "Vesterbrogade 10",
        "city": "København V",
        "postal_code": "1620",
        "country_code": "DK",
        "phone_number": "+45 20 12 34 56",
        "email": "mette.hansen@example.dk",
        "residential": True,
    },
    "PL": {
        "person_name": "Jan Kowalski",
        "address_line1": "ul. Królewska 10",
        "city": "Kraków",
        "postal_code": "30-079",
        "country_code": "PL",
        "phone_number": "+48 600 000 000",
        "email": "jan.kowalski@example.pl",
        "residential": True,
    },
    "RO": {
        "person_name": "Ion Popescu",
        "address_line1": "Strada Lipscani 10",
        "city": "București",
        "postal_code": "030031",
        "country_code": "RO",
        "phone_number": "+40 721 000 000",
        "email": "ion.popescu@example.ro",
        "residential": True,
    },
    "HU": {
        "person_name": "Kovács Anna",
        "address_line1": "Váci utca 10",
        "city": "Budapest",
        "postal_code": "1052",
        "country_code": "HU",
        "phone_number": "+36 30 000 0000",
        "email": "anna.kovacs@example.hu",
        "residential": True,
    },
    "NO": {
        "person_name": "Ola Nordmann",
        "address_line1": "Karl Johans gate 10",
        "city": "Oslo",
        "postal_code": "0154",
        "country_code": "NO",
        "phone_number": "+47 400 00 000",
        "email": "ola.nordmann@example.no",
        "residential": True,
    },
    "FR": {
        "person_name": "Jean Dupont",
        "address_line1": "10 Rue de Rivoli",
        "city": "Paris",
        "postal_code": "75004",
        "country_code": "FR",
        "phone_number": "+33 6 12 34 56 78",
        "email": "jean.dupont@example.fr",
        "residential": True,
    },
    "CH": {
        "person_name": "Lukas Müller",
        "address_line1": "Bahnhofstrasse 10",
        "city": "Zürich",
        "postal_code": "8001",
        "country_code": "CH",
        "phone_number": "+41 79 123 45 67",
        "email": "lukas.mueller@example.ch",
        "residential": True,
    },
    "GB": {
        "person_name": "John Smith",
        "address_line1": "10 Oxford Street",
        "city": "London",
        "postal_code": "W1D 1AN",
        "country_code": "GB",
        "phone_number": "+44 7700 900123",
        "email": "john.smith@example.co.uk",
        "residential": True,
    },
}
# Recipients in special territories, under the parent country DHL serves
# them as (tests/dhl_freight_sweden/fixtures/sandbox/
# lookup-product-matches-se-fi-22100.json, lookup-product-matches-se-gb-bt11aa.json).
ALAND = {
    "person_name": "Erik Eriksson",
    "address_line1": "Torggatan 10",
    "city": "Mariehamn",
    "postal_code": "22100",
    "country_code": "FI",
    "phone_number": "+358 40 000 0000",
    "email": "erik.eriksson@example.ax",
    "residential": True,
}
BELFAST = {
    "person_name": "Siobhan Kelly",
    "address_line1": "10 Donegall Place",
    "city": "Belfast",
    "postal_code": "BT1 1AA",
    "country_code": "GB",
    "phone_number": "+44 7700 900456",
    "email": "siobhan.kelly@example.co.uk",
    "residential": True,
}
ADDRESS_FIELDS = ("street", "city", "postal_code", "country_code")
# Test shipments carry no goods subject to SENT monitoring, so the suite
# declares lanes to PL SENT free; the connector requires the declaration.
SENT_FREE = {"dhl_freight_sweden_sent_free": True}


def declaration_options(recipient: dict) -> dict:
    """Transport declaration options the suite makes for a lane from ``SHIPPER``."""
    return SENT_FREE if recipient["country_code"] == "PL" else {}


def offered_products(
    session: harness.Session, gateway, label: str, recipient: dict
) -> typing.Tuple[typing.List[str], typing.List[models.Message]]:
    """Product codes DHL matches for a parcel from ``SHIPPER`` to ``recipient``."""
    settings = harness.settings_of(gateway)
    request = product_matches.product_matches_request(
        dict(
            shipper=dict(
                postal_code=SHIPPER["postal_code"],
                country_code=SHIPPER["country_code"],
            ),
            recipient=dict(
                postal_code=recipient["postal_code"],
                country_code=recipient["country_code"],
            ),
            parcels=[PARCEL],
        ),
        settings,
    )
    try:
        products, messages = product_matches.parse_product_matches_response(
            harness.proxy_of(gateway).find_product_matches(request), settings
        )
    finally:
        session.capture(gateway, label)
    codes = [str(product.get("code")) for product in products]
    session.capture_parsed(label, dict(codes=codes, messages=lib.to_dict(messages)))
    return codes, messages


def sub_type(point: dict) -> str:
    return (
        provider_units.PartySubType.ParcelStation.value
        if point.get("type") == "locker"
        else provider_units.PartySubType.ParcelShop.value
    )


def nearest_service_point(
    session: harness.Session,
    gateway,
    label: str,
    product: str,
    recipient: dict,
    sub_types: typing.Optional[typing.AbstractSet[str]] = None,
) -> typing.Tuple[typing.Optional[dict], typing.List[models.Message]]:
    """The nearest point to ``recipient`` that can book ``product``.

    A candidate needs a service point id, a complete address, and a sub type
    the connector accepts for the product and destination country, narrowed
    to ``sub_types`` when given.
    """
    settings = harness.settings_of(gateway)
    country = recipient["country_code"]
    request = service_points.service_points_request(
        dict(
            address=dict(
                street=recipient["address_line1"],
                city=recipient["city"],
                postal_code=recipient["postal_code"],
                country_code=country,
            ),
            max_items=5,
            parcel=PARCEL,
        ),
        settings,
    )
    try:
        points, messages = service_points.parse_service_points_response(
            harness.proxy_of(gateway).find_service_points(request), settings
        )
    finally:
        session.capture(gateway, label)
    session.capture_parsed(label, dict(points=points, messages=lib.to_dict(messages)))

    accepted = provider_units.ACCESS_POINT_SUB_TYPES.get(product, {}).get(
        country, frozenset()
    )
    if sub_types is not None:
        accepted = accepted & sub_types
    candidate = next(
        (
            point
            for point in points
            if point.get("service_point_id")
            and all((point.get("address") or {}).get(f) for f in ADDRESS_FIELDS)
            and sub_type(point) in accepted
        ),
        None,
    )
    return candidate, messages


def service_point_options(point: dict) -> dict:
    address = point["address"]
    return {
        "dhl_freight_sweden_service_point": point["service_point_id"],
        "dhl_freight_sweden_service_point_type": sub_type(point),
        "dhl_freight_sweden_service_point_name": point.get("name"),
        "dhl_freight_sweden_service_point_street": address["street"],
        "dhl_freight_sweden_service_point_city": address["city"],
        "dhl_freight_sweden_service_point_postal_code": address["postal_code"],
        "dhl_freight_sweden_service_point_country_code": address["country_code"],
    }


def require_booking(
    test: unittest.TestCase, session: harness.Session, product: str, country: str
) -> None:
    """Skip unless the product and recipient country are selected and a booking attempt remains."""
    reason = harness.booking_skip_reason(session.config, product, country)
    if reason:
        test.skipTest(reason)
    if session.budget.attempts >= session.budget.limit:
        test.skipTest(
            f"booking budget exhausted ({session.budget.attempts} of "
            f"DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS={session.budget.limit} used)"
        )


def book(
    test: unittest.TestCase,
    session: harness.Session,
    gateway,
    product: str,
    payload: dict,
) -> models.ShipmentDetails:
    """Book ``payload`` once within the budget and assert a labelled shipment.

    The attempt is reserved before the call and logged to ``bookings.jsonl``
    whether or not DHL returns a shipment id, because sandbox bookings
    cannot be cancelled through the API.
    """
    require_booking(
        test, session, product, str(payload["recipient"]["country_code"]).upper()
    )
    if not session.budget.reserve():
        test.skipTest("booking budget exhausted")

    shipment: typing.Optional[models.ShipmentDetails] = None
    messages: typing.List[models.Message] = []
    try:
        shipment, messages = (
            karrio.Shipment.create(models.ShipmentRequest(**payload))
            .from_(gateway)
            .parse()
        )
    finally:
        session.log_booking(
            product, shipment.tracking_number if shipment else None, test.id()
        )
        session.capture(gateway, f"booking-{product}")
        session.capture_parsed(
            f"booking-{product}",
            dict(
                tracking_number=shipment.tracking_number if shipment else None,
                label_type=shipment.label_type if shipment else None,
                label_length=len(shipment.docs.label or "") if shipment else 0,
                messages=lib.to_dict(messages),
            ),
        )

    errors = [m for m in messages if m.level not in ("warning", "info")]
    test.assertEqual(lib.to_dict(errors), [])
    assert shipment is not None
    test.assertTrue(shipment.tracking_number)
    test.assertEqual(shipment.shipment_identifier, shipment.tracking_number)
    test.assertTrue(shipment.docs.label)
    return shipment
