---
title: "Development"
---

This section is for working on the connector itself.
The README is the consumer guide; [Plugin layout](architecture/plugin-layout.md) describes how the package registers with karrio, [Documentation site](architecture/docs-site.md) describes how `docs/` is built and published, and [Sandbox suite and evidence](traceability/sandbox-suite.md) describes the opt-in suite that books against the DHL sandbox and the evidence files the documentation cites.
[Running the sandbox suite](../guides/sandbox-runs.md) shows how to run that suite.
Working notes, including the sandbox findings, are indexed in [docs/notes](../notes/README.md).

## Setup

The connector consumes only upstream karrio SDK surface, so the published `karrio` package from PyPI satisfies the runtime dependency.
Its tests import SDK modules such as `karrio.sdk`, `karrio.references`, and `karrio.core.models`, and run from the repository root against an editable SDK checkout.

Create a virtual environment and install the SDK checkout and the connector with `pip install -r requirements-dev.txt -e .`.
`requirements-dev.txt` installs the SDK editable from `../karrio/modules/sdk`; that path is a local checkout of the karrio SDK, and any checkout works for this connector, upstream or fork, because it uses no fork-only SDK surface.
A `git+https` install of the SDK cannot replace the checkout, because pip recursively fetches the monorepo's private submodules that `modules/sdk` does not need.

## Tests and type checking

Run the offline suite and the type check from the repository root:

```bash
.venv/bin/python -m unittest discover -s tests
pyright
```

The offline suite includes `tests/dhl_freight_sweden/test_examples.py`, which runs the scripts in `examples/` with network calls patched to fail, and `tests/dhl_freight_sweden/test_doc_links.py`, which checks that every relative link in the README and `docs/` resolves and that every sandbox evidence file is linked from at least one document.

## Product manual citations

The connector and its documentation cite the DHL Freight (Sweden) product manual, version 5.26, updated 2026-10-01 and valid from 2026-11-01, as `§x.y pN`.
DHL lists the current manual at <https://dhlpaket.se/dashboard/specifications/products/>, and the cited copy of version 5.26 has sha256 `050660c37ba93d1ae9514c50dfa42c2010bc87763ccaff51a740b2526af11b73`.
The manual is cited rather than vendored, and a new manual version means re-mapping every citation, because section numbers shift when products are removed.

## IFTMIN shipment instruction citations

The products' booking systems are cited from the DHL Freight (Sweden) Shipment Instruction IFTMIN UN S.93A S3, version 3.7, issued and valid from 2025-05-05, as `IFTMIN v3.7 pN`.
DHL lists it at <https://dhlpaket.se/dashboard/specifications/edi/>, and the cited copy has sha256 `5f6900bdc60121de6c789f4bc5406026a45ab4bca7c6008928200a2ca1926e5d`.
The connector books through the API Farm rather than EDI, and cites the IFTMIN for the UNB recipient addresses on p10, which assign each product to DHL's domestic or international booking system, for the party id length on p32, and, in Appendix A on pp59-61, for the 103 service point terminal id and the parties each product takes; it is cited rather than vendored like the manual.

## Breaking changes

Rating and booking follow the lanes that the "Valid countries" tables of manual v5.26 allow for each product, listed in [Products](../concepts/products.md#lanes).
Rating drops rates on other lanes, merchant rate sheets included, for example 233 from SE to GR and 601 from SE to LI, and an explicitly requested product adds a `destination_not_supported` message instead.
Booking fails before the booking request with `ProductLaneError` on such a lane (see [Booking rules](../concepts/booking-rules.md#product-lanes)), with `JointDeclarationDestinationError` for the customs joint declaration to a recipient country other than NO or CH across the EU VAT area border (see the README's customs services), and with `TerritoryPostalCodeError` for a territory code AX, IC, EA, FO, or GL whose postal code is missing or outside the territory (see [Destinations](../concepts/destinations.md#special-territories)).

The international products 202, 205, 233, SPI, and 601 send the new `international_account_number` setting as the Consignor party id instead of `account_number`, and booking one fails before the booking request with `InternationalAccountNumberError` when the setting is missing or longer than 15 characters (see [Booking rules](../concepts/booking-rules.md#customer-numbers)).
There is no fallback to `account_number`, so a connection that books these products must add the international customer number.

Product 103 sends the four-digit terminal id nnnn of a service point id SE-nnnn00 as the AccessPoint party id instead of the id as given, per manual §10.14.2.1 p231 and IFTMIN v3.7 p59, and booking 103 fails before the booking request with `ServicePointIdError` for an id that is neither SE-nnnn00 nor four digits (see [Booking rules](../concepts/booking-rules.md#access-points)).

Product 112 accepts only payer code 023, per manual §5.3 p19, where it previously accepted 022 as well.
Booking 112 with an explicit payer code 022, or with the Incoterm CPT, CIP, DAP, or DPU, which translate to 022, fails before the booking request with `PayerCodeError`; DDP still translates to 023 (see [Booking rules](../concepts/booking-rules.md#payer-codes)).

## Known limitations

The README is also the PyPI long description (`readme = "README.md"` in `pyproject.toml`), and its relative links to `docs/`, `examples/`, and the evidence files do not resolve on PyPI; fixing them is deferred until the package is published.
