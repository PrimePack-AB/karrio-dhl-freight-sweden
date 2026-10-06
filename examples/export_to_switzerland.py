"""A Home Delivery International B2C (601) parcel sold to a consumer in Zürich.

The request mirrors sandbox booking 2906762477 on account 116768: payer code
DAP, customs handling full service, and a commercial invoice whose amount is
the declared value
(tests/dhl_freight_sweden/fixtures/sandbox/booking-2906762477-601-se-ch.json).
``python -m examples.export_to_switzerland`` prints the TransportInstruction
body; book it with ``karrio.Shipment.create(request).from_(gateway).parse()``.
"""

import karrio.core.models as models

from examples.offline import print_transport_instruction


def shipment_request() -> models.ShipmentRequest:
    return models.ShipmentRequest(
        service="dhl_freight_sweden_home_delivery_international_b2c",
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
            person_name="Lukas Müller",
            address_line1="Bahnhofstrasse 10",
            city="Zürich",
            postal_code="8001",
            country_code="CH",
            phone_number="+41 79 123 45 67",
            email="lukas.mueller@example.ch",
            residential=True,
        ),
        parcels=[
            models.Parcel(
                weight=2.0,
                length=30.0,
                width=20.0,
                height=15.0,
                weight_unit="KG",
                dimension_unit="CM",
            )
        ],
        options={
            "dhl_freight_sweden_payer_code": "DAP",
            "dhl_freight_sweden_customs_handling_full_service": True,
        },
        customs=models.Customs(
            incoterm="DAP",
            invoice="INV-1003",
            invoice_date="2026-10-06",
            content_type="merchandise",
            commercial_invoice=True,
            duty=models.Duty(paid_by="recipient", currency="SEK", declared_value=200),
            commodities=[
                models.Commodity(
                    title="Cotton T-shirt",
                    description="Cotton T-shirt",
                    quantity=1,
                    weight=0.5,
                    weight_unit="KG",
                    value_amount=200,
                    value_currency="SEK",
                    origin_country="SE",
                    hs_code="610910",
                )
            ],
        ),
        reference="ORDER-1003",
    )


if __name__ == "__main__":
    print_transport_instruction(shipment_request())
