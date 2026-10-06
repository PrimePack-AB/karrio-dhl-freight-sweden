"""Build the committed sandbox evidence files from the out-of-repo captures.

The captures stay under the XDG state directory, outside the repository.
This module reads them, drops the client key and the response headers,
replaces label base64 with a length marker, and writes one evidence file
per finding into ``tests/dhl_freight_sweden/fixtures/sandbox/``.
Every exchange records its capture path relative to the state directory
and the capture's sha256, so the same captures always rebuild the same
bytes, and the committed files can be checked against the originals.

Run it from the repository root::

    .venv/bin/python -m sandbox_tests.dhl_freight_sweden.evidence
    .venv/bin/python -m sandbox_tests.dhl_freight_sweden.evidence \\
        --state-root ~/.local/state --out /tmp/evidence booking-2906761222-102-se-se.json

``CATALOG`` names each evidence file and the captures behind it; a new
finding gets a catalog entry pointing at its capture directory.
"""

import argparse
import base64
import dataclasses
import datetime
import email.utils
import hashlib
import json
import os
import pathlib
import re
import sys
import typing

Json = typing.Any
Exchange = typing.Dict[str, Json]

HOST = "test-api.freight-logistics.dhl.com"
ACCOUNT_NUMBER = "116768"
ACCOUNT_PLACEHOLDERS = frozenset({"<redacted>", "<ACCOUNT>", "__ACCOUNT__"})
BASE64 = re.compile(r"^[A-Za-z0-9+/=\s]{200,}$")
TI = "/transportinstructionapi/v1/transportinstruction/sendtransportinstruction"
PRINT = "/printapi/v1/print/printdocumentsbyid"
MEDIA_BOX = re.compile(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]")
SUITE_RUN = "sandbox_tests suite"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "tests" / "dhl_freight_sweden" / "fixtures" / "sandbox"


def default_state_root(environ: typing.Mapping[str, str]) -> pathlib.Path:
    """``$XDG_STATE_HOME``, or ``~/.local/state`` when it is unset."""
    state_home = environ.get("XDG_STATE_HOME")
    if state_home:
        return pathlib.Path(state_home)
    return pathlib.Path(environ.get("HOME") or pathlib.Path.home()) / ".local" / "state"


def utc(moment: datetime.datetime) -> str:
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def header_date(value: str) -> str:
    return utc(email.utils.parsedate_to_datetime(value))


def mtime(path: pathlib.Path) -> str:
    return utc(datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc))


def json_or_text(text: str) -> Json:
    try:
        return json.loads(text)
    except ValueError:
        return text


def endpoint_of(method: str, url: str) -> str:
    return f"{method} {url.split(HOST, 1)[1]}"


