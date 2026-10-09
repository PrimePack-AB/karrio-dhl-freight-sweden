"""Live DHL Freight SE sandbox harness: gating, booking budget, and captures.

Every live test runs only when ``DHL_FREIGHT_SWEDEN_SANDBOX=1`` and a client
key are set, always in test mode, and never against the production host.
The configuration parsing, budget, and redaction are pure; the effects
(the transport guard, the capture files, and the gateway) live in
``Session``, built once per process by ``session()``.
"""

import copy
import dataclasses
import datetime
import functools
import json
import os
import pathlib
import sys
import typing
import unittest
import urllib.parse

import karrio.core.utils.helpers as helpers
import karrio.lib as lib
import karrio.mappers.dhl_freight_sweden.proxy as connector_proxy
import karrio.mappers.dhl_freight_sweden.settings as connector_settings
import karrio.providers.dhl_freight_sweden.units as provider_units
import karrio.sdk as karrio

SANDBOX_HOST = "test-api.freight-logistics.dhl.com"
BOOKING_SEGMENTS = frozenset(
    {
        "booking-approved",
        "booking-pudo",
        "booking-export",
        "booking-declarations",
        "rejections",
    }
)
SEGMENTS = frozenset({"lookups"}) | BOOKING_SEGMENTS
DEFAULT_SEGMENTS = frozenset({"lookups"})
DEFAULT_MAX_BOOKINGS = 30
BOOKING_PATH = "/transportinstruction/sendtransportinstruction"
REDACTED = "<redacted>"
SECRET_HEADERS = frozenset({"client-key"})


class SandboxConfigError(ValueError):
    """Raised when a sandbox environment variable is malformed or unsafe."""


@dataclasses.dataclass(frozen=True)
class SandboxConfig:
    enabled: bool
    client_key: typing.Optional[str]
    account_number: typing.Optional[str]
    international_account_number: typing.Optional[str]
    segments: typing.FrozenSet[str]
    products: typing.Optional[typing.FrozenSet[str]]
    countries: typing.Optional[typing.FrozenSet[str]]
    max_bookings: int
    capture_dir: pathlib.Path


def parse_list(value: typing.Optional[str]) -> typing.FrozenSet[str]:
    return frozenset(item.strip() for item in (value or "").split(",") if item.strip())


def load_config(
    environ: typing.Mapping[str, str],
    now: datetime.datetime,
) -> SandboxConfig:
    """Read the sandbox configuration from an environment mapping.

    Unknown segments and a non-integer or negative booking budget raise
    rather than being ignored, so a typo never widens what a run books.
    No variable selects the host: the gateway always resolves the
    connector's test-mode sandbox host.
    """
    segments = parse_list(environ.get("DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS"))
    unknown = segments - SEGMENTS
    if unknown:
        raise SandboxConfigError(
            f"Unknown sandbox segments: {', '.join(sorted(unknown))}; "
            f"expected any of {', '.join(sorted(SEGMENTS))}"
        )

    raw_budget = environ.get("DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS") or ""
    try:
        max_bookings = int(raw_budget) if raw_budget.strip() else DEFAULT_MAX_BOOKINGS
    except ValueError:
        raise SandboxConfigError(
            f"DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS must be an integer, got {raw_budget!r}"
        )
    if max_bookings < 0:
        raise SandboxConfigError("DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS must not be negative")

    products = parse_list(environ.get("DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS"))
    countries = frozenset(
        code.upper()
        for code in parse_list(environ.get("DHL_FREIGHT_SWEDEN_SANDBOX_COUNTRIES"))
    )
    state_home = environ.get("XDG_STATE_HOME") or str(
        pathlib.Path(environ.get("HOME") or pathlib.Path.home()) / ".local" / "state"
    )
    capture_dir = environ.get("DHL_FREIGHT_SWEDEN_SANDBOX_CAPTURE_DIR") or str(
        pathlib.Path(state_home)
        / "karrio-dhl-freight-sweden"
        / "sandbox"
        / now.strftime("%Y%m%d-%H%M%S")
    )

    return SandboxConfig(
        enabled=environ.get("DHL_FREIGHT_SWEDEN_SANDBOX") == "1",
        client_key=environ.get("KARRIO_DHL_FREIGHT_SWEDEN_CLIENT_KEY") or None,
        account_number=environ.get("KARRIO_DHL_FREIGHT_SWEDEN_ACCOUNT_NUMBER") or None,
        international_account_number=environ.get(
            "KARRIO_DHL_FREIGHT_SWEDEN_INTERNATIONAL_ACCOUNT_NUMBER"
        )
        or None,
        segments=segments or DEFAULT_SEGMENTS,
        products=products or None,
        countries=countries or None,
        max_bookings=max_bookings,
        capture_dir=pathlib.Path(capture_dir),
    )


