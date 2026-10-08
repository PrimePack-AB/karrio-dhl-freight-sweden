"""DHL Freight (SE API Farm) joint declaration destinations.

Product manual v5.26 lists NO as the only valid country of Customs, joint
declaration (§6.8 p98). Product matches on account 116768 list
customsJointDeclaration among 601's customs services to CH (tests/
dhl_freight_sweden/fixtures/sandbox/lookup-product-matches-se-ch-8001.json),
so the connector accepts the service to NO and CH, compared after the
territory-to-parent mapping, and refuses it to any other destination outside
the EU VAT area. Within the EU VAT area customs services are dropped, not
validated.
"""

import unittest

import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import (
    JointDeclarationDestinationError,
)

from .fixture import detail_keys, gateway, serialize_request
from .test_shipment import Customs, _payload, _recipient_se

JOINT_DECLARATION = {
    "dhl_freight_sweden_customs_joint_declaration": True,
    "dhl_freight_sweden_customs_joint_declaration_id": "SFID-0001",
    "dhl_freight_sweden_payer_code": "DDP",
}

ADDRESSES = {
    "NO": ("Oslo", "0154"),
    "CH": ("Zurich", "8001"),
    "GB": ("London", "SW1A 1AA"),
    "IM": ("Douglas", "IM1 1AA"),
    "AX": ("Mariehamn", "22100"),
    "UA": ("Kyiv", "01001"),
    "DE": ("Berlin", "10115"),
}


def _recipient(country: str) -> dict:
    city, postal_code = ADDRESSES[country]
    return {**_recipient_se, "city": city, "postal_code": postal_code, "country_code": country}


def _request(country: str):
    payload = {
        **_payload("dhl_freight_sweden_road_freight_standard", _recipient(country), JOINT_DECLARATION),
        "customs": Customs,
    }
    return gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))


class TestDHLFreightJointDeclarationDestinations(unittest.TestCase):
    def test_joint_declaration_to_norway_and_switzerland_is_sent(self):
        for country in ["NO", "CH"]:
            with self.subTest(country=country):
                serialized = serialize_request(_request(country))

                self.assertEqual(
                    serialized["additionalServices"],
                    {"customsJointDeclaration": {"sfid": "SFID-0001"}},
                )

    def test_joint_declaration_elsewhere_outside_the_eu_vat_area_fails(self):
        for country, sent_as in [("GB", "GB"), ("IM", "GB"), ("AX", "FI"), ("UA", "UA")]:
            with self.subTest(country=country):
                with self.assertRaises(JointDeclarationDestinationError) as context:
                    _request(country)

                self.assertEqual(
                    detail_keys(context.exception),
                    {"dhl_freight_sweden_customs_joint_declaration"},
                )
                self.assertEqual(
                    str(context.exception),
                    "Customs, joint declaration is valid only to NO, the manual's only "
                    "valid country (§6.8 p98), and CH, which product matches offer; "
                    f"got recipient country {sent_as}",
                )

    def test_joint_declaration_within_the_eu_vat_area_is_dropped(self):
        serialized = serialize_request(_request("DE"))

        self.assertNotIn("customsJointDeclaration", serialized.get("additionalServices") or {})


if __name__ == "__main__":
    unittest.main()