class Builder:
    """Reads captures below ``state_root`` and assembles evidence documents.

    The suite's captures live in ``karrio-dhl-freight-sweden/sandbox/<run>``
    (the harness default) and the earlier scripts' captures in
    ``agent-logs/<project>/<run>``, both relative to ``state_root``.
    """

    def __init__(self, state_root: pathlib.Path) -> None:
        self.state_root = state_root
        self.suite = state_root / "karrio-dhl-freight-sweden" / "sandbox"
        self.logs = state_root / "agent-logs" / "karrio-dhl-freight-sweden"
        self.restored: typing.List[str] = []

    def source(self, path: pathlib.Path) -> Json:
        return dict(
            path=str(path.relative_to(self.state_root)),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )

    def clean(self, value: Json) -> Json:
        """Drop secrets and status echoes, omit base64, restore the account number."""
        if isinstance(value, dict):
            party = typing.cast(typing.Dict[str, Json], value)
            out: typing.Dict[str, Json] = {}
            if party.get("type") == "Consignor" and party.get("id") in ACCOUNT_PLACEHOLDERS:
                self.restored.append(party["id"])
                party = {**party, "id": ACCOUNT_NUMBER}
            for key, entry in party.items():
                if key.lower() in ("client-key", "http_status", "http_message"):
                    continue
                if key == "content" and isinstance(entry, str) and len(entry) > 64:
                    out[key] = f"<base64 omitted: {len(entry)} characters>"
                    continue
                out[key] = self.clean(entry)
            return out
        if isinstance(value, list):
            return [self.clean(entry) for entry in typing.cast(typing.List[Json], value)]
        if isinstance(value, str):
            if value in ACCOUNT_PLACEHOLDERS or value == "<KEY>":
                raise ValueError(f"placeholder {value!r} outside a Consignor party id")
            if BASE64.match(value):
                return f"<base64 omitted: {len(value)} characters>"
        return value

    def suite_exchange(self, run: str, stem: str) -> Exchange:
        """One call captured by the sandbox suite as ``<stem>.request/response.json``."""
        req_path = self.suite / run / f"{stem}.request.json"
        res_path = self.suite / run / f"{stem}.response.json"
        request = json.loads(req_path.read_text())
        response = json.loads(res_path.read_text())
        assert HOST in request["url"], request["url"]
        body = response.get("response") if response["key"] == "response" else response["error"]
        if isinstance(body, str):
            # Captures before the harness decoded empty bodies hold "[]" as text.
            body = json_or_text(body)
        status = body.get("http_status", 200) if isinstance(body, dict) else 200
        method = "POST" if request.get("data") is not None else "GET"
        return dict(
            endpoint=endpoint_of(method, request["url"]),
            http_status=status,
            date=header_date(response["response_headers"]["Date"]),
            date_basis="response Date header",
            request_source=self.source(req_path),
            response_source=self.source(res_path),
            request=self.clean(request.get("data")),
            response=self.clean(body),
        )

    def file_exchange(
        self,
        req_path: typing.Optional[pathlib.Path],
        res_path: pathlib.Path,
        method: str,
        path: str,
        status: int,
    ) -> Exchange:
        """One call saved by a script as bare body files without headers."""
        return dict(
            endpoint=f"{method} {path}",
            http_status=status,
            date=mtime(res_path),
            date_basis="response capture file mtime",
            request_source=self.source(req_path) if req_path else None,
            response_source=self.source(res_path),
            request=self.clean(json.loads(req_path.read_text())) if req_path else None,
            response=self.clean(json.loads(res_path.read_text())),
        )

    def trace_exchanges(self, trace_path: pathlib.Path) -> typing.List[Exchange]:
        """Every call in a connector tracer dump, paired by request id."""
        calls: typing.Dict[str, typing.Dict[str, Json]] = {}
        for record in json.loads(trace_path.read_text()):
            data = record["data"]
            calls.setdefault(data["request_id"], {})[record["key"]] = data
        out: typing.List[Exchange] = []
        for call in calls.values():
            request, response = call["request"], call["response"]
            assert HOST in request["url"]
            out.append(
                dict(
                    endpoint=endpoint_of("POST", request["url"]),
                    http_status=200,
                    date=header_date(response["response_headers"]["Date"]),
                    date_basis="response Date header",
                    request_source=self.source(trace_path),
                    response_source=self.source(trace_path),
                    request=self.clean(request["data"]),
                    response=self.clean(response["response"]),
                )
            )
        return out

    def with_label(
        self, exchange: Exchange, print_body: Json, pdf_path: pathlib.Path, text_path: pathlib.Path
    ) -> Exchange:
        """Attach the printed label's page size and extracted text to a Print API exchange.

        ``pdf_path`` must hold the bytes of the only report in ``print_body``,
        the raw Print API response, and ``text_path`` the ``pdftotext -layout``
        output of that PDF.
        """
        (report,) = print_body["reports"]
        pdf = pdf_path.read_bytes()
        assert base64.b64decode(report["content"]) == pdf, f"{pdf_path} is not the printed label"
        media_box = MEDIA_BOX.search(pdf)
        assert media_box, f"{pdf_path} has no MediaBox"
        exchange["label"] = dict(
            pdf_source=self.source(pdf_path),
            page_size_pt=[float(media_box.group(1)), float(media_box.group(2))],
            text_extraction="pdftotext -layout",
            text_source=self.source(text_path),
            text=text_path.read_text(),
        )
        return exchange

    def document(
        self,
        kind: str,
        summary: str,
        product: typing.Optional[str],
        route: typing.Optional[str],
        booking_id: typing.Optional[str],
        error_code: typing.Optional[str],
        captured_by: str,
        exchanges: typing.List[Exchange],
        primary: int = 0,
    ) -> Json:
        """The evidence document, claiming the account restorations made so far."""
        main = exchanges[primary]
        restored = sorted(set(self.restored))
        self.restored.clear()
        return dict(
            kind=kind,
            summary=summary,
            captured_at=main["date"],
            environment=HOST,
            endpoint=main["endpoint"],
            product=product,
            route=route,
            booking_id=booking_id,
            error_code=error_code,
            http_status=main["http_status"],
            captured_by=captured_by,
            redaction=(
                "client-key request headers and response headers dropped; "
                "label and document base64 replaced by a length marker"
            ),
            account_number_restored=(
                dict(
                    value=ACCOUNT_NUMBER,
                    placeholders=restored,
                    note="the source capture masked the customer number in the Consignor party id; "
                    "the sha256 values refer to the original capture files",
                )
                if restored
                else None
            ),
            exchanges=exchanges,
        )

    def suite_booking(
        self,
        summary: str,
        product: str,
        route: str,
        run: str,
        stems: typing.Sequence[str],
        test: str,
        primary: int,
    ) -> Json:
        exchanges = [self.suite_exchange(run, stem) for stem in stems]
        booking_id = exchanges[primary]["response"]["transportInstruction"]["id"]
        return self.document(
            "booking", summary, product, route, booking_id, None,
            f"{SUITE_RUN}: {test}", exchanges, primary,
        )


PRODUCT_MATCH_KEYS = ("code", "name", "shortName", "isDomestic")


def reduce_product_matches(exchange: Exchange) -> Exchange:
    exchange["response"] = [
        dict(product={key: match["product"].get(key) for key in PRODUCT_MATCH_KEYS})
        for match in exchange["response"]
    ]
    exchange["response_reduced"] = (
        "each match keeps product code, name, shortName, and isDomestic; "
        "the full body is identified by response_source.sha256"
    )
    return exchange


def consignee_country(request: Json) -> typing.Optional[str]:
    return next(
        (
            party["address"].get("countryCode")
            for party in request.get("parties") or []
            if party.get("type") == "Consignee"
        ),
        None,
    )


def destination_entry(entry: Json) -> Json:
    country = entry.get("country") or {}
    return dict(
        country={key: country.get(key) for key in ("countryCode", "customs")},
        **({"postalCodeExcludes": entry["postalCodeExcludes"]} if "postalCodeExcludes" in entry else {}),
    )


