#!/usr/bin/env python
"""Fetch node details (name, category, xref) for the curated corpus (run by `just nodes`).

Node names and Biolink categories come from the AUTHORITATIVE source for each id:
  - diseases -> MONDO            (OAK sqlite:obo:mondo)
  - drugs    -> NCI Thesaurus    (OAK sqlite:obo:ncit)
  - genes    -> HGNC, via the Monarch API (returns the HGNC symbol + biolink:Gene)

Equivalent identifiers (cross-references, e.g. HGNC -> NCBIGene / ENSEMBL / UniProt) come from the
SRI Node Normalizer, which is an equivalence / normalization service (Babel cliques) — useful for
xrefs, but NOT the authority for MONDO labels or HGNC symbols, so it is not used for name/category.

Writes data/node_details.json: {curie: {name, category, xref}}, consumed by the koza transform.
"""
from __future__ import annotations

import glob
import json
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

NODENORM = "https://nodenormalization-sri.renci.org/get_normalized_nodes"
MONARCH = "https://api-v3.monarchinitiative.org/v3/api/entity/"
OAK_ADAPTER = {"disease": "sqlite:obo:mondo", "drug": "sqlite:obo:ncit"}
CATEGORY = {"disease": "biolink:Disease", "drug": "biolink:Drug", "gene": "biolink:Gene"}
_adapters: dict[str, object] = {}


def collect_ids() -> dict[str, str]:
    ids: dict[str, str] = {}
    for path in sorted(glob.glob("kb/biologics/*.yaml")):
        rec = yaml.safe_load(open(path))
        ids[rec["biologic"]["id"]] = "drug"
        for ind in rec.get("indications") or []:
            if ind["object"].get("id"):
                ids[ind["object"]["id"]] = "disease"
        for tgt in rec.get("targets") or []:
            if tgt["object"].get("id"):
                ids[tgt["object"]["id"]] = "gene"
    return ids


def _oak_label(adapter_str: str, curie: str):
    if adapter_str not in _adapters:
        from oaklib import get_adapter
        _adapters[adapter_str] = get_adapter(adapter_str)
    return _adapters[adapter_str].label(curie)


def _monarch_name(curie: str):
    req = urllib.request.Request(MONARCH + urllib.parse.quote(curie, safe=":"),
                                 headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        return d.get("name") or d.get("symbol")
    except Exception:
        return None


def _xrefs(curies: list[str]) -> dict[str, list[str]]:
    """Equivalent identifiers from NodeNorm (xref only — not used for name/category)."""
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
        if v:
            out[c] = [e["identifier"] for e in v.get("equivalent_identifiers", []) if e["identifier"] != c][:10]
    return out


def main() -> None:
    ids = collect_ids()
    xref = _xrefs(list(ids))
    details = {}
    for curie, role in ids.items():
        name = _monarch_name(curie) if role == "gene" else _oak_label(OAK_ADAPTER[role], curie)
        details[curie] = {"name": name, "category": CATEGORY[role], "xref": xref.get(curie, [])}

    Path("data").mkdir(exist_ok=True)
    with open("data/node_details.json", "w") as fh:
        json.dump(details, fh, indent=1, sort_keys=True)

    missing = [c for c, d in details.items() if not d["name"]]
    print(f"node_details: {len(details)} ids — names from MONDO/NCIT (OAK) + HGNC (Monarch), "
          f"xrefs from NodeNorm; {len(missing)} without a name")
    if missing:
        print("  missing names:", ", ".join(missing))


if __name__ == "__main__":
    main()
