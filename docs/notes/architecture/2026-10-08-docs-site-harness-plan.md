---
title: "Docs site harness implementation plan"
created: 2026-10-08
---

# Docs Site Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Before each task, confirm your working directory matches the task's stated repository. Tasks 1-4 work in the harness repository, tasks 5-7 in the karrio repository.
> If you identify significant ambiguity, undefined terms, or missing context, return with questions rather than resolving through interpretation.

**Goal:** Publish this repository's `./docs` tree as a Starlight site on GitHub Pages, built by a reusable harness repository, with this repository gaining exactly one workflow file and one CLAUDE.md line.

**Architecture:** A new public repository `PrimePack-AB/starlight-docs-harness` (cloned to `~/projects/starlight-docs-harness`) holds a generic Starlight app that symlinks a consumer repository's rendered `docs/` subdirectories into its own `src/content/docs/` at build time, rewrites content links to site routes and repo-relative links to GitHub blob URLs via a rehype plugin, and exposes itself as a composite GitHub Action that uploads the Pages artifact. This repository adds `.github/workflows/docs-pages.yml` which invokes that action and deploys.

**Tech stack:** Astro 6.3.2, Starlight 0.38.3 (verified: no loader `base`, no `collections` option, no native relative-link rewriting; symlinked subdirectories under `src/content/docs/` keep the stock `docsLoader()`, sidebar autogeneration, and markdown processing intact), bun 1.3.4, vitest, Biome 2.4.11, GitHub Actions Pages deployment.

**Design contract:** `docs/notes/architecture/docs-site-harness-design.md` (commit `8bbfc45`).

**Safety constraints (from `tests/dhl_freight_sweden/test_doc_links.py`):** no file under `docs/` moves, renames, or changes format; the offline suite must still pass untouched at the end.

---

### Task 1: Scaffold the harness repository

**Files (all in `/home/joaqim/projects/starlight-docs-harness`, a fresh clone):**

- Create: `package.json`, `.gitignore`, `tsconfig.json`, `biome.json`, `astro.config.mjs`, `src/content.config.ts`, `src/content/docs/index.md`

- [ ] **Step 1: Create the repository and clone it**

```bash
cd /home/joaqim/projects
gh repo create PrimePack-AB/starlight-docs-harness --public \
  --description "Reusable Starlight harness that publishes any repository's docs/ to GitHub Pages" \
  --clone
cd starlight-docs-harness
git status --short --branch
```

Expected: empty tree on branch `main`, origin set to the new repository.

- [ ] **Step 2: Write `package.json`**

```json
{
  "name": "@primepack/starlight-docs-harness",
  "private": true,
  "type": "module",
  "packageManager": "bun@1.3.4",
  "scripts": {
    "dev": "bash scripts/link-content.sh && astro dev",
    "build": "bash scripts/link-content.sh && astro build",
    "preview": "astro preview",
    "check": "biome check .",
    "format": "biome check --write .",
    "test": "vitest run"
  },
  "devDependencies": {
    "@astrojs/starlight": "^0.38.3",
    "@biomejs/biome": "^2.4.11",
    "astro": "^6.3.2",
    "vitest": "^4.1.6"
  }
}
```

(`scripts/link-content.sh` arrives in Task 2; until then `bun run build` is not used — the Task 1 verification calls `bunx astro build` directly.)

- [ ] **Step 3: Write `.gitignore`**

```
node_modules/
dist/
.astro/
src/content/docs/*
!src/content/docs/index.md
```

(The negation works because only the children of `src/content/docs` are ignored, not the directory itself. Symlinked content directories from Task 2 never get committed; the harness-owned `index.md` does.)

- [ ] **Step 4: Write `tsconfig.json`**

```json
{
  "extends": "astro/tsconfigs/strict",
  "include": [".astro/types.d.ts", "src/**/*"],
  "exclude": ["src/content/docs"]
}
```

- [ ] **Step 5: Write `biome.json`**

```json
{
  "$schema": "https://biomejs.dev/schemas/2.4.11/schema.json",
  "files": {
    "includes": ["src/**", "tests/**", "scripts/**", "*.config.mjs", "package.json"]
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 120
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true
    }
  }
}
```