def reduce_product_matches_with_destinations(exchange: Exchange) -> Exchange:
    """Like ``reduce_product_matches``, keeping the product destinations that bear on the lane.

    Each match keeps the toCountries entries with a non-empty
    postalCodeExcludes and the entry of the request's Consignee country.
    """
    destination = consignee_country(exchange["request"])
    exchange["response"] = [
        dict(
            product={
                **{key: match["product"].get(key) for key in PRODUCT_MATCH_KEYS},
                "toCountries": [
                    destination_entry(entry)
                    for entry in match["product"].get("toCountries") or []
                    if entry.get("postalCodeExcludes")
                    or (entry.get("country") or {}).get("countryCode") == destination
                ],
            }
        )
        for match in exchange["response"]
    ]
    exchange["response_reduced"] = (
        "each match keeps product code, name, shortName, isDomestic, and the toCountries "
        "entries with a non-empty postalCodeExcludes or of the Consignee country, each "
        "reduced to countryCode, customs, and postalCodeExcludes; the full body is "
        "identified by response_source.sha256"
    )
    return exchange


def reduce_product(exchange: Exchange) -> Exchange:
    exchange["response"] = {key: exchange["response"].get(key) for key in ("code", "name", "payerCodes")}
    exchange["response_reduced"] = (
        "keeps code, name, and payerCodes; the full body is identified by response_source.sha256"
    )
    return exchange


Entry = typing.Callable[[Builder], Json]
CATALOG: typing.Dict[str, Entry] = {}


def evidence(name: str) -> typing.Callable[[Entry], Entry]:
    def register(entry: Entry) -> Entry:
        CATALOG[name] = entry
        return entry

    return register


BOOK_SCRIPT = "agent-logs/karrio-dhl-freight-sweden/booking-20261005-163104/book.py"
VERIFY_SCRIPT = "agent-logs/karrio-dhl-freight-sweden/connector-verify-20261005-164743/verify.py"
PROBE_SCRIPT = "agent-logs/karrio-dhl-freight-sweden/probe-20261005-161414/run.sh"


def direct_bookings(b: Builder) -> pathlib.Path:
    return b.logs / "booking-20261005-163104"


def connector_verify(b: Builder) -> pathlib.Path:
    return b.logs / "connector-verify-20261005-164743"


def probe(b: Builder) -> pathlib.Path:
    return b.logs / "probe-20261005-161414"


@evidence("booking-2906761073-109-se-pl.json")
def _(b: Builder) -> Json:
    d = direct_bookings(b)
    return b.document(
        "booking",
        "109 SE to PL with payer code 022, ParcelShop 8005-PL-4507446, and SENT_FREE true, sent directly to TransportInstruction.",
        "109", "SE 11143 -> PL 30-079", "2906761073", None, BOOK_SCRIPT,
        [b.file_exchange(d / "B1-109-022-shop-free.request.json", d / "B1-109-022-shop-free.response.json", "POST", TI, 200)],
    )


@evidence("booking-2906761081-112-se-pl.json")
def _(b: Builder) -> Json:
    d = direct_bookings(b)
    return b.document(
        "booking",
        "112 SE to PL with payer code 023, home delivery, and SENT_FREE true, sent directly to TransportInstruction.",
        "112", "SE 11143 -> PL 30-079", "2906761081", None, BOOK_SCRIPT,
        [b.file_exchange(d / "B2-112-023-home-free.request.json", d / "B2-112-023-home-free.response.json", "POST", TI, 200)],
    )


@evidence("booking-2906761123-109-se-pl.json")
def _(b: Builder) -> Json:
    return b.document(
        "booking",
        "109 SE to PL booked through the connector with payer code 022, ParcelShop 8005-PL-4507446, and SENT_FREE true, then printed.",
        "109", "SE 11143 -> PL 30-079", "2906761123", None, f"{VERIFY_SCRIPT} (V1)",
        b.trace_exchanges(connector_verify(b) / "V1.trace.json"),
    )


@evidence("booking-2906761131-112-se-pl.json")
def _(b: Builder) -> Json:
    return b.document(
        "booking",
        "112 SE to PL booked through the connector with payer code 023 and SENT_FREE true, then printed.",
        "112", "SE 11143 -> PL 30-079", "2906761131", None, f"{VERIFY_SCRIPT} (V2)",
        b.trace_exchanges(connector_verify(b) / "V2.trace.json"),
    )


@evidence("booking-2906761149-112-se-pl-payer-022.json")
def _(b: Builder) -> Json:
    d = connector_verify(b)
    return b.document(
        "booking",
        "112 SE to PL with payer code 022, sent directly past the connector's payer code check, was accepted.",
        "112", "SE 11143 -> PL 30-079", "2906761149", None, f"{VERIFY_SCRIPT} (V3-raw)",
        [b.file_exchange(d / "V3-raw.request.json", d / "V3-raw.response.json", "POST", TI, 200)],
    )


