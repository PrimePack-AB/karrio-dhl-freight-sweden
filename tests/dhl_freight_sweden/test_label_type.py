"""DHL Freight (SE API Farm) label type validation.

The Print API (vendor/se-api-farm/print-api-2.10.0.json) has no document
format parameter, and every sandbox label in fixtures/sandbox/label-*.json
is a PDF, so the connector refuses any other requested label type before
booking. The request's label_type outranks the connection config's.
"""

import unittest
from unittest.mock import patch

import karrio.core.models as models
import karrio.sdk as karrio
from karrio.providers.dhl_freight_sweden.shipment.create import LabelTypeError

from .fixture import _gateway, detail_keys, gateway, zpl_gateway
from .test_shipment import (
    BookingResponse102,
    LabelBase64,
    PlainTextPrintResponse,
    PrintResponse,
    ShipmentPayload102,
)

pdf_lower_gateway = _gateway({"label_type": "pdf"})


class TestDHLFreightLabelType(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _error(self, payload: dict, connection=gateway) -> LabelTypeError:
        with self.assertRaises(LabelTypeError) as context:
            connection.mapper.create_shipment_request(models.ShipmentRequest(**payload))
        return context.exception

    def _book(self, payload: dict, connection=gateway, printed=PrintResponse):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            mock.side_effect = [BookingResponse102, printed]
            details, messages = (
                karrio.Shipment.create(models.ShipmentRequest(**payload))
                .from_(connection)
                .parse()
            )
        return details, messages, mock

    def test_request_zpl_fails_without_sending_a_request(self):
        with patch("karrio.mappers.dhl_freight_sweden.proxy.lib.request") as mock:
            details, messages = (
                karrio.Shipment.create(
                    models.ShipmentRequest(**{**ShipmentPayload102, "label_type": "ZPL"})
                )
                .from_(gateway)
                .parse()
            )

        mock.assert_not_called()
        self.assertIsNone(details)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].code, "SHIPPING_SDK_FIELD_ERROR")
        self.assertEqual(set(messages[0].details or {}), {"label_type"})
        self.assertIn("ZPL", messages[0].message)
        self.assertIn("PDF", messages[0].message)

    def test_request_label_type_other_than_pdf_fails(self):
        for label_type in ["ZPL", "zpl", "Zpl", "PNG", "ZPL_203"]:
            with self.subTest(label_type=label_type):
                error = self._error({**ShipmentPayload102, "label_type": label_type})

                self.assertEqual(detail_keys(error), {"label_type"})
                self.assertIn(label_type, str(error))

    def test_request_pdf_books_a_pdf_label(self):
        for label_type in ["PDF", "pdf"]:
            with self.subTest(label_type=label_type):
                details, messages, mock = self._book(
                    {**ShipmentPayload102, "label_type": label_type}
                )

                self.assertEqual(mock.call_count, 2)
                self.assertEqual(messages, [])
                assert details is not None
                self.assertEqual(details.label_type, "PDF")
                self.assertEqual(details.docs.label, LabelBase64)

    def test_unset_label_type_books_a_pdf_label(self):
        details, messages, mock = self._book(ShipmentPayload102)

        self.assertEqual(mock.call_count, 2)
        self.assertEqual(messages, [])
        assert details is not None
        self.assertEqual(details.label_type, "PDF")

    def test_config_zpl_fails_when_the_request_sets_no_label_type(self):
        error = self._error(ShipmentPayload102, zpl_gateway)

        self.assertEqual(detail_keys(error), {"config.label_type"})
        self.assertIn("ZPL", str(error))

    def test_config_lower_case_pdf_books(self):
        details, messages, _ = self._book(ShipmentPayload102, pdf_lower_gateway)

        self.assertEqual(messages, [])
        assert details is not None
        self.assertEqual(details.label_type, "PDF")

    def test_request_pdf_outranks_config_zpl(self):
        details, messages, _ = self._book(
            {**ShipmentPayload102, "label_type": "PDF"}, zpl_gateway
        )

        self.assertEqual(messages, [])
        assert details is not None
        self.assertEqual(details.label_type, "PDF")

    def test_unidentified_document_is_declared_pdf_despite_config_zpl(self):
        details, messages, _ = self._book(
            {**ShipmentPayload102, "label_type": "PDF"},
            zpl_gateway,
            PlainTextPrintResponse,
        )

        self.assertEqual(messages, [])
        assert details is not None
        self.assertEqual(details.label_type, "PDF")

    def test_request_zpl_outranks_config_pdf(self):
        error = self._error(
            {**ShipmentPayload102, "label_type": "ZPL"}, pdf_lower_gateway
        )

        self.assertEqual(detail_keys(error), {"label_type"})
