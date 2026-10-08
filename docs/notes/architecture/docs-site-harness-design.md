---
title: "Docs site harness design"
created: 2026-10-08
---

Design for publishing this repository's `./docs` tree as a Starlight site on GitHub Pages, with no application code in this repository.

The decisions were settled in conversation on 2026-10-08 and are recorded here as the contract for the implementation plan.

## Settled decisions

The site is both locally previewable and published; publishing targets GitHub Pages at a public URL, replacing an earlier Cloudflare Workers direction.

The publish trigger is a CI workflow file in this repository, the single non-Python, non-markdown file the design permits.

The site renders all of `docs/` except `docs/notes/`, per the working-notes convention; the sandbox findings stay forge-only.

The Starlight harness lives in its own external repository rather than as a `packages/` directory inside this repository.

## Architecture

The harness repository, `PrimePack-AB/starlight-docs-harness`, contains a Starlight application reduced to its static core: no Cloudflare adapter, no semantic-release, no repository-coupled freshness check, no vendored fonts, and no social links.

The application is generalized by four inputs: `DOCS_DIR` for the content path, `SITE_TITLE`, `SITE_BASE` for the Pages base path, and `REPO_URL` for link rewriting.

The harness provides its own root `index.md` landing page, since Starlight requires one and a consuming repository must not need to add one.

The harness is packaged as a composite GitHub Action whose `action.yml` sets up bun, builds with the inputs in the environment, and uploads the Pages artifact.

This repository adds exactly one file, `.github/workflows/docs-pages.yml`: checkout, invoke the harness action with `docs-dir: docs` and `exclude: notes`, then `actions/deploy-pages`.

The Pages source is set once in repository settings to GitHub Actions, and the site serves at `https://primepack-ab.github.io/karrio-dhl-freight-sweden/`.

## Content handling

The harness mounts content in place: no file in `docs/` moves, is renamed, or converts format.

This is load-bearing, because `tests/dhl_freight_sweden/test_doc_links.py` reads the tree via `rglob("*.md")` and enforces that every relative link in the README, the non-notes docs, and the sandbox findings resolves to a real file, and that all 92 sandbox fixtures stay linked from a checked document.

Starlight 0.38 has no loader `base` option and no plugin-level collections, verified against the installed package source; the harness therefore symlinks each rendered subdirectory of `DOCS_DIR` into its own `src/content/docs/`, with `notes/` excluded simply by not being linked, and the symlinks are created by a script at build time rather than committed.

All 14 docs files carry single-field `title:` frontmatter, which the harness consumes as-is under a permissive schema that requires only `title`.

Links divide into three classes: relative markdown links between pages are rewritten to site routes by the harness's rehype plugin, since Astro performs no native relative-link rewriting; heading anchors survive because GitHub and Starlight both slugify with `github-slugger`; and repo-relative non-content links, chiefly the fixture citations in `development/traceability/sandbox-suite.md`, are rewritten by the same plugin to GitHub blob URLs so they do not 404 on the site.

`starlight-links-validator` stays off by default, because fixture links never map to site routes by design.

## Publishing and local preview

A push to `main` triggers the workflow, which builds and deploys to Pages; a failed build leaves the last good deployment serving, and failures surface in the Actions log.

Local preview runs from a clone of the harness with `DOCS_DIR` pointing at this repository's `docs/`, giving a hot-reloading dev server; the command is documented in this repository's CLAUDE.md commands section as a documentation edit, not code.

## Verification

The harness repository carries its own tests against a sample-content fixture tree, with a vitest setup for component tests; Playwright end-to-end tests are an optional addition.

This repository verifies narrowly: `test_doc_links.py` passes untouched because nothing moved, and the first pushed workflow either serves the site at the Pages URL or fails visibly under `gh run watch`.

## Verification outcome

Starlight 0.38 was verified against its installed package source: no loader `base` option, no collections configuration, no native relative-link rewriting, and static Pages-compatible builds with `site` plus `base`.

Starlight's `lastUpdated` and `editLink` are omitted, since git history and edit paths resolve against the harness repository rather than the content repository.

## Out of scope

A stale `biome.json` copy at the repository root was removed during design; the harness repository carries its own configuration.