SUITE_BOOKINGS: typing.Tuple[typing.Tuple[str, str, str, str, str, typing.Tuple[str, ...], str, int], ...] = (
    ("booking-2906761222-102-se-se.json", "102 within SE with payer code 1, then printed.",
     "102", "SE 11143 -> SE 11151", "20261005-182136", ("001-booking-102", "002-booking-102"),
     "test_booking_approved", 0),
    ("booking-2906761230-103-se-se.json",
     "103 within SE to service point SE-982000 sent as the full id, after a five-point service point lookup, then printed.",
     "103", "SE 11143 -> SE 11151", "20261005-182145",
     ("001-service-points-103-se", "003-booking-103", "004-booking-103"), "test_booking_pudo", 1),
    ("booking-2906761248-601-se-dk.json", "601 SE to DK with payer code DAP, then printed.",
     "601", "SE 11143 -> DK 1620", "20261005-182932", ("001-booking-601", "002-booking-601"),
     "test_booking_approved", 0),
    ("booking-2906761255-118-se-se.json",
     "118 within SE after a PostalCode route check with homeDeliveryParcel true (address_validation enforce), then printed.",
     "118", "SE 11143 -> SE 11151", "20261005-182938",
     ("001-booking-118", "002-booking-118", "003-booking-118"), "test_booking_approved", 1),
    ("booking-2906761263-109-se-ro.json",
     "109 SE to RO with payer code 022 to ParcelShop 8023-231652 without UIT entries, then printed.",
     "109", "SE 11143 -> RO 030031", "20261005-182947",
     ("003-service-points-109-ro", "005-booking-109", "006-booking-109"), "test_booking_export", 1),
    ("booking-2906761271-112-se-ro.json",
     "112 SE to RO with payer code 023 without UIT entries, then printed.",
     "112", "SE 11143 -> RO 030031", "20261005-182947", ("010-booking-112", "011-booking-112"),
     "test_booking_export", 0),
    ("booking-2906761289-109-se-hu.json",
     "109 SE to HU with payer code 022 to ParcelStation 8013-118530, a locker listing only parcel:pick-up-unregistered, without EKAER entries, then printed.",
     "109", "SE 11143 -> HU 1052", "20261005-183002",
     ("003-service-points-109-hu", "005-booking-109", "006-booking-109"), "test_booking_export", 1),
    ("booking-2906761297-112-se-hu.json",
     "112 SE to HU with payer code 023 without EKAER entries, then printed.",
     "112", "SE 11143 -> HU 1052", "20261005-183002", ("010-booking-112", "011-booking-112"),
     "test_booking_export", 0),
    ("booking-2906761305-109-se-no.json",
     "109 SE to NO with payer code 022, customsHandlingFullService, and a ProformaInvoice, to ParcelShop 8009-129635, then printed.",
     "109", "SE 11143 -> NO 0154", "20261005-183015",
     ("003-service-points-109-no", "005-booking-109", "006-booking-109"), "test_booking_export", 1),
    ("booking-2906761313-112-se-no.json",
     "112 SE to NO with payer code 023, customsHandlingFullService, and a ProformaInvoice, then printed.",
     "112", "SE 11143 -> NO 0154", "20261005-183015", ("010-booking-112", "011-booking-112"),
     "test_booking_export", 0),
    ("booking-2906761339-601-se-hu.json",
     "601 SE to HU with payer code DAP, EKAER_FREE false, and a placeholder EKAER_NUMBER, then printed.",
     "601", "SE 11143 -> HU 1052", "20261005-185338", ("003-booking-601", "004-booking-601"),
     "test_booking_declarations", 0),
    ("booking-2906761347-601-se-ro.json",
     "601 SE to RO with payer code DAP and UIT_FREE false without UIT_NUMBER, then printed.",
     "601", "SE 11143 -> RO 030031", "20261005-185350", ("003-booking-601", "004-booking-601"),
     "test_booking_declarations", 0),
    ("booking-2906761354-109-se-dk.json",
     "109 SE to DK with payer code 022 to ParcelShop 8009-115191, then printed.",
     "109", "SE 11143 -> DK 1620", "20261005-191426",
     ("003-service-points-109-dk", "005-booking-109", "006-booking-109"), "test_booking_export", 1),
    ("booking-2906761867-112-se-fr.json",
     "112 SE to FR home delivery with payer code 023, then printed; the response adds Chronopost additionalInformation entries.",
     "112", "SE 11143 -> FR 75004", "20261006-101051", ("003-booking-112", "004-booking-112"),
     "test_booking_export", 0),
    ("booking-2906761917-109-se-fi-aland.json",
     "109 SE to FI 22100 (Åland) with payer code 022 to ParcelShop 8011-221003201 without customs data, then printed.",
     "109", "SE 11143 -> FI 22100", "20261006-110739",
     ("003-service-points-109-fi-22100", "005-booking-109", "006-booking-109"),
     "test_booking_export.test_book_109_fi_aland_without_customs", 1),
    ("booking-2906761925-202-se-gb-northern-ireland.json",
     "202 SE to GB BT1 1AA (Northern Ireland) with payer code DAP without customs data, then printed.",
     "202", "SE 11143 -> GB BT1 1AA", "20261006-110752", ("003-booking-202", "004-booking-202"),
     "test_booking_export.test_book_202_gb_northern_ireland_without_customs", 0),
    ("booking-2906762105-109-se-no-standard-customs.json",
     "109 SE to NO with payer code 022, customsHandlingStandard, a made-up EORI number, and a "
     "ProformaInvoice, to ParcelShop 8009-129635, then printed.",
     "109", "SE 11143 -> NO 0154", "20261006-123912",
     ("003-service-points-109-no", "005-booking-109", "006-booking-109"),
     "test_booking_export.test_book_109_no_customs_standard", 1),
    ("booking-2906762113-112-se-no-standard-customs.json",
     "112 SE to NO with payer code 023, customsHandlingStandard, a made-up EORI number, and a "
     "ProformaInvoice, then printed.",
     "112", "SE 11143 -> NO 0154", "20261006-123912", ("010-booking-112", "011-booking-112"),
     "test_booking_export.test_book_112_no_customs_standard", 0),
    ("booking-2906762121-202-se-dk.json", "202 SE to DK with payer code DAP, then printed.",
     "202", "SE 11143 -> DK 1620", "20261006-123912", ("015-booking-202", "016-booking-202"),
     "test_booking_export.test_book_202_dk", 0),
    ("booking-2906762139-202-se-no.json",
     "202 SE to NO with payer code DAP, customsHandlingFullService, and a ProformaInvoice, then printed.",
     "202", "SE 11143 -> NO 0154", "20261006-123912", ("020-booking-202", "021-booking-202"),
     "test_booking_export.test_book_202_no_customs_full", 0),
    ("booking-2906762147-233-se-dk.json", "233 SE to DK with payer code DAP, then printed.",
     "233", "SE 11143 -> DK 1620", "20261006-123912", ("029-booking-233", "030-booking-233"),
     "test_booking_export.test_book_233_dk", 0),
    ("booking-2906762154-233-se-no.json",
     "233 SE to NO with payer code DAP, customsHandlingFullService, and a ProformaInvoice, then printed.",
     "233", "SE 11143 -> NO 0154", "20261006-123912", ("034-booking-233", "035-booking-233"),
     "test_booking_export.test_book_233_no_customs_full", 0),
    ("booking-2906762162-601-se-no.json",
     "601 SE to NO with payer code DAP, customsHandlingFullService, and a ProformaInvoice, then printed.",
     "601", "SE 11143 -> NO 0154", "20261006-123912", ("039-booking-601", "040-booking-601"),
     "test_booking_export.test_book_601_no_customs_full", 0),
)

