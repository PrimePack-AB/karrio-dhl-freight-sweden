---
title: "Plugin layout"
---

## Registration

The connector registers through the `karrio.plugins` entry point group under the id `dhl_freight_sweden` (`[project.entry-points."karrio.plugins"]` in `pyproject.toml`), so installing the package makes the carrier available to every karrio SDK runtime and uninstalling it removes the carrier.
The `METADATA` object in `karrio/plugins/dhl_freight_sweden/__init__.py` binds the mapper, proxy, settings, service and option units, and connection configs that the entry point exposes.
Karrio derives the advertised capabilities from the proxy's public methods: `create_shipment` and `validate_address` give shipping and address validation, and `get_rates` gives rating.
The connector-local lookups `find_product_matches` and `find_service_points` register no capability.

## Tracking and cancellation

The API Farm has no tracking or cancellation endpoint, so the proxy defines neither `get_tracking` nor `cancel_shipment` and karrio advertises neither capability.
`Settings.tracking_url` in `karrio/providers/dhl_freight_sweden/utils.py` builds the public DHL tracking web page URL that the connector returns as `meta.carrier_tracking_link`; it is a link for people, not a tracking API.
`karrio/providers/dhl_freight_sweden/shipment/cancel.py` is a stub that returns a `not_supported` message if it is ever wired, and the proxy does not reach it.

## Namespace packages and pyright

`pyrightconfig.json` resolves the SDK from the `../karrio/modules/sdk` checkout and the project venv from `.venv`, and checks `karrio/`, `examples/`, `sandbox_tests/`, and `tests/`.
At runtime `karrio` is a `pkgutil.extend_path` namespace shared by the SDK and this repository, which pyright cannot follow: the SDK's regular `karrio`, `karrio.providers`, `karrio.mappers`, `karrio.schemas`, and `karrio.plugins` packages would shadow this repository's directories.
The empty `__init__.pyi` files in those five directories make them regular packages for pyright, so imports of both the SDK and the connector resolve.
They have no runtime effect and are excluded from the wheel by `[tool.setuptools.exclude-package-data]`, so an installed connector never shadows the SDK's `karrio/__init__.py`.
