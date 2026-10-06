# karrio-dhl-freight-sweden

## Commands
- `.venv/bin/python -m unittest discover -s tests` - offline tests (repair: `.venv/bin/pip install -r requirements-dev.txt`)
- `pyright` from repo root - type check; trust the CLI over stale editor diagnostics after red-phase TDD
- Sandbox suite (opt-in, books real sandbox shipments): `DHL_FREIGHT_SWEDEN_SANDBOX=1`, `DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS=<segment>`, `DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=<n>`; run single cases with budget 1, never retry rejected bookings

## Product manual
- Source of truth: DHL Freight Sweden product manual, newest listed at https://dhlpaket.se/dashboard/specifications/products/ - cite the URL, do not crawl it; never vendor the PDF
- Cite as `§x.y pN` against the version and sha named in README; a new manual version means re-mapping every citation (section numbers shift when products are removed)

## Evidence rules
- Every sandbox claim in README.md or docs/notes/sandbox/sandbox-findings.md cites a committed redacted fixture in tests/dhl_freight_sweden/fixtures/sandbox/ produced by sandbox_tests evidence tooling
- Client key is secret (repo-root `.env`, never print); account number 116768 is not secret and must stay unredacted
- The API has no cancel endpoint; sandbox bookings stay booked

## Code map
- karrio/providers/dhl_freight_sweden/units.py - product country lists, payer/Incoterm tables, access points, POSTAL_CODE_EXCLUSIONS
- shipment/create.py - up-front booking validation (SENT/EKAER/UIT, GR tax ids, excluded postcodes, QR eligibility) as ShippingSDKDetailedError subclasses
- `karrio.Shipment.create` refuses non-SE shippers, so inbound-product tests (107) call the mapper/proxy directly