for _name, _summary, _product, _route, _run, _stems, _test, _primary in SUITE_BOOKINGS:
    evidence(_name)(
        lambda b, s=_summary, p=_product, r=_route, run=_run, st=_stems, t=_test, i=_primary: (
            b.suite_booking(s, p, r, run, st, t, i)
        )
    )

REJECTIONS_RUN = "20261005-185322"
REJECTIONS: typing.Tuple[typing.Tuple[str, str, str, str, str, str], ...] = (
    ("rejection-22001-109-se-pl-without-sent.json",
     "109 SE to PL with payer code 022 and ParcelShop 8005-PL-4504339 but no SENT entries was rejected with 22001.",
     "109", "003-rejection-109-pl-without-sent", "22001", "test_109_pl_without_sent_is_rejected_with_22001"),
    ("rejection-22015-112-se-pl-access-point.json",
     "112 SE to PL with payer code 023, SENT_FREE true, and an added AccessPoint party was rejected with 22015.",
     "112", "007-rejection-112-pl-access-point", "22015", "test_112_pl_with_access_point_is_rejected_with_22015"),
    ("rejection-22020-112-se-pl-payer-code-1.json",
     "112 SE to PL with payer code 1 and SENT_FREE true was rejected with 22020.",
     "112", "009-rejection-112-pl-payer-code-1", "22020", "test_112_pl_with_payer_code_1_is_rejected_with_22020"),
)

for _name, _summary, _product, _stem, _code, _test in REJECTIONS:
    evidence(_name)(
        lambda b, s=_summary, p=_product, st=_stem, c=_code, t=_test: b.document(
            "rejection", s, p, "SE 11143 -> PL 30-079", None, c,
            f"{SUITE_RUN}: test_rejections.{t}", [b.suite_exchange(REJECTIONS_RUN, st)],
        )
    )



@evidence("rejection-22005-112-se-gb.json")
def _(b: Builder) -> Json:
    return b.document(
        "rejection",
        "112 SE to GB home delivery with payer code 023 and customs handling full service, booked although "
        "product matches did not offer 112 to GB, was rejected with 22005 'No valid product was found for "
        "given productcode and countries' and 22026 'Consignee CountryCode is not valid for this product'.",
        "112", "SE 11143 -> GB W1D 1AN", None, "22005",
        f"{SUITE_RUN}: test_booking_export.test_book_112_gb",
        [reduce_product_matches(b.suite_exchange("20261006-103901", "001-product-matches-112-gb")),
         b.suite_exchange("20261006-103901", "003-booking-112")],
        primary=1,
    )


@evidence("rejection-24003-112-se-fi-aland.json")
def _(b: Builder) -> Json:
    return b.document(
        "rejection",
        "112 SE to FI 22100 (Åland) home delivery with payer code 023, customs handling full service, one "
        "commodity, and a proforma invoice, after product matches offered 112, was rejected with 24003 "
        "'customsHandlingFullService is not available for this country combination'.",
        "112", "SE 11143 -> FI 22100", None, "24003",
        f"{SUITE_RUN}: test_booking_export.test_book_112_fi_aland",
        [reduce_product_matches(b.suite_exchange("20261006-110728", "001-product-matches-112-fi-22100")),
         b.suite_exchange("20261006-110728", "003-booking-112")],
        primary=1,
    )


@evidence("rejection-24003-112-se-fi-aland-standard.json")
def _(b: Builder) -> Json:
    return b.document(
        "rejection",
        "112 SE to FI 22100 (Åland) home delivery with payer code 023, customs handling standard, a made-up "
        "EORI number, one commodity, and a proforma invoice, after product matches offered 112, was rejected "
        "with 24003 'customsHandlingStandard is not available for this country combination'.",
        "112", "SE 11143 -> FI 22100", None, "24003",
        f"{SUITE_RUN}: test_booking_export.test_book_112_fi_aland_standard_customs",
        [reduce_product_matches(b.suite_exchange("20261006-111214", "001-product-matches-112-fi-22100")),
         b.suite_exchange("20261006-111214", "003-booking-112")],
        primary=1,
    )


