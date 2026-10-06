---
title: "Gap-filling sandbox matrix implementation plan, 2026-10-06"
---

# Gap-filling sandbox matrix implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill every product-by-lane-class sandbox booking gap for products 202, 205, 233, 601, 401, 109, and 112, and raise the suite's default booking budget from 10 to 30 so the matrix runs in one pass.

**Architecture:** Nine new cases in the `booking-export` segment (freight intra-EU DK, freight extra-EU NO with customs, and Standard-customs variants for 112 and 109), one domestic case in `booking-approved` (401), one conditional forced 205 case, and evidence-pipeline registration for every resulting booking. The spec is [2026-10-06-sandbox-gap-filling-matrix-design.md](2026-10-06-sandbox-gap-filling-matrix-design.md).

**Tech stack:** Python stdlib `unittest`, the repo's sandbox harness (`sandbox_tests/dhl_freight_sweden/`), `pyright`, the evidence rebuilder `sandbox_tests.dhl_freight_sweden.evidence`.

**Verification model:** These are live-only sandbox tests; the default offline run never discovers them, so classic red-green TDD does not apply. The falsifiable offline gates are: module discovery with the sandbox disabled imports everything and skips every test, `pyright` passes, and `.venv/bin/python -m unittest discover -s tests` stays green. The live passes in tasks 5, 7, and 8 are the integration tests.

**Safety rules for every live command:**
- Source credentials with `set -a; . ./.env; set +a` and never print `.env` contents, the client key, or the environment afterwards.
- Never retry a rejected booking; the API has no cancel endpoint, so every attempt is permanent spend.
- If a case fails unexpectedly (DHL error-level messages, assertion failure), stop the whole pass at once — do not let later cases spend — and report the capture directory and the failure. Already-spent bookings are logged in `bookings.jsonl`.
- All commands run from the repository root `/home/joaqim/projects/karrio-dhl-freight-sweden` on branch `sandbox-gap-filling-matrix`; confirm `git branch --show-current` outputs `sandbox-gap-filling-matrix` before the first edit of each task.

**File map:**

- Modify `sandbox_tests/dhl_freight_sweden/test_booking_export.py` — Incoterm entries, ten new test methods, module docstring.
- Modify `sandbox_tests/dhl_freight_sweden/test_booking_approved.py` — the 401 domestic method, module docstring.
- Modify `sandbox_tests/dhl_freight_sweden/harness.py` — `DEFAULT_MAX_BOOKINGS`.
- Modify `sandbox_tests/dhl_freight_sweden/evidence.py` — new `SUITE_BOOKINGS` tuples (and, only if the conditional 205 case rejects, a rejection entry).
- Modify `README.md` — env-table default, `-k` narrowing note, segment descriptions, planned-segments line.
- Modify `CLAUDE.md` — the sandbox budget-policy bullet.
- Modify `docs/notes/sandbox/sandbox-findings.md` — bookings rows, Untested shrink, deviations.
- Create `tests/dhl_freight_sweden/fixtures/sandbox/booking-*.json` via the evidence rebuild.

---

### Task 1: Freight Incoterms in the export template

**Files:**
- Modify: `sandbox_tests/dhl_freight_sweden/test_booking_export.py:32` and the module docstring.

- [ ] **Step 1: Extend the Incoterm table**

Replace line 32:

```python
INCOTERMS = {"109": "DAP", "112": "DDP"}
```

with:

```python
INCOTERMS = {"109": "DAP", "112": "DDP", "202": "DAP", "205": "DAP", "233": "DAP", "601": "DAP"}
```

- [ ] **Step 2: Extend the module docstring's customs paragraph**

In the module docstring, after the sentence ending `...the customs service that needs no registration identifier.`, the paragraph currently explains the Combiterm translation for 109 and 112. Append one sentence to that paragraph, before the closing quotes:

```
The freight products 202, 205, 233, and 601 map to DAP, and each freight
case also passes that Incoterm as its explicit payer code, because the
freight products have no default payer code.
```

- [ ] **Step 3: Verify imports and types**

