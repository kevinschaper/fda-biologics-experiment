#!/usr/bin/env python
"""Verify FDA-label snippets are exact quotes from the real DailyMed SPL label.

The linkml-reference-validator only fetches PubMed/PMC, so FDA: references are skipped there.
This gives FDA snippets the same deterministic guarantee: fetch the SPL by setid (DailyMed API),
cache the extracted text under cache/fda_labels/<setid>.txt (committed, so CI verifies offline),
and check each FDA evidence snippet is an exact, whitespace-normalized substring of the label.

  validate_fda_snippets.py kb/biologics/infliximab.yaml [more.yaml ...]

Exit 0 if all FDA snippets verify (placeholder setids are skipped with a warning), else 1.
"""
from __future__ import annotations

import html
import re
import sys
import urllib.request
from pathlib import Path

import yaml

SPL_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.xml"
CACHE = Path("cache/fda_labels")


def _norm(s: str) -> str:
    return " ".join((s or "").split())


def _setid(reference: str, urls: list[str]) -> str | None:
    if reference and reference.startswith("FDA:"):
        return reference.split("FDA:", 1)[1]
    for u in urls or []:
        m = re.search(r"setid=([^&]+)", u)
        if m:
            return m.group(1)
    return None


def _label_text(setid: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{setid}.txt"
    if cached.exists():
        return cached.read_text()
    with urllib.request.urlopen(SPL_URL.format(setid=setid), timeout=60) as r:
        raw = r.read().decode("utf-8", "replace")
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    cached.write_text(text)
    return text


def _fda_snippets(rec: dict):
    urls = [u for s in (rec.get("provenance") or {}).get("sources") or []
            for u in (s.get("source_record_urls") or [])]
    for section in ("indications", "targets"):
        for claim in rec.get(section) or []:
            for ev in claim.get("evidence") or []:
                if str(ev.get("reference", "")).startswith("FDA:"):
                    yield _setid(ev.get("reference", ""), urls), ev.get("snippet", "")


def main(paths: list[str]) -> int:
    checks = issues = skipped = 0
    label_cache: dict[str, str] = {}
    for path in paths:
        with open(path) as fh:
            rec = yaml.safe_load(fh)
        for setid, snippet in _fda_snippets(rec):
            checks += 1
            if not setid or "placeholder" in setid.lower():
                print(f"  ⚠️  {path}: placeholder/missing SPL setid — skipped")
                skipped += 1
                continue
            if setid not in label_cache:
                try:
                    label_cache[setid] = _norm(_label_text(setid))
                except Exception as ex:
                    print(f"  ❌ {path}: could not fetch SPL {setid}: {ex}")
                    issues += 1
                    continue
            if _norm(snippet) in label_cache[setid]:
                print(f"  ✅ {setid[:8]}… : {snippet[:60]}")
            else:
                print(f"  ❌ {path}: snippet NOT found in SPL {setid}:\n      {snippet[:110]}")
                issues += 1
    print(f"\nFDA snippet checks: {checks} ({skipped} placeholder skipped), issues: {issues}")
    return 1 if issues else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit("usage: validate_fda_snippets.py FILE [FILE ...]")
    raise SystemExit(main(args))