- [ ] **Step 6: Write `astro.config.mjs` (minimal static core; generalized in Task 2)**

```js
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: process.env.SITE_URL ?? 'https://primepack-ab.github.io',
  base: process.env.SITE_BASE ?? '/',
  integrations: [
    starlight({
      title: process.env.SITE_TITLE ?? 'Docs',
      sidebar: [],
    }),
  ],
});
```

- [ ] **Step 7: Write `src/content.config.ts` (stock Starlight collection)**

```ts
import { defineCollection } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

export const collections = {
  docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
};
```

- [ ] **Step 8: Write `src/content/docs/index.md` (the harness-owned landing page)**

```markdown
---
title: "Welcome"
---

This site renders the `docs/` tree of its source repository.

Use the sidebar to browse the documentation sections.
```

- [ ] **Step 9: Install, format, build**

```bash
bun install
bun run format
bun run check
bunx astro build
```

Expected: `bun install` creates `bun.lock`; `check` passes; build succeeds with `dist/index.html` present (verify with `test -f dist/index.html`).

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: scaffold the static starlight harness"
```

---

### Task 2: Link external content and generalize the config

**Files (harness repository):**

- Create: `scripts/link-content.sh`
- Modify: `astro.config.mjs` (replaced wholesale)

- [ ] **Step 1: Write `scripts/link-content.sh`**

```bash
#!/usr/bin/env bash
# Symlink each rendered subdirectory of DOCS_DIR into src/content/docs.
# Subdirectories named in EXCLUDE_DIRS (comma-separated) are skipped, which is
# how notes/ stays off the site.
set -euo pipefail
shopt -s nullglob

root="$(cd "$(dirname "$0")/.." && pwd)"
docs_dir="$(cd "${DOCS_DIR:-$root/../karrio-dhl-freight-sweden/docs}" && pwd)"
exclude="${EXCLUDE_DIRS:-notes}"
target="$root/src/content/docs"
mkdir -p "$target"