Run: `.venv/bin/python -m unittest discover -v -s sandbox_tests 2>&1 | tail -n 2`
Expected: `OK (skipped=N)` for every test — the sandbox is disabled, so nothing runs, but the module imports.

Run: `pyright`
Expected: 0 errors.

Run: `.venv/bin/python -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 4: Commit**

```bash
git add sandbox_tests/dhl_freight_sweden/test_booking_export.py
git commit -m "feat: map the DAP incoterm for the freight products in sandbox customs"
```

---

### Task 2: Freight and Standard-customs cases in booking-export

**Files:**
- Modify: `sandbox_tests/dhl_freight_sweden/test_booking_export.py` (test methods and module docstring).

- [ ] **Step 1: Update the module docstring**

Replace the docstring's first paragraph (lines 1-12) with:

```python
"""Sandbox segment ``booking-export``: export products from SE to a destination matrix.

Each test books 109 (Parcel Connect B2C, to a service point) or 112 (Parcel
Connect Plus, home delivery) from SE to PL, RO, HU, or NO, 109 to a DK
ParcelShop, and 112 to FR and GB, which product manual v5.26 adds for 112,
GB only according to a separate agreement. Åland (FI 22100) is booked with
112 and customs and with 109 without customs data, and Northern Ireland
(GB BT1 1AA) with 202 without customs data. The freight products 202, 205,
233, and 601 book to DK inside the EU VAT area and to NO with customs
handling full service, each with the explicit DAP payer code, and 112 and
109 book to NO with customs handling Standard and a made-up EORI number.
Before spending a booking it checks for free that product matches offer the
product for the lane and, for 109, that a service point near the recipient
accepts it, and skips otherwise. Lanes to PL declare SENT free explicitly.
"""
```

Keep the existing second paragraph (the NO/GB customs explanation) unchanged below it.

- [ ] **Step 2: Add the nine pass-1 cases and the conditional forced case**

Insert after `test_book_112_gb` (line 193) and before `test_book_109_dk_parcel_shop`:

```python
    def test_book_112_no_customs_standard(self):
        self.export("112", "NO", standard_customs=True)

    def test_book_109_no_customs_standard(self):
        self.export("109", "NO", standard_customs=True)

    def test_book_202_dk(self):
        self.export(
            "202", "DK", with_customs=False,
            extra_options={"dhl_freight_sweden_payer_code": "DAP"},
        )

    def test_book_202_no_customs_full(self):
        self.export(
            "202", "NO", extra_options={"dhl_freight_sweden_payer_code": "DAP"}
        )

    def test_book_205_dk(self):
        self.export(
            "205", "DK", with_customs=False,
            extra_options={"dhl_freight_sweden_payer_code": "DAP"},
        )

    def test_book_205_no_customs_full(self):
        self.export(
            "205", "NO", extra_options={"dhl_freight_sweden_payer_code": "DAP"}
        )

    def test_book_233_dk(self):
        self.export(
            "233", "DK", with_customs=False,
            extra_options={"dhl_freight_sweden_payer_code": "DAP"},
        )

    def test_book_233_no_customs_full(self):
        self.export(
            "233", "NO", extra_options={"dhl_freight_sweden_payer_code": "DAP"}
        )

    def test_book_601_no_customs_full(self):
        self.export(
            "601", "NO", extra_options={"dhl_freight_sweden_payer_code": "DAP"}
        )
```

Insert at the end of the class, after `test_book_202_gb_northern_ireland_without_customs`:

```python
    def test_book_205_no_forced(self):
        # No probe has ever matched 205 (README.md, excluded postal codes);
        # like the 112 GB case, this books past the matches check to record
        # DHL's answer.
        self.export(
            "205",
            "NO",
            require_product_match=False,
            extra_options={"dhl_freight_sweden_payer_code": "DAP"},
        )
```

- [ ] **Step 3: Verify offline**

Run: `.venv/bin/python -m unittest discover -v -s sandbox_tests 2>&1 | tail -n 2`
Expected: `OK (skipped=6)` — the harness skips per class in `setUpClass`, so the skip count is invariant at six; the gate is a clean import with zero tests run.

Run: `pyright`
Expected: 0 errors.

Run: `.venv/bin/python -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 4: Commit**