@evidence("rejection-22001-103-se-access-point-id-only.json")
def _(b: Builder) -> Json:
    return b.document(
        "rejection",
        "103 within SE with the AccessPoint party of service point SE-982000 reduced to id, type, and sub type "
        "was rejected with 22001 for the missing address and the missing name, 22026 for the AccessPoint country "
        "code, and 22006 for the AccessPoint postal code.",
        "103", "SE 11143 -> SE 11151", None, "22001",
        f"{SUITE_RUN}: test_rejections.test_103_se_access_point_id_only_is_rejected_with_22001_and_22006",
        [b.suite_exchange("20261005-193156", "001-service-points-rejection-103-se"),
         b.suite_exchange("20261005-193156", "003-rejection-103-se-access-point-id-only")],
        primary=1,
    )


LOOKUPS_RUN = "20261005-182045"
CAPACITY_RUN = "20261005-182045-capacity-probe"


@evidence("lookup-postal-code-se-99999-16010.json")
def _(b: Builder) -> Json:
    return b.document(
        "lookup", "PostalCode route for SE 99999 answered 400 with the PascalCase ErrorResult 16010.",
        None, "SE 99999", None, "16010", f"{SUITE_RUN}: test_lookups",
        [b.suite_exchange(LOOKUPS_RUN, "003-postal-code-se-99999")],
    )


@evidence("lookup-postal-code-se-11151-route.json")
def _(b: Builder) -> Json:
    return b.document(
        "lookup", "PostalCode route for SE 11151 answered bookable true and homeDeliveryParcel true.",
        None, "SE 11151", None, None, f"{SUITE_RUN}: test_lookups",
        [b.suite_exchange(LOOKUPS_RUN, "001-postal-code-se-11151-118")],
    )


@evidence("lookup-postal-code-pl-route-16009.json")
def _(b: Builder) -> Json:
    return b.document(
        "lookup", "PostalCode route for PL 30-079 answered 400 with 16009 'Country code 'PL' not supported.'.",
        None, "PL 30-079", None, "16009", PROBE_SCRIPT,
        [b.file_exchange(None, probe(b) / "pc-route-PL-30-079.json", "GET", "/postalcodeapi/v1/postalcodes/PL/30-079/route", 400)],
    )


@evidence("lookup-service-points-se-capacity-not-applied.json")
def _(b: Builder) -> Json:
    return b.document(
        "lookup",
        "Nearest service points for Stockholm returned the same ten points in the same order for a 2.5 kg 40x30x15 cm piece and a 500 kg 300x200x200 cm piece.",
        None, "SE 11143", None, None, f"{SUITE_RUN}: test_lookups",
        [b.suite_exchange(LOOKUPS_RUN, "013-service-points-se-parcel"),
         b.suite_exchange(LOOKUPS_RUN, "015-service-points-se-oversized")],
    )


@evidence("lookup-service-points-pl-capacity-too-large.json")
def _(b: Builder) -> Json:
    return b.document(
        "lookup",
        "Nearest service points for Warszawa returned points for a 2.5 kg piece and answered 400 'The dimensions are too large' for a 500 kg 300x200x200 cm piece, with and without locationTypes locker.",
        None, "PL 00-251", None, None, f"manual capacity probe with the connector ({CAPACITY_RUN})",
        [b.suite_exchange(CAPACITY_RUN, "001-pl-fit"),
         b.suite_exchange(CAPACITY_RUN, "003-pl-oversized"),
         b.suite_exchange(CAPACITY_RUN, "005-pl-locker-oversized")],
        primary=1,
    )


@evidence("lookup-product-matches-se-pl.json")
def _(b: Builder) -> Json:
    return b.document(
        "lookup", "Product matches for SE 11143 to PL 00-251 returned HDI, 109, 202, 112, 601, and 233.",
        None, "SE 11143 -> PL 00-251", None, None, f"{SUITE_RUN}: test_lookups",
        [reduce_product_matches(b.suite_exchange(LOOKUPS_RUN, "007-product-matches-se-pl"))],
    )


@evidence("lookup-product-matches-se-gb.json")
def _(b: Builder) -> Json:
    return b.document(
        "lookup",
        "Product matches for SE 11143 to GB W1D 1AN returned HDI, 202, 601, and 233, without 109 or 112, "
        "so the booking-export case 112 to GB skipped without booking.",
        None, "SE 11143 -> GB W1D 1AN", None, None, f"{SUITE_RUN}: test_booking_export",
        [reduce_product_matches(b.suite_exchange("20261006-102955", "001-product-matches-112-gb"))],
    )


