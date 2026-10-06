"""A DHL Paket (102) parcel from Stockholm to a home address in Stockholm.

``python -m examples.domestic_parcel`` prints the TransportInstruction body.
To book the shipment, pass the same request to
``karrio.Shipment.create(request).from_(gateway).parse()`` with a gateway that
holds your client key and account number.
"""

import karrio.core.models as models

from examples.offline import print_transport_instruction


def shipment_request() -> models.ShipmentRequest:
    return models.ShipmentRequest(
        service="dhl_freight_sweden_paket",
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
        reference="ORDER-1001",
    )


if __name__ == "__main__":
    print_transport_instruction(shipment_request())
