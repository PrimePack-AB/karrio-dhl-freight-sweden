#!/usr/bin/env bash
# Usage: scripts/release.sh <version>
# Sets the [project] version in pyproject.toml, commits "chore(release): <version>",
# and creates the annotated tag v<version>; prints the push command without running it.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <version>   (CalVer YYYY.M.N, for example 2026.10.1)" >&2
  exit 2
fi

version=$1
tag="v$version"

if [[ ! "$version" =~ ^[0-9]{4}\.([1-9]|1[0-2])\.[1-9][0-9]*$ ]]; then
  echo "version $version is not CalVer YYYY.M.N (month and counter without leading zeros)" >&2
  exit 1
fi

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

branch=$(git symbolic-ref --quiet --short HEAD || true)
if [[ "$branch" != "main" ]]; then
  echo "releases are cut from main; current branch is ${branch:-detached HEAD}" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "working tree is not clean" >&2
  exit 1
fi

if git rev-parse --quiet --verify "refs/tags/$tag" >/dev/null; then
  echo "tag $tag already exists" >&2
  exit 1
fi

python3 - "$version" <<'PY'
import re
import sys
import tomllib
from pathlib import Path

version = sys.argv[1]
path = Path("pyproject.toml")
text = path.read_text()
project = re.search(r"(?ms)^\[project\]\n(.*?)(?=^\[|\Z)", text)
if project is None:
    sys.exit("pyproject.toml has no [project] table")
body, count = re.subn(
    r'(?m)^version = "[^"]*"$', f'version = "{version}"', project.group(1), count=1
)
if count != 1:
    sys.exit("pyproject.toml [project] table has no version line")
text = text[: project.start(1)] + body + text[project.end(1) :]
if tomllib.loads(text)["project"]["version"] != version:
    sys.exit("failed to set the [project] version")
path.write_text(text)
PY

scripts/check-release-tag.sh "$tag"

git add pyproject.toml
git commit -m "chore(release): $version"
git tag -a "$tag" -m "$version"

echo
echo "Created commit and tag $tag. Push both with:"
echo "  git push --atomic origin main $tag"