mounted=""
for entry in "$docs_dir"/*/; do
  name="$(basename "$entry")"
  case ",$exclude," in
    *",$name,"*) continue ;;
  esac
  mounted="$mounted,$name"
  ln -sfn "$docs_dir/$name" "$target/$name"
  printf 'linked %s -> %s\n' "$name" "$docs_dir/$name"
done

# Remove stale symlinks whose source directory is no longer mounted.
for link in "$target"/*; do
  [ -L "$link" ] || continue
  name="$(basename "$link")"
  case "$mounted" in
    *",$name"*) ;;
    *) rm -f "$link" && printf 'unlinked %s\n' "$name" ;;
  esac
done
```

```bash
chmod +x scripts/link-content.sh
```

- [ ] **Step 2: Replace `astro.config.mjs` with the generalized version**

```js
import fs from 'node:fs';
import path from 'node:path';
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

const root = process.cwd();
const docsDir = path.resolve(root, process.env.DOCS_DIR ?? '../karrio-dhl-freight-sweden/docs');
const excludeDirs = (process.env.EXCLUDE_DIRS ?? 'notes')
  .split(',')
  .map((dir) => dir.trim())
  .filter(Boolean);

const mountedDirs = fs.existsSync(docsDir)
  ? fs
      .readdirSync(docsDir, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && !excludeDirs.includes(entry.name))
      .map((entry) => entry.name)
      .sort()
  : [];

const sidebar = mountedDirs.map((dir) => ({
  label: dir.charAt(0).toUpperCase() + dir.slice(1),
  autogenerate: { directory: dir },
}));

export default defineConfig({
  site: process.env.SITE_URL ?? 'https://primepack-ab.github.io',
  base: process.env.SITE_BASE ?? '/',
  integrations: [
    starlight({
      title: process.env.SITE_TITLE ?? 'Docs',
      sidebar,
    }),
  ],
});
```

- [ ] **Step 3: Verify linking against the real docs tree**

```bash
DOCS_DIR=/home/joaqim/projects/karrio-dhl-freight-sweden/docs bash scripts/link-content.sh
```

Expected output exactly:

```
linked concepts -> /home/joaqim/projects/karrio-dhl-freight-sweden/docs/concepts
linked development -> /home/joaqim/projects/karrio-dhl-freight-sweden/docs/development
linked guides -> /home/joaqim/projects/karrio-dhl-freight-sweden/docs/guides
```

- [ ] **Step 4: Verify a full build**

```bash
DOCS_DIR=/home/joaqim/projects/karrio-dhl-freight-sweden/docs \
SITE_TITLE=karrio-dhl-freight-sweden \
SITE_BASE=/karrio-dhl-freight-sweden \
bunx astro build
test -f dist/concepts/products/index.html
test -f dist/development/index.html
test ! -e dist/notes
```

Expected: build succeeds; `development/index.md` renders as the section root at `dist/development/index/`; `dist/notes` does not exist. (Internal links are still wrong — Task 3 fixes them.)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: link external docs directories into the content root"
```

---

### Task 3: Rehype link-rewriting plugin (TDD)

**Files (harness repository):**

- Create: `vitest.config.ts`, `tests/rehype-repo-links.test.mjs`, `src/plugins/rehype-repo-links.mjs`
- Modify: `astro.config.mjs` (add the plugin wiring)

- [ ] **Step 1: Add vitest config**

`bun add -d vitest` (already declared in Task 1; idempotent if present), then write `vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.mjs'],
  },
});
```

- [ ] **Step 2: Write the failing tests `tests/rehype-repo-links.test.mjs`**

```js
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterAll, beforeAll, expect, it } from 'vitest';
import { rehypeRepoLinks } from '../src/plugins/rehype-repo-links.mjs';

const mounts = path.join(process.cwd(), 'src', 'content', 'docs');
let docsDir;

const anchor = (href) => ({
  type: 'element',
  tagName: 'a',
  properties: { href },
  children: [{ type: 'text', value: 'link' }],
});

beforeAll(() => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-test-'));
  docsDir = path.join(tmp, 'consumer', 'docs');
  fs.mkdirSync(path.join(docsDir, 'concepts'), { recursive: true });
  fs.mkdirSync(path.join(docsDir, 'guides'), { recursive: true });
  fs.mkdirSync(path.join(docsDir, 'notes', 'sandbox'), { recursive: true });
  fs.mkdirSync(path.join(tmp, 'consumer', 'tests', 'fixtures'), { recursive: true });
  fs.writeFileSync(path.join(docsDir, 'concepts', 'products.md'), '---\ntitle: "Products"\n---\n');
  fs.writeFileSync(path.join(docsDir, 'guides', 'lookups.md'), '---\ntitle: "Lookups"\n---\n');
  fs.writeFileSync(path.join(docsDir, 'notes', 'sandbox', 'findings.md'), '---\ntitle: "Findings"\n---\n');
  fs.writeFileSync(path.join(tmp, 'consumer', 'tests', 'fixtures', 'booking.json'), '{}\n');
  fs.symlinkSync(path.join(docsDir, 'concepts'), path.join(mounts, 'concepts'), 'dir');
  fs.symlinkSync(path.join(docsDir, 'guides'), path.join(mounts, 'guides'), 'dir');
});

afterAll(() => {
  fs.rmSync(path.join(mounts, 'concepts'), { force: true });
  fs.rmSync(path.join(mounts, 'guides'), { force: true });
});

const apply = (href, file = 'src/content/docs/guides/lookups.md') => {
  const plugin = rehypeRepoLinks({
    docsDir,
    excludeDirs: ['notes'],
    baseUrl: '/karrio-dhl-freight-sweden',
    repoUrl: 'https://github.com/PrimePack-AB/karrio-dhl-freight-sweden',
    repoRef: 'main',
  });
  const tree = { type: 'root', children: [anchor(href)] };
  plugin(tree, { history: [file] });
  return tree.children[0].properties.href;
};

it('rewrites relative markdown links inside mounted directories to site routes', () => {
  expect(apply('../concepts/products.md#the-eu-vat-area')).toBe(
    '/karrio-dhl-freight-sweden/concepts/products/#the-eu-vat-area',
  );
});

it('rewrites markdown links into excluded directories to blob URLs', () => {
  expect(apply('../notes/sandbox/findings.md')).toBe(
    'https://github.com/PrimePack-AB/karrio-dhl-freight-sweden/blob/main/docs/notes/sandbox/findings.md',
  );
});

it('rewrites repo-relative non-content links to blob URLs', () => {
  expect(apply('../../tests/fixtures/booking.json')).toBe(
    'https://github.com/PrimePack-AB/karrio-dhl-freight-sweden/blob/main/tests/fixtures/booking.json',
  );
});

it('leaves absolute, fragment-only, and mailto links untouched', () => {
  expect(apply('https://example.com/x.md')).toBe('https://example.com/x.md');
  expect(apply('#anchor')).toBe('#anchor');
  expect(apply('mailto:someone@example.org')).toBe('mailto:someone@example.org');
});
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
bun run test
```

Expected: FAIL — cannot resolve `../src/plugins/rehype-repo-links.mjs`.

- [ ] **Step 4: Implement `src/plugins/rehype-repo-links.mjs`**

```js
import fs from 'node:fs';
import path from 'node:path';

/**
 * Rewrite relative links in docs pages: targets inside mounted docs
 * subdirectories become site routes; every other relative target becomes an
 * absolute GitHub blob or tree URL against the source repository.
 */
