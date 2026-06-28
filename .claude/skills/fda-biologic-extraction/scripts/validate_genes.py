#!/usr/bin/env python
"""Validate HGNC gene ids in curated records against the Monarch API.

linkml-term-validator cannot validate HGNC (its OAK build uses lowercase 'hgnc:' while we
store Biolink-correct uppercase 'HGNC:'), so target genes are checked here against
api-v3.monarchinitiative.org. Each HGNC id must exist, be a biolink:Gene, and — when
matched_label is set — match the gene symbol Monarch returns.

  validate_genes.py kb/biologics/pembrolizumab.yaml [more.yaml ...]

Exit 0 if all gene ids valid, 1 otherwise.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

import yaml

API = "https://api-v3.monarchinitiative.org/v3/api/entity/"


def fetch(curie: str):
    url = API + urllib.parse.quote(curie, safe=":")
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def gene_ids(record: dict):
    for t in (record.get("targets") or []):
        obj = t.get("object") or {}
        cid = obj.get("id")
        if cid and str(cid).startswith("HGNC:"):
            yield cid, obj.get("matched_label")


def main(paths: list[str]) -> int:
    checks = issues = 0
    for path in paths:
        with open(path) as fh:
            record = yaml.safe_load(fh)
        for cid, matched in gene_ids(record):
            checks += 1
            ent = fetch(cid)
            if ent is None:
                print(f"  ❌ {path}: {cid} not found in Monarch (404)")
                issues += 1
            elif ent.get("category") != "biolink:Gene":
                print(f"  ❌ {path}: {cid} is {ent.get('category')}, not biolink:Gene")
                issues += 1
            else:
                label = ent.get("name") or ent.get("symbol")
                if matched and label and matched != label:
                    print(f"  ⚠️  {path}: {cid} Monarch label '{label}' != matched_label '{matched}'")
                    issues += 1
                else:
                    print(f"  ✅ {cid} -> {label}")
    print(f"\nGene checks: {checks}, issues: {issues}")
    return 1 if issues else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit("usage: validate_genes.py FILE [FILE ...]")
    raise SystemExit(main(args))
