#!/usr/bin/env python
"""Fetch canonical node details from canonical sources (run by `just nodes`).

For every unique node id across kb/biologics/*.yaml:
  - diseases (MONDO) and genes (HGNC): SRI Node Normalizer — canonical label, biolink category,
    and equivalent identifiers (e.g. HGNC -> NCBIGene/ENSEMBL), kept as xrefs for downstream merge.
  - drugs (NCIT): NodeNorm does not cover NCIt drugs, so fall back to the OAK NCIt adapter label.

Writes data/node_details.json: {curie: {name, category, xref}}. The koza transform reads this so
node attributes come from canonical sources rather than the hand-curated matched_label.
"""
from __future__ import annotations

import glob
import json
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

NODENORM = "https://nodenormalization-sri.renci.org/get_normalized_nodes"
ROLE_CATEGORY = {"drug": "biolink:Drug", "disease": "biolink:Disease", "gene": "biolink:Gene"}
_ncit = None


def collect_ids() -> dict[str, str]:
    ids: dict[str, str] = {}
    for path in sorted(glob.glob("kb/biologics/*.yaml")):
        rec = yaml.safe_load(open(path))
        ids[rec["biologic"]["id"]] = "drug"
        for ind in rec.get("indications") or []:
            ids[ind["object"]["id"]] = "disease"
        for tgt in rec.get("targets") or []:
            ids[tgt["object"]["id"]] = "gene"
    return ids


def nodenorm(curies: list[str]) -> dict[str, dict]:
    if not curies:
        return {}
    q = "&".join("curie=" + urllib.parse.quote(c, safe=":") for c in curies) + "&conflate=true"
    try:
        with urllib.request.urlopen(f"{NODENORM}?{q}", timeout=60) as r:
            data = json.load(r)
    except Exception:
        return {}
    out = {}
    for c, v in data.items():
        if not v:
            continue
        out[c] = {
            "name": (v.get("id") or {}).get("label"),
            "category": (v.get("type") or [None])[0],
            "xref": [e["identifier"] for e in v.get("equivalent_identifiers", []) if e["identifier"] != c][:10],
        }
    return out


def oak_ncit_label(curie: str):
    global _ncit
    if _ncit is None:
        from oaklib import get_adapter
        _ncit = get_adapter("sqlite:obo:ncit")
    return _ncit.label(curie)


def main() -> None:
    ids = collect_ids()
    nn = nodenorm(list(ids))
    details = {}
    for curie, role in ids.items():
        hit = nn.get(curie)
        if hit and hit.get("name"):
            details[curie] = {"name": hit["name"],
                              "category": hit.get("category") or ROLE_CATEGORY[role],
                              "xref": hit.get("xref", [])}
        elif role == "drug":
            details[curie] = {"name": oak_ncit_label(curie), "category": ROLE_CATEGORY[role], "xref": []}
        else:
            details[curie] = {"name": None, "category": ROLE_CATEGORY[role], "xref": []}

    Path("data").mkdir(exist_ok=True)
    with open("data/node_details.json", "w") as fh:
        json.dump(details, fh, indent=1, sort_keys=True)

    missing = [c for c, d in details.items() if not d["name"]]
    print(f"node_details: {len(details)} ids enriched, {len(missing)} without a canonical name")
    if missing:
        print("  missing:", ", ".join(missing))


if __name__ == "__main__":
    main()
