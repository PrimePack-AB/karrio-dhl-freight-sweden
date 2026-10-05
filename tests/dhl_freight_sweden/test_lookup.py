"""DHL Freight lookup payload helper tests (connector-local capabilities)."""

import unittest

import karrio.core.errors as errors
import karrio.providers.dhl_freight_sweden.lookup as lookup


class TestDHLFreightSwedenLookup(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_guard_payload_keys_accepts_known_keys(self):
        self.assertIsNone(
            lookup.guard_payload_keys({"a": 1}, {"a", "b"}, "example")
        )

    def test_guard_payload_keys_rejects_unexpected_keys(self):
        with self.assertRaises(errors.ShippingSDKDetailedError) as context:
            lookup.guard_payload_keys(
                {"a": 1, "services": [], "piece": {}}, {"a", "b"}, "example"
            )

        exception = context.exception
        self.assertEqual(exception.code, "SHIPPING_SDK_FIELD_ERROR")
        self.assertIn("piece, services", str(exception))
        self.assertEqual(
            exception.details,
            {
                "piece": dict(code="unexpected", message="unexpected payload key"),
                "services": dict(code="unexpected", message="unexpected payload key"),
            },
        )

    def test_metric_measurements_default_to_kg_cm(self):
        self.assertEqual(
            lookup.to_metric_measurements(
                {"weight": 2.5, "length": 40, "width": 30, "height": 15}
            ),
            dict(weight=2.5, length=40.0, width=30.0, height=15.0, volume=0.018),
        )

    def test_metric_measurements_convert_lb_in(self):
        self.assertEqual(
            lookup.to_metric_measurements(
                {
                    "weight": 5,
                    "weight_unit": "LB",
                    "length": 10,
                    "width": 10,
                    "height": 10,
                    "dimension_unit": "IN",
                }
            ),
            dict(weight=2.27, length=25.4, width=25.4, height=25.4, volume=0.016387),
        )

    def test_metric_measurements_tolerate_irrelevant_parcel_fields(self):
        self.assertEqual(
            lookup.to_metric_measurements(
                {
                    "id": "parcel_1",
                    "weight": 1,
                    "weight_unit": "KG",
                    "packaging_type": "pallet",
                    "description": "Books",
                    "reference_number": "REF-1",
                    "options": {"insurance": 100},
                    "items": [
                        {"title": "Book", "quantity": 1, "weight": 1, "weight_unit": "KG"}
                    ],
                }
            ),
            dict(weight=1.0, length=None, width=None, height=None, volume=None),
        )

    def test_metric_measurements_omit_volume_without_all_dimensions(self):
        self.assertEqual(
            lookup.to_metric_measurements({"length": 40, "width": 30}),
            dict(weight=None, length=40.0, width=30.0, height=None, volume=None),
        )


if __name__ == "__main__":
    unittest.main()
