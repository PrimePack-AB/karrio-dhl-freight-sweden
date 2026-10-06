"""The runnable request examples under ``examples/``.

The README quotes these examples, so each test pins the request an example
builds to the behaviour the README describes and, where a sandbox booking
exists, to the request DHL accepted. Every test runs with ``lib.request``
patched to fail, so an example that reached the network would fail here.
"""

import contextlib
import io
import json
import pathlib
import re
import runpy
import sys
import typing
import unittest
from unittest.mock import patch

import karrio.lib as lib
import karrio.providers.dhl_freight_sweden.service_points as service_points
from examples import domestic_parcel, export_to_switzerland, service_point_parcel
from examples.offline import offline_gateway, transport_instruction

from .fixture import as_dict, proxy_of, settings_of

EVIDENCE_DIR = pathlib.Path(__file__).parent / "fixtures" / "sandbox"
REPO = pathlib.Path(__file__).resolve().parents[2]
QUOTED_BLOCK = re.compile(
    r"<!-- quoted from (?P<path>\S+) -->\n```python\n(?P<code>.*?)\n```", re.S
)


def _stripped_lines(text: str) -> typing.List[str]:
    return [line.strip() for line in text.strip().split("\n")]


def _contains_run(haystack: typing.List[str], needle: typing.List[str]) -> bool:
    return any(
        haystack[start : start + len(needle)] == needle
        for start in range(len(haystack) - len(needle) + 1)
    )


def _exchange(evidence: str, endpoint: str) -> typing.Dict[str, typing.Any]:
    data = json.loads((EVIDENCE_DIR / evidence).read_text())
    return next(e for e in data["exchanges"] if endpoint in e["endpoint"])


def _booked_request(evidence: str) -> typing.Dict[str, typing.Any]:
    return _exchange(evidence, "sendtransportinstruction")["request"]


def _parties(body: dict, party_type: str) -> typing.List[dict]:
    return [party for party in body["parties"] if party["type"] == party_type]


def _without(mapping: dict, *keys: str) -> dict:
    return {key: value for key, value in mapping.items() if key not in keys}


class TestExamples(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        network = patch(
            "karrio.lib.request",
            side_effect=AssertionError("an example reached the network"),
        )
        network.start()
        self.addCleanup(network.stop)

    def test_domestic_parcel_books_102_home_delivery(self):
        body = transport_instruction(domestic_parcel.shipment_request())

        self.assertEqual(body["productCode"], "102")
        self.assertEqual(body["payerCode"], {"code": "1"})
        self.assertEqual(_parties(body, "Consignor")[0]["id"], "YOUR_ACCOUNT_NUMBER")
        self.assertEqual(_parties(body, "AccessPoint"), [])
        self.assertNotIn("customsInformation", body)

    def test_service_point_parcel_matches_booking_2906761230(self):
        body = transport_instruction(service_point_parcel.shipment_request())
        booked = _booked_request("booking-2906761230-103-se-se.json")

        self.assertEqual(body["productCode"], booked["productCode"])
        self.assertEqual(body["payerCode"], booked["payerCode"])
        self.assertEqual(
            _parties(body, "AccessPoint"), _parties(booked, "AccessPoint")
        )

    def test_service_point_matches_lookup_normalisation(self):
        lookup = _exchange(
            "booking-2906761230-103-se-se.json", "findnearestservicepoints"
        )
        gateway = offline_gateway()
        with patch("karrio.lib.request", return_value=json.dumps(lookup["response"])):
            points, _ = service_points.parse_service_points_response(
                proxy_of(gateway).find_service_points(
                    service_points.service_points_request(
                        {"address": {"postal_code": "11151", "country_code": "SE"}},
                        settings_of(gateway),
                    )
                ),
                settings_of(gateway),
            )

        first = as_dict(points[0])
        self.assertEqual(
            {key: first.get(key) for key in service_point_parcel.SERVICE_POINT},
            service_point_parcel.SERVICE_POINT,
        )

    def test_service_point_locker_books_as_parcel_station(self):
        options = service_point_parcel.service_point_options(
            {**service_point_parcel.SERVICE_POINT, "type": "locker"}
        )

        self.assertEqual(
            options["dhl_freight_sweden_service_point_type"], "ParcelStation"
        )

    def test_export_to_switzerland_matches_booking_2906762477(self):
        body = transport_instruction(export_to_switzerland.shipment_request())
        booked = _booked_request("booking-2906762477-601-se-ch.json")

        self.assertEqual(body["productCode"], booked["productCode"])
        self.assertEqual(body["payerCode"], booked["payerCode"])
        self.assertEqual(body["additionalServices"], booked["additionalServices"])
        self.assertEqual(
            body["customsInformation"]["customsCommodities"],
            booked["customsInformation"]["customsCommodities"],
        )
        self.assertEqual(
            [_without(d, "id") for d in body["customsInformation"]["customsDocuments"]],
            [_without(d, "id") for d in booked["customsInformation"]["customsDocuments"]],
        )
        self.assertEqual(
            [_without(p, "marksAndNumbers") for p in body["pieces"]],
            [_without(p, "marksAndNumbers") for p in booked["pieces"]],
        )

    def test_scripts_print_their_transport_instruction(self):
        for module in (domestic_parcel, service_point_parcel, export_to_switzerland):
            with self.subTest(module=module.__name__):
                stdout = io.StringIO()
                with patch.dict(sys.modules), contextlib.redirect_stdout(stdout):
                    sys.modules.pop(module.__name__)
                    runpy.run_module(module.__name__, run_name="__main__")

                self.assertEqual(
                    json.loads(stdout.getvalue()),
                    lib.to_dict(transport_instruction(module.shipment_request())),
                )

    def test_readme_quotes_the_examples_verbatim(self):
        quotes = list(QUOTED_BLOCK.finditer((REPO / "README.md").read_text()))

        self.assertEqual(
            sorted({quote["path"] for quote in quotes}),
            [
                "examples/domestic_parcel.py",
                "examples/export_to_switzerland.py",
                "examples/service_point_parcel.py",
            ],
        )
        for quote in quotes:
            with self.subTest(path=quote["path"]):
                source = (REPO / quote["path"]).read_text()
                self.assertTrue(
                    _contains_run(_stripped_lines(source), _stripped_lines(quote["code"]))
                )


if __name__ == "__main__":
    unittest.main()