TERRITORIES_RUN = "20261006-105223"
TERRITORY_PROBES: typing.Tuple[typing.Tuple[str, str, str, str], ...] = (
    ("se-fi-22100", "009", "FI 22100", "Åland under FI"),
    ("se-ax-22100", "001", "AX 22100", "Åland under its own code AX"),
    ("se-fi-00100", "007", "FI 00100", "mainland Finland (control)"),
    ("se-gb-je23ab", "019", "GB JE2 3AB", "Jersey under GB"),
    ("se-gb-gy11aa", "015", "GB GY1 1AA", "Guernsey under GB"),
    ("se-gb-bt11aa", "013", "GB BT1 1AA", "Northern Ireland under GB"),
    ("se-gb-im11aa", "017", "GB IM1 1AA", "the Isle of Man under GB"),
    ("se-gb-w1d1an", "021", "GB W1D 1AN", "London (control)"),
    ("se-je-je23ab", "025", "JE JE2 3AB", "Jersey under its own code JE"),
    ("se-gg-gy11aa", "023", "GG GY1 1AA", "Guernsey under its own code GG"),
    ("se-dk-3900", "003", "DK 3900", "Greenland under DK"),
    ("se-fo-100", "011", "FO 100", "the Faroe Islands under their own code FO"),
    ("se-es-35001", "005", "ES 35001", "the Canary Islands under ES"),
)


def territory_probe(b: Builder, lane: str, sequence: str, destination: str, area: str) -> Json:
    exchange = reduce_product_matches_with_destinations(
        b.suite_exchange(TERRITORIES_RUN, f"{sequence}-product-matches-{lane}")
    )
    codes = [match["product"]["code"] for match in exchange["response"]]
    return b.document(
        "lookup",
        f"Product matches for SE 11143 to {destination} ({area}) returned "
        + (", ".join(codes) if codes else "no products")
        + ".",
        None, f"SE 11143 -> {destination}", None, None,
        f"{SUITE_RUN}: test_lookups.test_product_matches_territory_{destination.lower().replace(' ', '_')}",
        [exchange],
    )


for _lane, _sequence, _destination, _area in TERRITORY_PROBES:
    evidence(f"lookup-product-matches-{_lane}.json")(
        lambda b, l=_lane, s=_sequence, d=_destination, a=_area: territory_probe(b, l, s, d, a)
    )


@evidence("lookup-product-matches-se-se.json")
def _(b: Builder) -> Json:
    return b.document(
        "lookup", "Product matches for a domestic SE lane.",
        None, "SE -> SE", None, None, f"{SUITE_RUN}: test_lookups",
        [reduce_product_matches(b.suite_exchange(LOOKUPS_RUN, "009-product-matches-se-se"))],
    )


@evidence("lookup-products-109-112-payer-codes.json")
def _(b: Builder) -> Json:
    p = probe(b)
    return b.document(
        "lookup",
        "The Product API catalog lists payer codes CPT, 022, DPU, DAP, 023, CIP, and DDP for 109 and 112, with customs true only for DDP.",
        "109, 112", None, None, None, PROBE_SCRIPT,
        [reduce_product(b.file_exchange(None, p / "product-109.json", "GET", "/productapi/v1/products/109", 200)),
         reduce_product(b.file_exchange(None, p / "product-112.json", "GET", "/productapi/v1/products/112", 200))],
    )


SUITE_LABELS = "agent-logs/karrio-dhl-freight-sweden/suite-labels-20261005"
SUITE_LABELS_20261006 = "agent-logs/karrio-dhl-freight-sweden/suite-labels-20261006"


def suite_label(
    b: Builder, summary: str, product: str, route: str, booking_id: str,
    run: str, booking_stem: str, print_stem: str, test: str,
    labels: str = SUITE_LABELS,
) -> Json:
    """A suite booking and its print call, with the label PDF decoded into ``labels``."""
    d = b.state_root / labels
    printed = json.loads((b.suite / run / f"{print_stem}.response.json").read_text())["response"]
    return b.document(
        "label", summary, product, route, booking_id, None,
        f"{SUITE_RUN}: {test}; label PDF decoded from the print response into {labels}",
        [b.suite_exchange(run, booking_stem),
         b.with_label(
             b.suite_exchange(run, print_stem), printed,
             d / f"label_{booking_id}.pdf", d / f"label_{booking_id}.txt",
         )],
        primary=1,
    )


@evidence("label-2906761222-102-se-se.json")
def _(b: Builder) -> Json:
    return suite_label(
        b,
        "102 within SE booked with consignor phone +46 8 123 456 and consignee phone +46 70 123 45 67, "
        "printed with page type Label as one 297.638 x 595.276 pt (105 x 210 mm) PDF page; "
        "the label text shows one Phn. line with no number.",
        "102", "SE 11143 -> SE 11151", "2906761222",
        "20261005-182136", "001-booking-102", "002-booking-102", "test_booking_approved",
    )


@evidence("label-2906761230-103-se-se-service-point.json")
def _(b: Builder) -> Json:
    return suite_label(
        b,
        "103 within SE to service point SE-982000 booked with consignor phone +46 8 123 456, consignee phone "
        "+46 70 123 45 67, and no AccessPoint phone, printed with page type Label as one 297.638 x 595.276 pt (105 x 210 mm) PDF page; "
        "the label text shows one Phn. line with no number.",
        "103", "SE 11143 -> SE 11151", "2906761230",
        "20261005-182145", "003-booking-103", "004-booking-103", "test_booking_pudo",
    )


@evidence("label-2906761255-118-se-se.json")
def _(b: Builder) -> Json:
    return suite_label(
        b,
        "118 within SE booked with consignor phone +46 8 123 456 and consignee phone +46 70 123 45 67, "
        "printed with page type Label as one 297.638 x 595.276 pt (105 x 210 mm) PDF page; "
        "the label text shows one Phn. line with no number.",
        "118", "SE 11143 -> SE 11151", "2906761255",
        "20261005-182938", "002-booking-118", "003-booking-118", "test_booking_approved",
    )