def check_host(url: str) -> str:
    """Return the host of ``url``, raising unless it is the sandbox host."""
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host != SANDBOX_HOST:
        raise SandboxConfigError(
            f"Refusing a sandbox carrier call to {host or url!r}; only {SANDBOX_HOST} is allowed"
        )
    return host


def skip_reason(config: SandboxConfig, segment: str) -> typing.Optional[str]:
    """Why a segment does not run under ``config``, or None when it runs."""
    if not config.enabled:
        return "DHL_FREIGHT_SWEDEN_SANDBOX is not 1"
    if not config.client_key:
        return "KARRIO_DHL_FREIGHT_SWEDEN_CLIENT_KEY is not set"
    if segment not in config.segments:
        return f"segment {segment} is not in DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS"
    if segment in BOOKING_SEGMENTS and not config.account_number:
        return "KARRIO_DHL_FREIGHT_SWEDEN_ACCOUNT_NUMBER is not set"
    return None


def booking_skip_reason(
    config: SandboxConfig, product: str, country: str
) -> typing.Optional[str]:
    """Why a booking of ``product`` to ``country`` is filtered out, or None."""
    if config.products is not None and product not in config.products:
        return f"product {product} is not in DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS"
    if config.countries is not None and country not in config.countries:
        return f"country {country} is not in DHL_FREIGHT_SWEDEN_SANDBOX_COUNTRIES"
    if (
        provider_units.booking_system(product) == provider_units.BookingSystem.international
        and not config.international_account_number
    ):
        return "KARRIO_DHL_FREIGHT_SWEDEN_INTERNATIONAL_ACCOUNT_NUMBER is not set"
    return None


def mutated_request(
    request: lib.Serializable, mutate: typing.Callable[[dict], dict]
) -> lib.Serializable:
    """The connector's ``request`` with ``mutate`` applied to its serialized payload.

    The connector validates the booking while building ``request``, so a
    payload DHL is expected to reject is derived from a valid request just
    before it is sent; ``mutate`` receives a deep copy.
    """
    return lib.Serializable(
        request.value,
        lambda _: mutate(copy.deepcopy(request.serialize())),
        request.ctx,
    )


def decoded_body(value: typing.Any) -> typing.Any:
    """A JSON text body decoded, empty bodies such as ``[]`` included; other values unchanged."""
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except ValueError:
        return value


class BookingBudget:
    """Process-wide count of booking attempts against a fixed limit.

    An attempt is counted when reserved, before the booking call, so a
    booking whose response is lost still consumes budget.
    """

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.attempts = 0

    def reserve(self) -> bool:
        if self.attempts >= self.limit:
            return False
        self.attempts += 1
        return True


def capture_secrets(config: SandboxConfig) -> typing.Tuple[typing.Optional[str], ...]:
    """The values masked in captures: the client key only.

    The domestic and international customer numbers stay in the captures
    because DHL API Farm support traces sandbox bookings by them, and neither
    is a credential.
    """
    return (config.client_key,)


def redact(value: typing.Any, secrets: typing.Iterable[typing.Optional[str]]) -> typing.Any:
    """Copy ``value`` with secret headers and every secret substring masked."""
    masked = [secret for secret in secrets if secret]

    def _redact(item: typing.Any) -> typing.Any:
        if isinstance(item, dict):
            return {
                key: REDACTED
                if str(key).lower() in SECRET_HEADERS
                else _redact(entry)
                for key, entry in item.items()
            }
        if isinstance(item, (list, tuple)):
            return [_redact(entry) for entry in item]
        if isinstance(item, str):
            return functools.reduce(
                lambda text, secret: text.replace(secret, REDACTED), masked, item
            )
        return item

    return _redact(value)


