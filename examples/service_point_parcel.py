"""A Service Point B2C (103) parcel to a DHL service point in Stockholm.

``SERVICE_POINT`` has the shape that
``service_points.parse_service_points_response`` returns for each point; its
values are those of point SE-982000 in sandbox booking 2906761230
(tests/dhl_freight_sweden/fixtures/sandbox/booking-2906761230-103-se-se.json).
``python -m examples.service_point_parcel`` prints the TransportInstruction
body; book it with ``karrio.Shipment.create(request).from_(gateway).parse()``.
"""

import typing

import karrio.core.models as models

from examples.offline import print_transport_instruction

SERVICE_POINT: typing.Dict[str, typing.Any] = {
    "id": "SE-982000",
    "service_point_id": "SE-982000",
    "name": "H.T. ROSIS GODIS & TOBAK T-BANEPLAN",
    "type": "servicepoint",
    "address": {
        "street": "SVEAVÄGEN 20",
        "city": "STOCKHOLM",
        "postal_code": "11157",
        "country_code": "SE",
    },
}


def service_point_options(point: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
    """The booking options that address the shipment to ``point``.

    DHL books a ``locker`` as a ParcelStation and every other location type
    as a ParcelShop.
    """
    address = point["address"]
    return {
        "dhl_freight_sweden_service_point": point["service_point_id"],
        "dhl_freight_sweden_service_point_type": (
            "ParcelStation" if point["type"] == "locker" else "ParcelShop"
        ),
        "dhl_freight_sweden_service_point_name": point["name"],
        "dhl_freight_sweden_service_point_street": address["street"],
        "dhl_freight_sweden_service_point_city": address["city"],
        "dhl_freight_sweden_service_point_postal_code": address["postal_code"],
        "dhl_freight_sweden_service_point_country_code": address["country_code"],
    }


def shipment_request(
    point: typing.Dict[str, typing.Any] = SERVICE_POINT,
) -> models.ShipmentRequest:
    return models.ShipmentRequest(
        service="dhl_freight_sweden_service_point_b2c",
        shipper=models.Address(
            company_name="Example Shop AB",
            person_name="Sven Svensson",
            address_line1="Kungsgatan 1",
            city="Stockholm",
            postal_code="11143",
            country_code="SE",
            phone_number="+46 8 123 456",
            email="orders@example.se",
        ),
        recipient=models.Address(
            person_name="Anna Andersson",
            address_line1="Drottninggatan 10",
            city="Stockholm",
            postal_code="11151",
            country_code="SE",
            phone_number="+46 70 123 45 67",
            email="anna.andersson@example.se",
            residential=True,
        ),
        parcels=[
            models.Parcel(
                weight=1.0,
                length=30.0,
                width=20.0,
                height=10.0,
                weight_unit="KG",
                dimension_unit="CM",
            )
        ],
        options=service_point_options(point),
        reference="ORDER-1002",
    )


if __name__ == "__main__":
    print_transport_instruction(shipment_request())