export function rehypeRepoLinks({ docsDir, excludeDirs = ['notes'], baseUrl = '', repoUrl = '', repoRef = 'main' }) {
  const mountedDirs = new Set(
    fs
      .readdirSync(docsDir, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && !excludeDirs.includes(entry.name))
      .map((entry) => entry.name),
  );

  const splitFragment = (href) => {
    const index = href.indexOf('#');
    return index === -1 ? [href, ''] : [href.slice(0, index), href.slice(index)];
  };

  const toRoute = (href, realFile) => {
    const [target, fragment] = splitFragment(href);
    if (!/\.(md|mdx)$/.test(target)) return null;
    const resolved = path.resolve(path.dirname(realFile), target);
    const rel = path.relative(docsDir, resolved);
    if (rel.startsWith('..') || path.isAbsolute(rel)) return null;
    if (!mountedDirs.has(rel.split(path.sep)[0])) return null;
    const route = rel.replace(/\.(md|mdx)$/, '').replace(/\/?index$/, '');
    return `${baseUrl}/${route}/${fragment}`;
  };

  const toRepoUrl = (href, realFile) => {
    if (!repoUrl) return null;
    const [target, fragment] = splitFragment(href);
    const resolved = path.resolve(path.dirname(realFile), target);
    const rel = path.relative(path.dirname(docsDir), resolved);
    if (rel.startsWith('..') || path.isAbsolute(rel)) return null;
    const stat = fs.statSync(resolved, { throwIfNoEntry: false });
    const kind = stat?.isDirectory() ? 'tree' : 'blob';
    const kept = target.endsWith('.md') ? fragment : '';
    return `${repoUrl}/${kind}/${repoRef}/${rel}${kept}`;
  };

  const walk = (node, visit) => {
    if (node.type === 'element') visit(node);
    for (const child of node.children ?? []) walk(child, visit);
  };

  return (tree, file) => {
    const logical = file.history?.[0] ?? file.path;
    if (!logical) return;
    const absolute = path.resolve(process.cwd(), logical);
    if (!fs.existsSync(absolute)) return;
    const realFile = fs.realpathSync(absolute);
    const inDocs = path.relative(docsDir, realFile);
    if (inDocs.startsWith('..') || path.isAbsolute(inDocs)) return;

    walk(tree, (node) => {
      if (node.tagName !== 'a') return;
      const href = node.properties?.href;
      if (typeof href !== 'string') return;
      if (/^([a-z]+:)?\/\//i.test(href) || href.startsWith('#') || href.startsWith('mailto:')) return;
      const rewritten = toRoute(href, realFile) ?? toRepoUrl(href, realFile);
      if (rewritten) node.properties.href = rewritten;
    });
  };
}
```

(The `fs.realpathSync` call is what makes repo-relative links resolve correctly: the vfile path is the symlink path under `src/content/docs/`, whose depth differs from the real file's depth inside the consumer repository's `docs/` tree.)

- [ ] **Step 5: Run tests to verify they pass**

```bash
bun run test
```

Expected: 4 passed.

- [ ] **Step 6: Wire the plugin into `astro.config.mjs`**

Add the import at the top:

```js
import { rehypeRepoLinks } from './src/plugins/rehype-repo-links.mjs';
```

Add between `base` and `integrations`:

```js
  markdown: {
    rehypePlugins: [
      [
        rehypeRepoLinks,
        {
          docsDir,
          excludeDirs,
          baseUrl: process.env.SITE_BASE?.replace(/\/$/, '') ?? '',
          repoUrl: process.env.REPO_URL ?? '',
          repoRef: process.env.REPO_REF ?? 'main',
        },
      ],
    ],
  },
```

- [ ] **Step 7: Rebuild against the real docs and inspect the rewritten links**

```bash
bun run format && bun run check
DOCS_DIR=/home/joaqim/projects/karrio-dhl-freight-sweden/docs \
SITE_TITLE=karrio-dhl-freight-sweden \
SITE_BASE=/karrio-dhl-freight-sweden \
REPO_URL=https://github.com/PrimePack-AB/karrio-dhl-freight-sweden \
bunx astro build
rg -l 'blob/main/tests/dhl_freight_sweden/fixtures' dist | head
rg -o 'href="/karrio-dhl-freight-sweden/concepts/[a-z-]+/"' dist/guides/lookups/index.html | head -3
```

Expected: the first `rg` lists the `sandbox-suite` page (fixture citations now point at GitHub blob URLs); the second shows route-style hrefs. If the fixture `rg` finds nothing, the plugin is not running — check the `markdown` block placement.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: rewrite content and repository links in docs pages"
```

---

### Task 4: Action manifest, sample docs, harness CI, README

**Files (harness repository):**

- Create: `action.yml`, `.github/workflows/ci.yml`, `README.md`, `tests/sample-docs/docs/concepts/sample-concept.md`, `tests/sample-docs/docs/guides/sample-guide.md`, `tests/sample-docs/docs/notes/internal-note.md`

- [ ] **Step 1: Write the three sample docs**

`tests/sample-docs/docs/concepts/sample-concept.md`:

```markdown
---
title: "Sample concept"
---

A link to the [sample guide](../guides/sample-guide.md) and one to a [repo file](../../package.json).
```

`tests/sample-docs/docs/guides/sample-guide.md`:

```markdown
---
title: "Sample guide"
---

Guide body.
```

`tests/sample-docs/docs/notes/internal-note.md`:

```markdown
---
title: "Internal note"
---

Must not render.
```

- [ ] **Step 2: Write `action.yml`**

```yaml
name: starlight-docs-harness
description: Build a Starlight site from a repository's docs/ directory and upload a GitHub Pages artifact.
inputs:
  docs-dir:
    description: Docs directory relative to the repository root.
    default: docs
  exclude:
    description: Comma-separated docs subdirectories excluded from the site.
    default: notes
  title:
    description: Site title. Defaults to the repository name.
    default: ''
  base:
    description: Site base path. Defaults to /<repository-name> for project pages.
    default: ''
  repo-url:
    description: Repository web URL used to rewrite repo-relative links.
    default: ''
  repo-ref:
    description: Repository ref used to rewrite repo-relative links.
    default: main
runs:
  using: composite
  steps:
    - uses: oven-sh/setup-bun@v2
      with:
        bun-version: 1.3.4
    - name: Build site
      shell: bash
      working-directory: ${{ github.action_path }}
      env:
        DOCS_DIR: ${{ github.workspace }}/${{ inputs.docs-dir }}
        EXCLUDE_DIRS: ${{ inputs.exclude }}
        SITE_TITLE: ${{ inputs.title }}
        SITE_BASE: ${{ inputs.base }}
        REPO_URL: ${{ inputs.repo-url }}
        REPO_REF: ${{ inputs.repo-ref }}
      run: |
        export SITE_URL="${SITE_URL:-${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY_OWNER}.github.io}"
        export SITE_TITLE="${SITE_TITLE:-${GITHUB_REPOSITORY##*/}}"
        export SITE_BASE="${SITE_BASE:-/${GITHUB_REPOSITORY##*/}}"
        bun install --frozen-lockfile
        bun run build
    - uses: actions/upload-pages-artifact@v3
      with:
        path: ${{ github.action_path }}/dist
```

- [ ] **Step 3: Write `.github/workflows/ci.yml`**

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
        with:
          bun-version: 1.3.4
      - run: bun install --frozen-lockfile
      - run: bun run check
      - run: bun run test
      - name: Smoke build against sample docs
        env:
          DOCS_DIR: ${{ github.workspace }}/tests/sample-docs/docs
          EXCLUDE_DIRS: notes
          SITE_BASE: /starlight-docs-harness
          REPO_URL: ${{ github.server_url }}/${{ github.repository }}
        run: |
          bun run build
          test ! -e dist/notes
          test -f dist/index.html
          test -f dist/concepts/sample-concept/index.html
          rg -q 'href="/starlight-docs-harness/guides/sample-guide/"' dist/concepts/sample-concept/index.html
          rg -q 'blob/main/package.json' dist/concepts/sample-concept/index.html
```

- [ ] **Step 4: Write `README.md`**

```markdown
---
title: "README"
---

# starlight-docs-harness

A reusable Starlight application that publishes any repository's `docs/` tree to GitHub Pages, without the consuming repository carrying any JavaScript.

Rendered subdirectories of the consumer's `docs/` are symlinked into `src/content/docs/` at build time; subdirectories listed in `EXCLUDE_DIRS` (default `notes`) are not linked and do not render.

Relative markdown links between pages become site routes; links to files outside the rendered tree (fixtures, notes, code) become absolute GitHub blob or tree URLs.

## Local preview

```bash
git clone https://github.com/PrimePack-AB/starlight-docs-harness
cd starlight-docs-harness
bun install
DOCS_DIR=/absolute/path/to/consumer/docs SITE_TITLE=consumer SITE_BASE=/consumer \
REPO_URL=https://github.com/owner/consumer bun run dev
```

## Usage as an action

```yaml
- uses: PrimePack-AB/starlight-docs-harness@v1
  with:
    repo-url: https://github.com/owner/consumer
```

Inputs: `docs-dir` (default `docs`), `exclude` (default `notes`), `title`, `base`, `repo-url`, `repo-ref` (default `main`). The action uploads the `github-pages` artifact; the consumer workflow runs `actions/deploy-pages` after it.
```

- [ ] **Step 5: Run the CI smoke block locally**

```bash
bun run format && bun run check && bun run test
DOCS_DIR=$PWD/tests/sample-docs/docs \
EXCLUDE_DIRS=notes \
SITE_BASE=/starlight-docs-harness \
REPO_URL=https://github.com/PrimePack-AB/starlight-docs-harness \
bunx astro build
test ! -e dist/notes
test -f dist/concepts/sample-concept/index.html
rg -q 'href="/starlight-docs-harness/guides/sample-guide/"' dist/concepts/sample-concept/index.html
rg -q 'blob/main/package.json' dist/concepts/sample-concept/index.html
```

Expected: every assertion passes. (The local run links `tests/sample-docs/docs` into `src/content/docs`, replacing the karrio links from Task 2; rerunning Task 2's link command restores them.)

- [ ] **Step 6: Commit, push, tag**

```bash
git add -A
git commit -m "feat: add the pages action manifest, sample docs, and CI"
git push -u origin main
git tag v1
git push origin v1
```

---

### Task 5: Pages workflow in the karrio repository

**Repository:** `/home/joaqim/projects/karrio-dhl-freight-sweden`, branch `docs-site-design` (exists, holds the design note).

**Files:**

- Create: `.github/workflows/docs-pages.yml`

- [ ] **Step 1: Write `.github/workflows/docs-pages.yml`**

```yaml
name: docs-pages

on:
  push:
    branches: [main]
    paths:
      - docs/**
      - .github/workflows/docs-pages.yml
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: PrimePack-AB/starlight-docs-harness@v1
        with:
          repo-url: https://github.com/PrimePack-AB/karrio-dhl-freight-sweden
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/docs-pages.yml
git commit -m "ci: publish the docs tree to github pages via the starlight harness"
```

---

### Task 6: Local preview command in CLAUDE.md

**Repository:** karrio, branch `docs-site-design`.

**Files:**

- Modify: `CLAUDE.md` (Commands section)

- [ ] **Step 1: Add to the Commands list**

```markdown
- Docs site preview: `DOCS_DIR=$PWD/docs REPO_URL=https://github.com/PrimePack-AB/karrio-dhl-freight-sweden bun --cwd ../starlight-docs-harness run dev` — renders ./docs minus docs/notes/; publishing is automatic on push to main via docs-pages
```

- [ ] **Step 2: Verify the command works from this repository**

```bash
DOCS_DIR=$PWD/docs SITE_BASE=/karrio-dhl-freight-sweden \
REPO_URL=https://github.com/PrimePack-AB/karrio-dhl-freight-sweden \
bun --cwd ../starlight-docs-harness run dev -- --host 127.0.0.1 --port 4322 &
sleep 8
curl -fsSL http://127.0.0.1:4322/karrio-dhl-freight-sweden/concepts/products/ | rg -q '<html'
kill %1
```

Expected: the curl succeeds (page HTML served). Dev-server live-reload through symlinks may not pick up every edit; a dev-server restart always reflects the tree.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add the docs site preview command"
```

---

### Task 7: Enable Pages, merge, and verify the published site

**Repository:** karrio. One-time repository settings change, then integration.

- [ ] **Step 1: Enable Pages with the workflow build source**

```bash
gh api repos/PrimePack-AB/karrio-dhl-freight-sweden/pages --jq .build_type \
  || gh api -X POST repos/PrimePack-AB/karrio-dhl-freight-sweden/pages -f build_type=workflow
gh api repos/PrimePack-AB/karrio-dhl-freight-sweden/pages --jq .build_type
```

Expected: final command prints `workflow`.

- [ ] **Step 2: Merge the branch and push**

```bash
git checkout main
git merge --ff-only docs-site-design
git push origin main
```

- [ ] **Step 3: Watch the deployment**

```bash
gh run watch --repo PrimePack-AB/karrio-dhl-freight-sweden $(gh run list --repo PrimePack-AB/karrio-dhl-freight-sweden --workflow docs-pages --limit 1 --json databaseId --jq '.[0].databaseId')
```

Expected: `docs-pages` completes successfully (both build and deploy jobs).

- [ ] **Step 4: Verify the live site**

```bash
curl -fsSL https://primepack-ab.github.io/karrio-dhl-freight-sweden/ | rg '<title>'
curl -fsSL https://primepack-ab.github.io/karrio-dhl-freight-sweden/development/traceability/sandbox-suite/ \
  | rg -o 'blob/main/tests/dhl_freight_sweden/fixtures/[^"#]+' | head -3
curl -o /dev/null -w '%{http_code}\n' https://primepack-ab.github.io/karrio-dhl-freight-sweden/notes/sandbox/sandbox-findings/
```

Expected: the title contains `karrio-dhl-freight-sweden`; the sandbox-suite page links fixtures as GitHub blob URLs; the notes URL returns `404` (excluded from the site by design).

- [ ] **Step 5: Confirm zero repository-side regressions**

```bash
.venv/bin/python -m unittest discover -s tests
```

Expected: the offline suite passes exactly as before (nothing under `docs/` moved, renamed, or changed format).

- [ ] **Step 6: Clean up the branch**

```bash
git branch -d docs-site-design
```