class Session:
    """Process-wide sandbox state: config, budget, captures, transport guard."""

    def __init__(self, config: SandboxConfig) -> None:
        self.config = config
        self.budget = BookingBudget(config.max_bookings)
        self.sequence = 0
        self.booking_calls = 0
        self._install_transport_guard()

    def gateway(
        self,
        connection_config: typing.Optional[dict] = None,
        client_key: typing.Optional[str] = None,
    ):
        """Create a test-mode gateway on the connector's sandbox host.

        ``client_key`` replaces the configured key, for a case that probes how
        the sandbox answers a key it does not accept.
        """
        if "server_url" in (connection_config or {}):
            raise SandboxConfigError("The sandbox suite does not accept a server_url")
        gateway = karrio.gateway["dhl_freight_sweden"].create(
            dict(
                id="sandbox",
                test_mode=True,
                carrier_id="dhl_freight_sweden",
                client_key=client_key or self.config.client_key,
                account_number=self.config.account_number,
                international_account_number=self.config.international_account_number,
                config=connection_config or {},
            )
        )
        if not gateway.settings.test_mode:
            raise SandboxConfigError("The sandbox gateway is not in test mode")
        check_host(gateway.settings.server_url or "")
        return gateway

    def _install_transport_guard(self) -> None:
        """Refuse any carrier call off the sandbox host or beyond the budget.

        The SDK's ``request`` opens connections through the module-level
        ``helpers.urlopen``, so wrapping it covers every proxy call.
        """
        original = helpers.urlopen

        def guarded_urlopen(request, *args, **kwargs):
            url = request.full_url if hasattr(request, "full_url") else str(request)
            check_host(url)
            if urllib.parse.urlparse(url).path.endswith(BOOKING_PATH):
                self.booking_calls += 1
                if self.booking_calls > self.budget.attempts:
                    raise SandboxConfigError(
                        "Refusing a booking call without a reserved budget attempt"
                    )
            return original(request, *args, **kwargs)

        setattr(helpers, "urlopen", guarded_urlopen)

    @functools.cached_property
    def capture_dir(self) -> pathlib.Path:
        self.config.capture_dir.mkdir(parents=True, exist_ok=True)
        print(f"sandbox captures: {self.config.capture_dir}", file=sys.stderr)
        return self.config.capture_dir

    def _write(self, name: str, content: typing.Any) -> None:
        safe = redact(content, capture_secrets(self.config))
        (self.capture_dir / name).write_text(
            json.dumps(safe, ensure_ascii=False, indent=1, default=str) + "\n"
        )

    def capture(self, gateway, label: str) -> None:
        """Write the gateway's traced calls since the last capture, redacted.

        Each request/response pair becomes ``NNN-<label>.request.json`` and
        ``NNN-<label>.response.json``.
        """
        records = sorted(gateway.tracer.drain_records(), key=lambda r: r.timestamp)
        calls: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
        for record in records:
            data = dict(lib.to_dict(record.data) or {})
            for field in ("data", "response", "error"):
                if field in data:
                    data[field] = decoded_body(data[field])
            calls.setdefault(data.get("request_id") or str(record.timestamp), {})[
                "request" if record.key == "request" else "response"
            ] = dict(key=record.key, **data)

        for call in calls.values():
            self.sequence += 1
            for kind, content in call.items():
                self._write(f"{self.sequence:03d}-{label}.{kind}.json", content)

    def capture_parsed(self, label: str, parsed: typing.Any) -> None:
        """Write the connector's parsed output as ``NNN-<label>.parsed.json``."""
        self.sequence += 1
        self._write(f"{self.sequence:03d}-{label}.parsed.json", parsed)

    def log_booking(self, product: str, shipment_id: typing.Optional[str], test: str) -> None:
        entry = dict(
            product=product,
            shipment_id=shipment_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            test=test,
        )
        with (self.capture_dir / "bookings.jsonl").open("a") as log:
            log.write(json.dumps(redact(entry, capture_secrets(self.config))) + "\n")


def settings_of(gateway) -> connector_settings.Settings:
    return typing.cast(connector_settings.Settings, gateway.settings)


def proxy_of(gateway) -> connector_proxy.Proxy:
    """The connector proxy, which carries the connector-local lookups."""
    return typing.cast(connector_proxy.Proxy, gateway.proxy)


@functools.cache
def config() -> SandboxConfig:
    return load_config(os.environ, datetime.datetime.now())


@functools.cache
def session() -> Session:
    return Session(config())


def require_segment(segment: str) -> Session:
    """Skip the calling test class unless ``segment`` runs; else the session."""
    reason = skip_reason(config(), segment)
    if reason:
        raise unittest.SkipTest(reason)
    return session()
