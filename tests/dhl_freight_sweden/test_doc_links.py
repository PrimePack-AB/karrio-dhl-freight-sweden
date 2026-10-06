"""Relative links in the documentation, and the evidence they cite.

The checked documents are the README, every page under ``docs/`` outside the
ephemeral ``docs/notes/`` tree, and the sandbox findings note, which together
carry every sandbox claim. Working notes such as plans are not checked.
"""

import pathlib
import re
import typing
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
EVIDENCE_DIR = REPO / "tests" / "dhl_freight_sweden" / "fixtures" / "sandbox"

INLINE_LINK = re.compile(r"\]\(([^)\s]+)\)")
REFERENCE_DEFINITION = re.compile(r"^\[[^\]]+\]:\s*(\S+)", re.M)
FENCE = re.compile(r"^```.*?^```", re.M | re.S)
EXTERNAL = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def checked_documents() -> typing.List[pathlib.Path]:
    docs = REPO / "docs"
    return [
        REPO / "README.md",
        docs / "notes" / "README.md",
        docs / "notes" / "sandbox" / "sandbox-findings.md",
        *sorted(
            path
            for path in docs.rglob("*.md")
            if (docs / "notes") not in path.parents
        ),
    ]


def relative_links(document: pathlib.Path) -> typing.List[str]:
    text = FENCE.sub("", document.read_text())
    targets = INLINE_LINK.findall(text) + REFERENCE_DEFINITION.findall(text)
    return [
        target
        for target in targets
        if not EXTERNAL.match(target) and not target.startswith("#")
    ]


def resolve(document: pathlib.Path, target: str) -> pathlib.Path:
    return (document.parent / target.split("#", 1)[0]).resolve()


class TestDocLinks(unittest.TestCase):
    def test_relative_links_resolve(self):
        for document in checked_documents():
            for target in relative_links(document):
                with self.subTest(document=str(document.relative_to(REPO)), target=target):
                    self.assertTrue(resolve(document, target).exists())

    def test_every_evidence_file_is_linked(self):
        linked = {
            resolve(document, target)
            for document in checked_documents()
            for target in relative_links(document)
        }

        for evidence in sorted(EVIDENCE_DIR.glob("*.json")):
            with self.subTest(evidence=evidence.name):
                self.assertIn(evidence.resolve(), linked)


if __name__ == "__main__":
    unittest.main()