```bash
git add sandbox_tests/dhl_freight_sweden/test_booking_export.py
git commit -m "test: add the freight and Standard customs sandbox booking cases"
```

---

### Task 3: The 401 domestic case in booking-approved

**Files:**
- Modify: `sandbox_tests/dhl_freight_sweden/test_booking_approved.py`.

- [ ] **Step 1: Update the module docstring**

Replace the docstring's second sentence (line 3-6) with:

```python
Each test books one shipment and prints its label: 102 and 401 (SE domestic),
601 (SE to DK), and 118 (SE home delivery behind the ``enforce`` postal-code
pre-flight). Bookings count against ``DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS``
and cannot be cancelled through the API.
```

- [ ] **Step 2: Add the case**

Insert after `test_book_102_domestic`:

```python
    def test_book_401_domestic(self):
        booking.book(
            self,
            self.session,
            self.gateway,
            "401",
            dict(
                service="401",
                shipper=booking.SHIPPER,
                recipient=booking.RECIPIENTS["SE"],
                parcels=[booking.PARCEL],
            ),
        )
```

- [ ] **Step 3: Verify offline**

Run: `.venv/bin/python -m unittest discover -v -s sandbox_tests 2>&1 | tail -n 2`
Expected: `OK (skipped=6)` — per-class skipping keeps the count invariant; the gate is a clean import with zero tests run.

Run: `pyright` and `.venv/bin/python -m unittest discover -s tests`
Expected: 0 errors; OK.

- [ ] **Step 4: Commit**

```bash
git add sandbox_tests/dhl_freight_sweden/test_booking_approved.py
git commit -m "test: add the 401 domestic sandbox booking case"
```

---

### Task 4: Budget default and selector documentation

**Files:**
- Modify: `sandbox_tests/dhl_freight_sweden/harness.py:40`.
- Modify: `README.md:652` and `README.md:671-672`.
- Modify: `CLAUDE.md` (Commands section, sandbox bullet).

- [ ] **Step 1: Raise the default**

Replace in `harness.py`:

```python
DEFAULT_MAX_BOOKINGS = 10
```

with:

```python
DEFAULT_MAX_BOOKINGS = 30
```

- [ ] **Step 2: Update the README env table**

Replace the row at `README.md:652`:

```markdown
| `DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS` | `10` | booking attempts allowed in one process |
```

with:

```markdown
| `DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS` | `30` | booking attempts allowed in one process |
```

- [ ] **Step 3: Document `-k` selection in the README**

At `README.md:672`, replace:

```markdown
To book a single product or lane, narrow the selectors, for example `DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS=booking-approved DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS=102 DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=1`.
```

with:

```markdown
To book a single product or lane, narrow the selectors, for example `DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS=booking-approved DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS=102 DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=1`.
The selectors cannot separate two cases that share a product and country, so add `unittest -k <method name>` per case (repeatable, matched as a substring of the test id) to rerun exactly one case, for example `-k test_book_112_no_customs_standard`.
```

- [ ] **Step 4: Update the CLAUDE.md policy bullet**

In `CLAUDE.md` under Commands, replace:

```markdown
- Sandbox suite (opt-in, books real sandbox shipments): `DHL_FREIGHT_SWEDEN_SANDBOX=1`, `DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS=<segment>`, `DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=<n>`; run single cases with budget 1, never retry rejected bookings
```

with:

```markdown
- Sandbox suite (opt-in, books real sandbox shipments): `DHL_FREIGHT_SWEDEN_SANDBOX=1`, `DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS=<segment>`, `DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS=<codes>`, `DHL_FREIGHT_SWEDEN_COUNTRIES=<codes>`, `DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=<n>` (default 30); narrow single cases with `unittest -k <method>`, never retry rejected bookings
```

- [ ] **Step 5: Verify**

