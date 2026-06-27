#!/usr/bin/env python
"""Ground a surface name to an ontology CURIE. DETERMINISTIC.

The curating agent MUST call this instead of emitting an id from memory.

  ground.py --type disease "rheumatoid arthritis"     # -> MONDO via OAK
  ground.py --type drug    "adalimumab"               # -> NCIT via OAK
  ground.py --type gene    "TNF"                       # -> HGNC via genenames.org

Output: JSON list of candidates, best first:
  [{"curie","label","score","match_type","source"}]
An empty list means no confident match -> the caller sets needs_review: true.

Resolution order: curated overrides (overrides.yaml) -> ontology search.
First OAK run downloads the ontology SQLite to ~/.data/oaklib (NCIT is ~500MB).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

OAK_ADAPTER = {"disease": "sqlite:obo:mondo", "drug": "sqlite:obo:ncit"}
PREFIX = {"disease": "MONDO", "drug": "NCIT", "gene": "HGNC"}
OVERRIDES_FILE = Path(__file__).with_name("overrides.yaml")

_adapters: dict[str, object] = {}


def _norm(s: str) -> str:
    return " ".join(s.strip().lower().split())


def _load_overrides() -> dict:
    if not OVERRIDES_FILE.exists():
        return {}
    import yaml
    return yaml.safe_load(OVERRIDES_FILE.read_text()) or {}


def _override(kind: str, name: str) -> list[dict]:
    table = (_load_overrides().get(kind) or {})
    norm = {_norm(k): v for k, v in table.items()}
    hit = norm.get(_norm(name))
    if not hit:
        return []
    return [{"curie": hit["curie"], "label": hit.get("label"),
             "score": 1.0, "match_type": "override", "source": "overrides.yaml"}]


def _adapter(adapter_str: str):
    if adapter_str not in _adapters:
        from oaklib import get_adapter
        _adapters[adapter_str] = get_adapter(adapter_str)
    return _adapters[adapter_str]


def _search_config():
    """Case-insensitive match over labels AND aliases (brand/generic synonyms)."""
    from oaklib.datamodels.search import SearchConfiguration, SearchProperty
    return SearchConfiguration(
        force_case_insensitive=True,
        properties=[SearchProperty.LABEL, SearchProperty.ALIAS],
    )


def _oak_candidates(kind: str, name: str, limit: int) -> list[dict]:
    prefix = PREFIX[kind]
    adapter = _adapter(OAK_ADAPTER[kind])
    norm = _norm(name)
    out, seen = [], set()
    for curie in adapter.basic_search(name, config=_search_config()):
        if not str(curie).startswith(prefix + ":") or curie in seen:
            continue
        seen.add(curie)
        label = adapter.label(curie)
        if label and _norm(label) == norm:
            mt, score = "exact", 1.0
        else:
            aliases = {_norm(a) for a in (adapter.entity_aliases(curie) or [])}
            mt, score = ("synonym", 0.9) if norm in aliases else ("partial", 0.5)
        out.append({"curie": curie, "label": label, "score": score,
                    "match_type": mt, "source": "oak:" + prefix.lower()})
    out.sort(key=lambda r: -r["score"])
    return out[:limit]


def _gn_get(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except Exception:
        return []
    return (data.get("response") or {}).get("docs") or []


def _gene_candidates(name: str, limit: int) -> list[dict]:
    base = "https://rest.genenames.org"
    q = urllib.parse.quote(name.strip())
    out, seen = [], set()
    for field, score, mt in (("symbol", 1.0, "exact_symbol"),
                             ("alias_symbol", 0.9, "alias"),
                             ("prev_symbol", 0.85, "prev_symbol")):
        for doc in _gn_get(f"{base}/fetch/{field}/{q}"):
            hid = doc.get("hgnc_id")
            if hid and hid not in seen:
                seen.add(hid)
                out.append({"curie": hid, "label": doc.get("symbol"), "score": score,
                            "match_type": mt, "source": "genenames"})
        if out:
            return out[:limit]
    for doc in _gn_get(f"{base}/search/{q}"):
        hid = doc.get("hgnc_id")
        if hid and hid not in seen:
            seen.add(hid)
            out.append({"curie": hid, "label": doc.get("symbol"),
                        "score": round(float(doc.get("score", 0)), 3),
                        "match_type": "search", "source": "genenames"})
    return out[:limit]


def ground(kind: str, name: str, limit: int) -> list[dict]:
    hits = _override(kind, name)
    if hits:
        return hits
    if kind == "gene":
        return _gene_candidates(name, limit)
    return _oak_candidates(kind, name, limit)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Ground a name to an ontology CURIE.")
    p.add_argument("--type", required=True, choices=["disease", "drug", "gene"])
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=5)
    args = p.parse_args(argv)
    print(json.dumps(ground(args.type, args.name, args.limit), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
