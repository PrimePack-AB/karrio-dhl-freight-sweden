---
title: "Development"
---

This section is for working on the connector itself.
The README is the consumer guide; [Plugin layout](architecture/plugin-layout.md) describes how the package registers with karrio, and [Sandbox suite and evidence](traceability/sandbox-suite.md) describes the opt-in suite that books against the DHL sandbox and the evidence files the documentation cites.
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
