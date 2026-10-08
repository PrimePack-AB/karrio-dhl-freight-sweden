# karrio-dhl-freight-sweden

## Commands
- `.venv/bin/python -m unittest discover -s tests` - offline tests (repair: `.venv/bin/pip install -r requirements-dev.txt`)
- `pyright` from repo root - type check; trust the CLI over stale editor diagnostics after red-phase TDD
- Sandbox suite (opt-in, books real sandbox shipments): `DHL_FREIGHT_SWEDEN_SANDBOX=1`, `DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS=<segment>`, `DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS=<codes>`, `DHL_FREIGHT_SWEDEN_SANDBOX_COUNTRIES=<codes>`, `DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=<n>` (default 30); narrow single cases with `unittest -k <method>`, never retry rejected bookings
- Territory-table parity with nordic_conventions: `cd ../nordic_conventions && PYTHONPATH=../karrio-dhl-freight-sweden .venv/bin/python -m unittest discover -s tests` - EU VAT tables and postcode normalisation must change identically in both repos
- Docs site preview: `DOCS_DIR=$PWD/docs SITE_BASE=/karrio-dhl-freight-sweden REPO_URL=https://github.com/PrimePack-AB/karrio-dhl-freight-sweden bun run --cwd ../starlight-docs-harness dev` - renders ./docs minus docs/notes/ at http://localhost:4321/karrio-dhl-freight-sweden/; publishing is automatic on docs pushes to main via docs-pages

## Product manual
- Source of truth: DHL Freight Sweden product manual, newest listed at https://dhlpaket.se/dashboard/specifications/products/ - cite the URL, do not crawl it; never vendor the PDF
- Cite as `§x.y pN` against the version and sha named in README; a new manual version means re-mapping every citation (section numbers shift when products are removed)
- Exclusion precedence: manual first; Product API `postalCodeExcludes` only where the manual is silent, and only once a product-matches fixture is committed
- When the sandbox contradicts the manual (e.g. Åland 24003), follow the sandbox, keep the manual citation, and record the deviation in the findings note

## Evidence rules
- Every sandbox claim in README.md, any docs/ page outside docs/notes/, or docs/notes/sandbox/sandbox-findings.md cites a committed redacted fixture in tests/dhl_freight_sweden/fixtures/sandbox/ produced by sandbox_tests evidence tooling; `test_doc_links.py` enforces the links
- Client key is secret (repo-root `.env`, never print); account number 116768 is not secret and must stay unredacted
- The API has no cancel endpoint; sandbox bookings stay booked
- Probe with free lookups (product matches, service points) before spending bookings; `require_product_match=False` forces a single case past the matches gate

## Code map
- karrio/providers/dhl_freight_sweden/units.py - product country lists, payer/Incoterm tables, access points, POSTAL_CODE_EXCLUSIONS, EU VAT-area tables, TERRITORY_PARENTS (territory codes sent as parent country; DHL matches nothing for AX/JE/GG/FO)
- shipment/create.py - up-front booking validation (SENT/EKAER/UIT, GR tax ids, excluded postcodes, QR eligibility) as ShippingSDKDetailedError subclasses
- `karrio.Shipment.create` refuses non-SE shippers, so inbound-product tests (107) call the mapper/proxy directly

## Current State
- 2026-10-08: docs site live at https://primepack-ab.github.io/karrio-dhl-freight-sweden/ via `.github/workflows/docs-pages.yml` and the external harness PrimePack-AB/starlight-docs-harness pinned at v1.1 (commit 14fdd00); the docs-site-design branch is merged and deleted; design, plan with closure notes, and the deferred-maintenance register are in docs/notes/architecture/