@evidence("label-2906761297-112-se-hu.json")
def _(b: Builder) -> Json:
    return suite_label(
        b,
        "112 SE to HU booked with consignor phone +46 8 123 456 and consignee phone +36 30 000 0000, "
        "printed with page type Label as one 297.638 x 595.276 pt (105 x 210 mm) PDF page; "
        "the label text shows one Phn. line with no number.",
        "112", "SE 11143 -> HU 1052", "2906761297",
        "20261005-183002", "010-booking-112", "011-booking-112", "test_booking_export",
    )


@evidence("label-2906761248-601-se-dk.json")
def _(b: Builder) -> Json:
    return suite_label(
        b,
        "601 SE to DK home delivery booked with consignor phone +46 8 123 456, Consignee Mette Hansen, and consignee phone +45 20 12 34 56, "
        "printed with page type Label as one 297.638 x 595.276 pt (105 x 210 mm) PDF page; "
        "the label text shows one Phn. line with no number and no consignee phone.",
        "601", "SE 11143 -> DK 1620", "2906761248",
        "20261005-182932", "001-booking-601", "002-booking-601", "test_booking_approved",
    )


@evidence("label-2906761305-109-se-no-parcelshop.json")
def _(b: Builder) -> Json:
    return suite_label(
        b,
        "109 SE to NO ParcelShop 8009-129635 (CHRISTIAN KROHGS GATE 1, 0186 OSLO) booked with Consignee "
        "Ola Nordmann, Karl Johans gate 10, 0154 Oslo, and consignee phone +47 400 00 000, printed with "
        "page type Label as one 297.638 x 595.276 pt (105 x 210 mm) PDF page; the label text shows the "
        "Consignee name below the sender block and the Consignee name and address at the bottom, the "
        "sender's +46 8 123 456 as the only Phn. line, and no consignee phone.",
        "109", "SE 11143 -> NO 0154", "2906761305",
        "20261005-183015", "005-booking-109", "006-booking-109", "test_booking_export",
    )


@evidence("label-2906761354-109-se-dk-parcelshop.json")
def _(b: Builder) -> Json:
    return suite_label(
        b,
        "109 SE to DK ParcelShop 8009-115191 booked with Consignee Mette Hansen, Vesterbrogade 10, "
        "and consignee phone +45 20 12 34 56, printed with page type Label as one 297.638 x 595.276 pt "
        "(105 x 210 mm) PDF page; the label text shows the Consignee name below the sender block and the "
        "Consignee name and address in the TE block, the sender's +46 8 123 456 as the only Phn. line, "
        "and no consignee phone.",
        "109", "SE 11143 -> DK 1620", "2906761354",
        "20261005-191426", "005-booking-109", "006-booking-109", "test_booking_export",
    )


@evidence("label-2906761867-112-se-fr.json")
def _(b: Builder) -> Json:
    return suite_label(
        b,
        "112 SE to FR home delivery booked with consignor phone +46 8 123 456, Consignee Jean Dupont, "
        "10 Rue de Rivoli, 75004 Paris, and consignee phone +33 6 12 34 56 78, printed with page type Label "
        "as one 283.46 x 425.2 pt (100 x 150 mm) PDF page; the label text shows the Chronopost reference "
        "XY22 2000 028 and the routing code 25075004+74000000, and no Phn. line and no phone number.",
        "112", "SE 11143 -> FR 75004", "2906761867",
        "20261006-101051", "003-booking-112", "004-booking-112", "test_booking_export",
        labels=SUITE_LABELS_20261006,
    )


def render(document: Json) -> str:
    return json.dumps(document, ensure_ascii=False, indent=1) + "\n"


def build(state_root: pathlib.Path, out: pathlib.Path, names: typing.Iterable[str]) -> typing.List[pathlib.Path]:
    """Write the named evidence files (all of ``CATALOG`` when empty) into ``out``."""
    selected = list(names) or list(CATALOG)
    unknown = [name for name in selected if name not in CATALOG]
    if unknown:
        raise SystemExit(f"unknown evidence files: {', '.join(unknown)}")
    out.mkdir(parents=True, exist_ok=True)
    builder = Builder(state_root)
    written: typing.List[pathlib.Path] = []
    for name in selected:
        path = out / name
        path.write_text(render(CATALOG[name](builder)))
        written.append(path)
    return written


@dataclasses.dataclass(frozen=True)
class Arguments:
    state_root: pathlib.Path
    out: pathlib.Path
    names: typing.List[str]


def parse_arguments(argv: typing.Sequence[str], environ: typing.Mapping[str, str]) -> Arguments:
    parser = argparse.ArgumentParser(description="Build the committed sandbox evidence files from the captures.")
    parser.add_argument(
        "--state-root", type=pathlib.Path, default=default_state_root(environ),
        help="directory the capture paths are relative to (default: $XDG_STATE_HOME or ~/.local/state)",
    )
    parser.add_argument(
        "--out", type=pathlib.Path, default=DEFAULT_OUT,
        help=f"evidence directory (default: {DEFAULT_OUT.relative_to(REPO_ROOT)})",
    )
    parser.add_argument("names", nargs="*", help="evidence file names to build (default: all)")
    parsed = parser.parse_args(argv)
    return Arguments(parsed.state_root.expanduser(), parsed.out, parsed.names)


def main(argv: typing.Sequence[str]) -> None:
    arguments = parse_arguments(argv, os.environ)
    for path in build(arguments.state_root, arguments.out, arguments.names):
        print(path)


if __name__ == "__main__":
    main(sys.argv[1:])
