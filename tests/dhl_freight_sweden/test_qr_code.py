"""DHL Freight (SE API Farm) QR code print option for Parcel Return Connect.

Product manual v5.26 §5.15 p65 offers a QR code for 107 through the print
API selection "qrCode": true, valid for countries BE, BG, CZ, DE, ES, LU,
and PT, the countries the return shipment is sent from.
"""

import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.lib as lib
from karrio.providers.dhl_freight_sweden.shipment.create import QrCodeEligibilityError

from .fixture import as_dict, detail_keys, gateway, proxy_of
from .test_shipment import (
    BookingResponse102,
    PrintResponse,
    _payload,
    _recipient_se,
    _shipper,
)


class TestDHLFreightQrCode(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _print_options(self, payload: dict) -> dict:
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(**payload)
        )
        return as_dict(request.ctx["print_options"])

    def _error(self, payload: dict) -> QrCodeEligibilityError:
        with self.assertRaises(QrCodeEligibilityError) as context:
            gateway.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def test_107_from_qr_code_countries_prints_a_qr_code(self):
        for country in ["BE", "BG", "CZ", "DE", "ES", "LU", "PT"]:
            with self.subTest(country=country):
                print_options = self._print_options(
                    _return(country, {"dhl_freight_sweden_qr_code": True})
                )

                self.assertEqual(
                    print_options,
                    {
                        "label": True,
                        "qrCode": True,
                        "pageOptions": {"pageType": "Label"},
                    },
                )

    def test_qr_code_is_sent_on_the_print_by_id_request(self):
        # karrio.Shipment.create rejects a shipper country other than the
        # account country (SHIPPING_SDK_ORIGIN_NOT_SERVICED_ERROR), so the
        # return lane is driven through the gateway's mapper and proxy.
        request = gateway.mapper.create_shipment_request(
            models.ShipmentRequest(
                **_return("DE", {"dhl_freight_sweden_qr_code": True})
            )
        )
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.side_effect = [BookingResponse102, PrintResponse]
            proxy_of(gateway).create_shipment(request)

        printed = as_dict(lib.to_dict(mock.call_args_list[1].kwargs["data"]))
        self.assertEqual(as_dict(printed["options"])["qrCode"], True)

    def test_without_the_option_no_qr_code_is_requested(self):
        for options in [{}, {"dhl_freight_sweden_qr_code": False}]:
            with self.subTest(options=options):
                print_options = self._print_options(_return("DE", options))

                self.assertNotIn("qrCode", print_options)

    def test_107_from_other_countries_fails(self):
        for country in ["AT", "FR", "NL"]:
            with self.subTest(country=country):
                error = self._error(
                    _return(country, {"dhl_freight_sweden_qr_code": True})
                )

                self.assertEqual(detail_keys(error), {"dhl_freight_sweden_qr_code"})
                self.assertIn(country, str(error))

    def test_other_products_fail(self):
        error = self._error(
            _payload(
                "dhl_freight_sweden_paket",
                _recipient_se,
                {"dhl_freight_sweden_qr_code": True},
            )
        )

        self.assertEqual(detail_keys(error), {"dhl_freight_sweden_qr_code"})
        self.assertIn("102", str(error))


def _return(country: str, options: dict) -> dict:
    return {
        **_payload("dhl_freight_sweden_parcel_return_connect_c2b", _recipient_se, options),
        "shipper": {
            **_shipper,
            "company_name": "Test Consumer",
            "city": "Return City",
            "postal_code": "10115",
            "country_code": country,
        },
    }


if __name__ == "__main__":
    unittest.main()
