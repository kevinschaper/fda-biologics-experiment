#!/usr/bin/env python
"""Verify PMID-backed snippets are exact quotes from the cited publication.

The linkml-reference-validator data-mode plugin does not reliably traverse our multivalued
`evidence` lists (it only sees evidence[0]), so we drive its per-quote checker directly: for each
PMID EvidenceItem run `linkml-reference-validator validate text <snippet> <PMID>`, which fetches the
reference (cached under references_cache/) and verifies the snippet by substring.

  validate_pmid_snippets.py kb/biologics/adalimumab.yaml [more.yaml ...]

Exit 0 if all PMID snippets verify (no PMIDs = nothing to check), else 1.
"""
from __future__ import annotations

import subprocess
import sys

import yaml


def pmid_snippets(rec: dict):
    for section in ("indications", "targets"):
        for claim in rec.get(section) or []:
            for ev in claim.get("evidence") or []:
                ref = str(ev.get("reference", ""))
                if ref.startswith("PMID:"):
                    yield ref, ev.get("snippet", "")


def verify(snippet: str, reference: str) -> bool:
    r = subprocess.run(
        ["linkml-reference-validator", "validate", "text", snippet, reference],
        capture_output=True, text=True,
    )
    return "Valid: True" in r.stdout


def main(paths: list[str]) -> int:
    checks = issues = 0
    for path in paths:
        with open(path) as fh:
            rec = yaml.safe_load(fh)
        for ref, snippet in pmid_snippets(rec):
            checks += 1
            if verify(snippet, ref):
                print(f"  ✅ {ref} : {snippet[:60]}")
            else:
                print(f"  ❌ {path}: snippet NOT found in {ref}:\n      {snippet[:110]}")
                issues += 1
    print(f"\nPMID snippet checks: {checks}, issues: {issues}")
    return 1 if issues else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit("usage: validate_pmid_snippets.py FILE [FILE ...]")
    raise SystemExit(main(args))
