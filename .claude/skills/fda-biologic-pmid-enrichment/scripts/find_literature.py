#!/usr/bin/env python
"""Discover candidate supporting publications (EuropePMC) for a drug + disease/target.

DISCOVERY ONLY — returns relevant PMIDs with title + a plain-text abstract preview so you can
judge which paper genuinely supports the edge. Do NOT copy the quote from this preview: its markup
differs from what the validator fetches. Copy the verbatim quote from
  linkml-reference-validator lookup PMID:<id> --format json
and confirm with
  linkml-reference-validator validate text "<quote>" PMID:<id>

  find_literature.py "adalimumab" "rheumatoid arthritis"
  find_literature.py "pembrolizumab" "melanoma" --extra "phase 3"
  find_literature.py "adalimumab" "TNF" --extra "binds OR neutralizes OR mechanism"
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request

SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _strip(t: str | None) -> str:
    return re.sub(r"<[^>]+>", " ", t or "").strip()


def search(drug: str, topic: str, extra: str, n: int) -> list[dict]:
    terms = [f'"{drug}"', f'"{topic}"']
    if extra:
        terms.append(f"({extra})")
    query = " AND ".join(terms) + " AND HAS_ABSTRACT:Y"
    url = SEARCH + "?" + urllib.parse.urlencode(
        {"query": query, "format": "json", "resultType": "core", "pageSize": n})
    data = json.load(urllib.request.urlopen(url, timeout=30))
    out = []
    for r in data.get("resultList", {}).get("result", []):
        pmid = r.get("pmid")
        if not pmid:
            continue
        out.append({
            "pmid": f"PMID:{pmid}",
            "title": _strip(r.get("title")),
            "year": r.get("pubYear"),
            "type": r.get("pubType"),
            "abstract_preview": _strip(r.get("abstractText"))[:400],
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Find candidate supporting PMIDs via EuropePMC.")
    ap.add_argument("drug")
    ap.add_argument("topic", help="disease (for indications) or target gene/protein (for targets)")
    ap.add_argument("--extra", default="randomized OR trial OR efficacy",
                    help="extra query clause to bias toward pivotal/mechanistic papers")
    ap.add_argument("-n", "--num", type=int, default=5)
    a = ap.parse_args()
    print(json.dumps(search(a.drug, a.topic, a.extra, a.num), indent=1))


if __name__ == "__main__":
    main()
