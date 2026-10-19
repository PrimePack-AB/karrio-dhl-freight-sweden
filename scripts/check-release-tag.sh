#!/usr/bin/env bash
# Usage: scripts/check-release-tag.sh <tag>
# Exits non-zero unless <tag> is "v" followed by the [project] version in pyproject.toml.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <tag>" >&2
  exit 2
fi

tag=$1
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
version=$(python3 -c 'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["project"]["version"])' "$repo_root/pyproject.toml")

if [[ "$tag" != "v$version" ]]; then
  echo "tag $tag does not match pyproject.toml version $version (expected v$version)" >&2
  exit 1
fi
echo "tag $tag matches pyproject.toml version $version"