Run: `.venv/bin/python -c "from sandbox_tests.dhl_freight_sweden import harness; assert harness.DEFAULT_MAX_BOOKINGS == 30; print('ok')"`
Expected: `ok`.

Run: `pyright` and `.venv/bin/python -m unittest discover -s tests`
Expected: 0 errors; OK.

- [ ] **Step 6: Commit**

```bash
git add sandbox_tests/dhl_freight_sweden/harness.py README.md CLAUDE.md
git commit -m "feat: raise the sandbox default booking budget to 30"
```

---

### Task 5: Pass 1 — the freight matrix live run

**Files:** none in the repository; captures land under `~/.local/state/karrio-dhl-freight-sweden/sandbox/<run>/`.

- [ ] **Step 1: Run the nine cases**

```bash
set -a; . ./.env; set +a
DHL_FREIGHT_SWEDEN_SANDBOX=1 \
DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS=booking-export \
DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS=202,205,233,601,112,109 \
DHL_FREIGHT_SWEDEN_COUNTRIES=DK,NO \
DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=12 \
.venv/bin/python -m unittest discover -v -s sandbox_tests \
  -k test_book_112_no_customs_standard \
  -k test_book_109_no_customs_standard \
  -k test_book_202_dk \
  -k test_book_202_no_customs_full \
  -k test_book_205_dk \
  -k test_book_205_no_customs_full \
  -k test_book_233_dk \
  -k test_book_233_no_customs_full \
  -k test_book_601_no_customs_full 2>&1 | tee /tmp/sandbox-pass1.log
```

Expected: the seven non-205 cases book (`ok`), except that the 109 Standard case may end in a service-point skip, which costs nothing; the two 205 cases either book or end in `skipped ... product matches do not offer 205 from SE to DK/NO` — a skip costs nothing.
Any `FAILED` is unexpected: stop, capture the run directory from the `sandbox captures:` line in the log, and report back before touching anything else.

- [ ] **Step 2: Record what happened**

```bash
RUN=<run-dir-from-the-log>
ls ~/.local/state/karrio-dhl-freight-sweden/sandbox/$RUN/
cat ~/.local/state/karrio-dhl-freight-sweden/sandbox/$RUN/bookings.jsonl
```

Expected: one `bookings.jsonl` line per booking with a shipment id; capture files numbered sequentially (`001-product-matches-...` pair, `002-...parsed.json`, then per product either the 109 service-point pair or straight to `NNN-booking-<product>` transport-instruction and print pairs).
Note the run directory and each booking id — task 6 needs them. Note the UTC time from each booking response's `Date` header for the findings rows.

---

### Task 6: Pass 1 evidence and documentation

**Files:**
- Modify: `sandbox_tests/dhl_freight_sweden/evidence.py` (SUITE_BOOKINGS).
- Create: `tests/dhl_freight_sweden/fixtures/sandbox/booking-<id>-<product>-se-<dest>.json`.
- Modify: `docs/notes/sandbox/sandbox-findings.md`, `README.md:657-661`, `README.md:677`.

- [ ] **Step 1: Add one SUITE_BOOKINGS tuple per booking**

Each tuple's shape (from `evidence.py:433-497`): `(file name, summary, product, route, run dir, stems, test id, primary)`.
The `stems` are the capture file stems without the `.request.json`/`.response.json` suffix: the transport-instruction exchange and the print exchange, both labeled `booking-<product>`, plus for 109 the `service-points-109-no` pair before them.
`primary` is the index of the transport-instruction exchange within `stems` — 0 without a service-point lookup, 1 with.
Read the exact numbers from the run directory listing; they are sequential across the whole process, so later cases have higher prefixes.

Worked example for a 202 DK booking whose transport instruction is `013-booking-202` in run `20261006-HHMMSS`:

```python
    ("booking-<id>-202-se-dk.json", "202 SE to DK with payer code DAP, then printed.",
     "202", "SE 11143 -> DK 1620", "20261006-HHMMSS", ("013-booking-202", "014-booking-202"),
     "test_booking_export.test_book_202_dk", 0),
```

