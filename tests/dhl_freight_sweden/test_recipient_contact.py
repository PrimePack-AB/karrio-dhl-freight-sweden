"""DHL Freight (SE API Farm) party contact details required per product.

Product manual v5.26 makes the receiver's mobile phone number mandatory
for 118 (§5.16 p68), the consignee's phone number mandatory for 401
(§5.17 p72), the consignee's phone number and e-mail address mandatory for
601 (§5.19 p81), and the sender's phone number mandatory for 402 and 502
(§5.18 p76). The connector refuses such a booking before the booking
request when the party's phone_number or email is missing or blank, and
checks presence only.
"""

import unittest

import karrio.core.models as models
from karrio.providers.dhl_freight_sweden.shipment.create import (
    RecipientContactError,
    ShipperContactError,
)

from .fixture import as_list, detail_keys, gateway, serialize_request
from .test_shipment import _payload, _recipient_dk, _recipient_se, _shipper

_HEMLEVERANS = "dhl_freight_sweden_hemleverans_paket_b2c"
_HOME_DELIVERY_INTERNATIONAL = "dhl_freight_sweden_home_delivery_international_b2c"
_HOME_DELIVERY = "dhl_freight_sweden_home_delivery_b2c"
_HOME_DELIVERY_RETURNS = {
    "402": "dhl_freight_sweden_home_delivery_c2b",
    "502": "dhl_freight_sweden_home_delivery_c2b_502",
}
_RETURN_OPTIONS = {"dhl_freight_sweden_payer_code": "3"}


class TestDHLFreightRecipientContact(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _serialize(self, payload: dict) -> dict:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        return serialize_request(request)

    def _error(self, payload: dict) -> RecipientContactError:
        with self.assertRaises(RecipientContactError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def _party(self, serialized: dict, party_type: str) -> dict:
        return next(
            party
            for party in as_list(serialized["parties"])
            if party["type"] == party_type
        )

    def _consignee(self, serialized: dict) -> dict:
        return self._party(serialized, "Consignee")

    def test_118_without_phone_is_refused(self):
        for phone in (None, "", "   "):
            with self.subTest(phone=phone):
                error = self._error(
                    _payload(_HEMLEVERANS, {**_recipient_se, "phone_number": phone})
                )

                self.assertEqual(detail_keys(error), {"recipient.phone_number"})
                self.assertEqual(
                    (error.details or {})["recipient.phone_number"]["code"],
                    "required",
                )
                self.assertIn("118", str(error))

    def test_118_without_email_books(self):
        serialized = self._serialize(
            _payload(_HEMLEVERANS, {**_recipient_se, "email": None})
        )

        self.assertEqual(serialized["productCode"], "118")

    def test_118_with_phone_books(self):
        serialized = self._serialize(_payload(_HEMLEVERANS, _recipient_se))

        self.assertEqual(serialized["productCode"], "118")
        self.assertEqual(
            self._consignee(serialized)["phone"], _recipient_se["phone_number"]
        )

    def test_601_missing_contact_fields_are_refused_together(self):
        cases = [
            ({"phone_number": None}, {"recipient.phone_number"}),
            ({"email": None}, {"recipient.email"}),
            ({"phone_number": "", "email": " "}, {"recipient.phone_number", "recipient.email"}),
            (
                {"phone_number": None, "email": None},
                {"recipient.phone_number", "recipient.email"},
            ),
        ]

        for blanked, missing in cases:
            with self.subTest(blanked=blanked):
                error = self._error(
                    _payload(
                        _HOME_DELIVERY_INTERNATIONAL,
                        {**_recipient_dk, **blanked},
                        {"dhl_freight_sweden_payer_code": "DAP"},
                    )
                )

                self.assertEqual(detail_keys(error), missing)
                self.assertIn("601", str(error))
                for field in missing:
                    self.assertIn(field, str(error))

    def test_601_with_phone_and_email_books(self):
        serialized = self._serialize(
            _payload(
                _HOME_DELIVERY_INTERNATIONAL,
                _recipient_dk,
                {"dhl_freight_sweden_payer_code": "DAP"},
            )
        )
        consignee = self._consignee(serialized)

        self.assertEqual(serialized["productCode"], "601")
        self.assertEqual(
            (consignee["phone"], consignee["email"]),
            (_recipient_dk["phone_number"], _recipient_dk["email"]),
        )

    def test_401_without_phone_is_refused(self):
        for phone in (None, "", "   "):
            with self.subTest(phone=phone):
                error = self._error(
                    _payload(_HOME_DELIVERY, {**_recipient_se, "phone_number": phone})
                )

                self.assertEqual(detail_keys(error), {"recipient.phone_number"})
                self.assertEqual(
                    (error.details or {})["recipient.phone_number"]["code"],
                    "required",
                )
                self.assertEqual(
                    str(error),
                    "Product 401 requires the recipient's phone number; "
                    "missing recipient.phone_number",
                )

    def test_401_with_phone_books(self):
        serialized = self._serialize(
            _payload(_HOME_DELIVERY, {**_recipient_se, "email": None})
        )

        self.assertEqual(serialized["productCode"], "401")
        self.assertEqual(
            self._consignee(serialized)["phone"], _recipient_se["phone_number"]
        )

    def test_home_delivery_return_without_sender_phone_is_refused(self):
        for code, service in _HOME_DELIVERY_RETURNS.items():
            for phone in (None, "", "   "):
                with self.subTest(product=code, phone=phone):
                    with self.assertRaises(ShipperContactError) as context:
                        gateway.mapper.create_shipment_request(
                            models.ShipmentRequest(
                                **{
                                    **_payload(service, _recipient_se, _RETURN_OPTIONS),
                                    "shipper": {**_shipper, "phone_number": phone},
                                }
                            )
                        )
                    error = context.exception

                    self.assertEqual(detail_keys(error), {"shipper.phone_number"})
                    self.assertEqual(
                        (error.details or {})["shipper.phone_number"]["code"],
                        "required",
                    )
                    self.assertEqual(
                        str(error),
                        f"Product {code} requires the shipper's phone number; "
                        "missing shipper.phone_number",
                    )

    def test_home_delivery_return_with_sender_phone_books(self):
        for code, service in _HOME_DELIVERY_RETURNS.items():
            with self.subTest(product=code):
                serialized = self._serialize(
                    {
                        **_payload(
                            service,
                            {**_recipient_se, "phone_number": None, "email": None},
                            _RETURN_OPTIONS,
                        ),
                        "shipper": {**_shipper, "email": None},
                    }
                )

                self.assertEqual(serialized["productCode"], code)
                self.assertEqual(
                    self._party(serialized, "Consignor")["phone"],
                    _shipper["phone_number"],
                )

    def test_recipient_products_do_not_require_the_sender_phone(self):
        serialized = self._serialize(
            {
                **_payload(_HEMLEVERANS, _recipient_se),
                "shipper": {**_shipper, "phone_number": None},
            }
        )

        self.assertEqual(serialized["productCode"], "118")

    def test_other_products_without_contact_details_book(self):
        serialized = self._serialize(
            _payload(
                "dhl_freight_sweden_paket",
                {**_recipient_se, "phone_number": None, "email": None},
            )
            | {"shipper": {**_shipper, "phone_number": None, "email": None}}
        )

        self.assertEqual(serialized["productCode"], "102")


if __name__ == "__main__":
    unittest.main()
