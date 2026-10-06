"""DHL Freight (SE API Farm) VAT/TIN requirement for lanes to or from GR.

Product manual v5.26 makes a VAT number/TIN mandatory for all parties in
the shipment information of 202 (§5.4 p22), SPI (§5.11 p51), and 601
(§5.19 p81) for shipments to or from Greece (GR). The connector transmits
the shipper as Consignor and the recipient as Consignee, each with its
federal_tax_id, else state_tax_id, as vatEoriSocialSecurityNumber.
"""

import typing
import unittest

import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import PartyTaxIdError

from .fixture import as_list, detail_keys, gateway, serialize_request
from .test_shipment import _payload, _recipient_de, _recipient_se, _shipper


class TestDHLFreightGreekTaxIds(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _serialize(self, payload: dict) -> dict:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        return serialize_request(request)

    def _error(self, payload: dict) -> PartyTaxIdError:
        with self.assertRaises(PartyTaxIdError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def test_lanes_to_gr_without_tax_ids_fail(self):
        for service in GreekTaxIdServices:
            with self.subTest(service=service):
                error = self._error(_to_gr(service, _shipper, _recipient_gr))

                self.assertEqual(
                    detail_keys(error),
                    {"shipper.federal_tax_id", "recipient.federal_tax_id"},
                )
                self.assertIn("GR", str(error))

    def test_lanes_to_gr_name_only_the_missing_party(self):
        cases = [
            ("shipper.federal_tax_id", _shipper, _recipient_gr_with_tax_id),
            ("recipient.federal_tax_id", _shipper_with_tax_id, _recipient_gr),
            (
                "recipient.federal_tax_id",
                _shipper_with_tax_id,
                {**_recipient_gr, "federal_tax_id": "  "},
            ),
        ]

        for missing, shipper, recipient in cases:
            with self.subTest(missing=missing, recipient=recipient.get("federal_tax_id")):
                error = self._error(
                    _to_gr("dhl_freight_sweden_road_freight_standard", shipper, recipient)
                )

                self.assertEqual(detail_keys(error), {missing})

    def test_lanes_from_gr_without_tax_ids_fail(self):
        payload = {
            **_payload(
                "dhl_freight_sweden_road_freight_standard",
                _recipient_se,
                {"dhl_freight_sweden_payer_code": "EXW"},
            ),
            "shipper": _shipper_gr,
        }

        error = self._error(payload)

        self.assertEqual(
            detail_keys(error), {"shipper.federal_tax_id", "recipient.federal_tax_id"}
        )

    def test_state_tax_id_satisfies_the_requirement(self):
        serialized = self._serialize(
            _to_gr(
                "dhl_freight_sweden_road_freight_standard",
                {**_shipper, "state_tax_id": "SE556000000001"},
                _recipient_gr_with_tax_id,
            )
        )

        self.assertEqual(
            as_list(serialized["parties"])[0]["vatEoriSocialSecurityNumber"],
            "SE556000000001",
        )

    def test_lanes_to_gr_with_tax_ids_send_them_per_party(self):
        for service in GreekTaxIdServices:
            with self.subTest(service=service):
                serialized = self._serialize(
                    _to_gr(service, _shipper_with_tax_id, _recipient_gr_with_tax_id)
                )

                self.assertEqual(
                    [
                        (party["type"], party["vatEoriSocialSecurityNumber"])
                        for party in as_list(serialized["parties"])
                    ],
                    [("Consignor", "SE556000000001"), ("Consignee", "EL123456789")],
                )

    def test_other_products_to_gr_do_not_require_tax_ids(self):
        serialized = self._serialize(
            _to_gr("dhl_freight_sweden_road_freight_direct", _shipper, _recipient_gr)
        )

        self.assertEqual(serialized["productCode"], "205")

    def test_lanes_without_gr_do_not_require_tax_ids(self):
        serialized = self._serialize(
            _payload(
                "dhl_freight_sweden_road_freight_standard",
                _recipient_de,
                {"dhl_freight_sweden_payer_code": "DAP"},
            )
        )

        self.assertEqual(serialized["productCode"], "202")


def _to_gr(service: str, shipper: dict, recipient: dict, options: typing.Optional[dict] = None) -> dict:
    return {
        **_payload(
            service,
            recipient,
            {"dhl_freight_sweden_payer_code": "DAP", **(options or {})},
        ),
        "shipper": shipper,
    }


GreekTaxIdServices = [
    "dhl_freight_sweden_road_freight_standard",
    "dhl_freight_sweden_standard_pallet_international",
    "dhl_freight_sweden_home_delivery_international_b2c",
]

_recipient_gr = {
    **_recipient_se,
    "city": "Athina",
    "postal_code": "10431",
    "country_code": "GR",
}
_recipient_gr_with_tax_id = {**_recipient_gr, "federal_tax_id": "EL123456789"}
_shipper_with_tax_id = {**_shipper, "federal_tax_id": "SE556000000001"}
_shipper_gr = {
    **_recipient_gr,
    "company_name": "Test Shipper AE",
    "person_name": "Maria Papadopoulou",
}


if __name__ == "__main__":
    unittest.main()