Draft summaries for the others, adjusted to what the responses echo (payer code, customs service, EORI, service-point id for 109):

- `"<id> 202 SE to NO with payer code DAP, customsHandlingFullService, and a ProformaInvoice, then printed."`
- same shape for 205 and 233 to DK and NO, 601 to NO
- `"<id> 112 SE to NO with payer code 023, customsHandlingStandard, a made-up EORI number, and a ProformaInvoice, then printed."`
- `"<id> 109 SE to NO with payer code 022, customsHandlingStandard, a made-up EORI number, and a ProformaInvoice, to ParcelShop <id>, then printed."` — with stems `("NNN-service-points-109-no", "NNN-booking-109", "NNN+1-booking-109")` and primary 1.

Place the new tuples at the end of `SUITE_BOOKINGS`, before the closing `)`, in booking order.

- [ ] **Step 2: Rebuild and check reproducibility**

```bash
.venv/bin/python -m sandbox_tests.dhl_freight_sweden.evidence
git status --short tests/dhl_freight_sweden/fixtures/sandbox/
```

Expected: only new `booking-<id>-*.json` files; no existing fixture modified (byte reproducibility — a modified existing file means a wrong tuple, not a rebuilder fault).

- [ ] **Step 3: Run the offline gates**

Run: `.venv/bin/python -m unittest discover -s tests`
Expected: OK — the evidence contract tests parse every new fixture with the connector's parsers and check the redaction.

Run: `pyright`
Expected: 0 errors.

- [ ] **Step 4: Findings note rows**

In `docs/notes/sandbox/sandbox-findings.md`, append one row per booking to the bookings table (lines 35-57) in the existing column format, with the UTC response time, payer code, customs (`full service, ProformaInvoice` / `standard, EORI SE0000000000, ProformaInvoice`), service point or `none`, routing code from the response, and the `[booking-<id>][b-<suffix>]` link; add the link definitions to the appendix (lines 237-294).
Update the table preamble's booking count and year-listing sentence if it enumerates dates.
Rewrite the Untested lines that this pass closes (lines 228-232): drop 205, 233, and 401 from the never-booked lists, extend the 601 sentence with NO, and reduce the customs sentence to what remains untested (own declaration, joint declaration including 109 with 023, VOEC, other non-EU destinations). If DHL deviated from the manual in any response, add a Deviations entry citing the fixture instead of silently normalizing.

- [ ] **Step 5: README segment description**

Update `README.md:659-661`: the `booking-export` paragraph gains the freight lanes to DK and NO with explicit DAP payer codes, the NO Standard-customs variants for 112 and 109, and the sentence that the 205 cases skip unless product matches offer 205.
Replace the now-stale `README.md:677` planned-segments sentence:

```markdown
Planned segments, not yet implemented: a wider customs matrix covering the other customs services and non-EU destinations, and the freight products.
```

with a sentence naming what remains unbooked (own and joint declaration, VOEC, further non-EU destinations) — or delete the line if task 8's outcome closes it fully.

- [ ] **Step 6: Commit**

```bash
git add sandbox_tests/dhl_freight_sweden/evidence.py tests/dhl_freight_sweden/fixtures/sandbox/ docs/notes/sandbox/sandbox-findings.md README.md
git commit -m "test: add evidence for the freight matrix and Standard customs bookings"
```

---

### Task 7: Pass 2 — the 401 domestic live run and evidence

**Files:** `sandbox_tests/dhl_freight_sweden/evidence.py`, `tests/dhl_freight_sweden/fixtures/sandbox/`, `docs/notes/sandbox/sandbox-findings.md`, `README.md:657`.

- [ ] **Step 1: Run the case**

```bash
set -a; . ./.env; set +a
DHL_FREIGHT_SWEDEN_SANDBOX=1 \
DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS=booking-approved \
DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS=401 \
DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=1 \
.venv/bin/python -m unittest discover -v -s sandbox_tests 2>&1 | tee /tmp/sandbox-pass2.log
```

