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

## Releasing

Releases are in-development versions published as GitHub releases of this repository only, listed in its [releases feed](https://github.com/PrimePack-AB/karrio-dhl-freight-sweden/releases.atom); nothing is published to PyPI.
Versions are CalVer `YYYY.M.N`, without leading zeros, where `N` counts releases within the month, and each is tagged `vYYYY.M.N`.
The `karrio-ref` key under `[tool.primepack]` in `pyproject.toml` names the SDK the release is tested against and must be a `snapshot-YYYY.MM.DD.N` tag of the Joaqim/karrio fork, because the fork's `develop` branch is regenerated and force-pushed and its commits are not durable.
To cut a release, run `scripts/release.sh YYYY.M.N` on a clean `main`; it sets the `[project]` version, commits `chore(release): YYYY.M.N`, creates the annotated tag, and prints the push command without running it.
Pushing the tag runs `.github/workflows/release.yml`, which checks the tag against the version with `scripts/check-release-tag.sh`, runs the offline suite against the fork SDK at `karrio-ref`, and creates the release with generated notes that name the fork snapshot it was tested against; the connector also works with upstream karrio.

## Product manual citations

The connector and its documentation cite the DHL Freight (Sweden) product manual, version 5.26, updated 2026-10-01 and valid from 2026-11-01, as `§x.y pN`.
DHL lists the current manual at <https://dhlpaket.se/dashboard/specifications/products/>, and the cited copy of version 5.26 has sha256 `050660c37ba93d1ae9514c50dfa42c2010bc87763ccaff51a740b2526af11b73`.
The manual is cited rather than vendored, and a new manual version means re-mapping every citation, because section numbers shift when products are removed.

## IFTMIN shipment instruction citations

The products' booking systems are cited from the DHL Freight (Sweden) Shipment Instruction IFTMIN UN S.93A S3, version 3.7, issued and valid from 2025-05-05, as `IFTMIN v3.7 pN`.
DHL lists it at <https://dhlpaket.se/dashboard/specifications/edi/>, and the cited copy has sha256 `5f6900bdc60121de6c789f4bc5406026a45ab4bca7c6008928200a2ca1926e5d`.
The connector books through the API Farm rather than EDI, and cites the IFTMIN for the UNB recipient addresses on p10, which assign each product to DHL's domestic or international booking system — a mapping the manual's per-product "Information to be sent via EDI or API" tables corroborate (§5.2 p16, §5.14 p64) — for the party id length on p32, and, in Appendix A on pp59-61, for the 103 service point terminal id and the parties each product takes; it is cited rather than vendored like the manual.

## API Farm specification citations

Comments, tests, and documentation cite the DHL Freight (Sweden) API Farm OpenAPI specifications by title and version, for example "PickupRequest API 2.10.0".
DHL publishes them in Swagger in the API Farm, which requires registering an organisation and an application, as the [API Farm get-started page](https://dhlpaket.se/dashboard/services/api-farm/get-started/) describes; the [API Farm page](https://dhlpaket.se/dashboard/services/api-farm/) lists an overview page per API.
Each specification names its sandbox server under `https://test-api.freight-logistics.dhl.com/`, which answered HTTP 401 without a client key on 2026-10-20, so no public per-file URL is cited.
Only the TransportInstruction specification names a contact, the API Farm page and `se.dbi@dhl.com`; none carries a licence, terms of service, or `externalDocs` field.

The cited copies were vendored into the karrio fork on 2026-08-11 and are no longer included in this repository; the overview pages were checked on 2026-10-20.
To keep a local copy for development, place the JSON files under `vendor/se-api-farm/`, which `.gitignore` excludes; the schema check in `tests/dhl_freight_sweden/test_sandbox_harness.py` runs only when `vendor/se-api-farm/pickup-request-api-2.10.0.json` is present.

| File | Title | Version | sha256 | DHL overview page |
| --- | --- | --- | --- | --- |
| `additional-service-api-2.10.0.json` | Additional Service API | 2.10.0 | `049cfa208c990bc2ae01c02bc3257f7bae894482797cec1b4f13236917f87554` | [AdditionalService API](https://dhlpaket.se/dashboard/services/api-farm/additionalservice/) |
| `eid-api-2.10.0.json` | EId API | 2.10.0 | `629cc4ed1beabfc9294f43e807925991e0075ca2fe88ef23a1aee4159b3c53d5` | [e-ID API](https://dhlpaket.se/dashboard/services/api-farm/e-id/) |
| `home-delivery-locator-api-2.10.0.json` | HomeDeliveryLocator API | 2.10.0 | `b86dcf08320a3a09709c55a291d329cf64dddf4731748e79777889a1b6a2895c` | [HomeDeliveryLocator API](https://dhlpaket.se/dashboard/services/api-farm/homedeliverylocator/) |
| `pallet-api-2.10.0.json` | Pallet API | 2.10.0 | `d776df5c4fa97d62723e652e80942927b809e93e0d98c74b8c291e10073d6515` | none listed |
| `pickup-request-api-2.10.0.json` | PickupRequest API | 2.10.0 | `2140fd50864a3c6367b1d54af54c3bcaae57ad27bdd539438bba3e4c48549894` | [PickupRequest API](https://dhlpaket.se/dashboard/services/api-farm/pickuprequest/) |
| `postalcode-api-2.10.0.json` | Postalcode API | 2.10.0 | `8a33a298b7fc925f68f81c7059c6ad0115280152fa2d62d5770aef40fcbaa1c2` | [PostalCodes API](https://dhlpaket.se/dashboard/services/api-farm/postalcodes/) |
| `pricequote-api-2.10.0.json` | PriceQuote API | 2.10.0 | `20f68b2eb16e26934335dd8566948b35257e9502ccf09f4cbaf1d76cac309a7a` | [PriceQuote API](https://dhlpaket.se/dashboard/services/api-farm/pricequote/) |
| `print-api-2.10.0.json` | Print API | 2.10.0 | `166698e8a2a003d411565e5c27db4735b73b6244dfefbb9937be7d4be3829549` | [Print API](https://dhlpaket.se/dashboard/services/api-farm/print/) |
| `product-api-2.10.0.json` | Product API | 2.10.0 | `d69b561096d55a3be915cee4843515993798b4478ae94b63872d8156a6ece69e` | [Product API](https://dhlpaket.se/dashboard/services/api-farm/product/) |
| `servicepoint-api-2.10.0.json` | Servicepoint API | 2.10.0 | `1d9b8cc31273df2099d61346d0d8ced97e14471384b98621bfe96a3827d1173a` | [ServicePointLocator API](https://dhlpaket.se/dashboard/services/api-farm/servicepointlocator/) |
| `terminal-api-2.10.0.json` | Terminal API | 2.10.0 | `3b7e48f9cbc84ebb2a176dfdcdd238b7f92a7970a44810db3a47ecd6d3aa7355` | none listed |
| `timetable-api-2.10.0.json` | TimeTable Api | 2.10.0 | `f015284f31ec0a60631df61a967fc5f9c65879110d650939acf0e0065cd7abf6` | [TimeTable API](https://dhlpaket.se/dashboard/services/api-farm/timetable/) |
| `transport-instruction-2.10.0.json` | TransportInstruction | 2.10.0 | `553baeca6456183142f03af2252d47391a21484e68811c333accf76c354e22ac` | [TransportInstruction API](https://dhlpaket.se/dashboard/services/api-farm/transportinstruction/) |

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