Expected: `test_book_401_domestic ... ok`; the segment's other cases skip on the product filter before any spend.
The `PRODUCTS=401` filter isolates the case, so no `-k` is needed.

- [ ] **Step 2: Evidence tuple, rebuild, gates**

Add the SUITE_BOOKINGS tuple (stems are the two `booking-401` exchanges, primary 0):

```python
    ("booking-<id>-401-se-se.json", "401 within SE with payer code 1, then printed.",
     "401", "SE 11143 -> SE 11151", "<run-dir>", ("NNN-booking-401", "NNN+1-booking-401"),
     "test_booking_approved.test_book_401_domestic", 0),
```

Rebuild with `.venv/bin/python -m sandbox_tests.dhl_freight_sweden.evidence`, then run `.venv/bin/python -m unittest discover -s tests` and `pyright` — OK and 0 errors.

- [ ] **Step 3: Documentation**

Findings note: bookings row; drop 401 from the Untested never-booked list (line 228).
README `booking-approved` sentence (line 657): add 401 within SE.

- [ ] **Step 4: Commit**

```bash
git add sandbox_tests/dhl_freight_sweden/evidence.py tests/dhl_freight_sweden/fixtures/sandbox/ docs/notes/sandbox/sandbox-findings.md README.md
git commit -m "test: add evidence for the 401 domestic booking"
```

---

### Task 8 (conditional): Pass 3 — the forced 205 case

Run only if task 5 showed both 205 cases skipped as unoffered. Skip this task entirely otherwise.

- [ ] **Step 1: Run the forced case**

```bash
set -a; . ./.env; set +a
DHL_FREIGHT_SWEDEN_SANDBOX=1 \
DHL_FREIGHT_SWEDEN_SANDBOX_SEGMENTS=booking-export \
DHL_FREIGHT_SWEDEN_SANDBOX_PRODUCTS=205 \
DHL_FREIGHT_SWEDEN_COUNTRIES=NO \
DHL_FREIGHT_SWEDEN_SANDBOX_MAX_BOOKINGS=1 \
.venv/bin/python -m unittest discover -v -s sandbox_tests -k test_book_205_no_forced 2>&1 | tee /tmp/sandbox-pass3.log
```

Two outcomes, both acceptable:
`ok` — 205 booked; register it exactly as in task 6's recipe.
`FAILED` — DHL rejected (the assertion in `booking.book` fails by design, the same way the 112 GB answer was captured); the capture still holds the request and response. Register it as rejection evidence: grep `evidence.py` for `rejection-22005-112` to find the hand-written entry pattern for a booking-segment rejection, and follow it with the observed error code in the file name (`rejection-<code>-205-se-no.json`) and a REJECTIONS-style tuple or `@evidence` function. Add the findings rejections-table row and the Untested/README sentence stating what DHL answered for 205.

- [ ] **Step 2: Rebuild, gates, commit**

Same gates as task 6 step 2-3, then:

```bash
git add sandbox_tests/dhl_freight_sweden/evidence.py tests/dhl_freight_sweden/fixtures/sandbox/ docs/notes/sandbox/sandbox-findings.md README.md
git commit -m "test: record DHL's answer for a forced 205 booking to NO"
```

---

### Task 9: Final verification and integration offer

- [ ] **Step 1: Full gates**

Run: `.venv/bin/python -m unittest discover -s tests`
Expected: OK.

Run: `pyright`
Expected: 0 errors.

Run: `git -C . log --oneline main..sandbox-gap-filling-matrix`
Expected: the design note, plan note, and one commit per task above.

- [ ] **Step 2: Consistency sweep**

Check that every new sentence in `README.md` and `docs/notes/sandbox/sandbox-findings.md` naming a booking or rejection cites its fixture, that `bookings.jsonl` booking count equals the new evidence files plus any rejection, and that no fixture in `git status` is left untracked.

- [ ] **Step 3: Report and offer integration**

Report the booking ids, total spend, and any deviations to the user, and offer the fast-forward integration: `git checkout main && git merge --ff-only sandbox-gap-filling-matrix` (rebase first if main moved). Do not merge without the user's go-ahead.
