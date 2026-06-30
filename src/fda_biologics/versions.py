"""Upstream source versions for fda-biologics-ingest.

Provides get_source_versions() consumed by scripts/write_metadata.py (which composes + validates
the release receipt via the kozahub-metadata-schema package). FDA labels version per-record (SPL
setid + optional source_version/retrieved in each kb file), so there is no single dataset version;
we record the ontologies/services used for grounding and node enrichment as the reproducibility
anchors plus a per-record FDA summary.
"""
from __future__ import annotations

import glob
import json
import urllib.request
from typing import Any

import yaml
from kozahub_metadata_schema import now_iso, version_from_github_release


def _nodenorm_babel() -> str:
    try:
        with urllib.request.urlopen("https://nodenormalization-sri.renci.org/status", timeout=10) as r:
            return json.load(r).get("babel_version") or "unknown"
    except Exception:
        return "unknown"


def _fda_summary() -> tuple[int, int]:
    records = 0
    labels: set[str] = set()
    for path in glob.glob("kb/biologics/*.yaml"):
        rec = yaml.safe_load(open(path))
        records += 1
        for s in (rec.get("provenance") or {}).get("sources") or []:
            for url in s.get("source_record_urls") or []:
                labels.add(url)
    return records, len(labels)


def get_source_versions() -> list[dict[str, Any]]:
    mondo_ver, mondo_method = version_from_github_release("monarch-initiative/mondo")
    babel = _nodenorm_babel()
    n_records, n_labels = _fda_summary()
    return [
        {"id": "infores:fda",
         "name": "FDA structured product labels (DailyMed SPL) — indications and mechanism of action",
         "urls": ["https://dailymed.nlm.nih.gov/"],
         "version": f"per-record ({n_records} records, {n_labels} label sources)",
         "version_method": "per_record_spl_setid", "retrieved_at": now_iso()},
        {"id": "infores:ncit",
         "name": "NCI Thesaurus — drug grounding and node labels (OAK sqlite:obo:ncit)",
         "urls": ["https://obofoundry.org/ontology/ncit.html"],
         "version": "unknown", "version_method": "unavailable", "retrieved_at": now_iso()},
        {"id": "infores:mondo",
         "name": "MONDO disease ontology — disease grounding and node labels",
         "urls": ["https://github.com/monarch-initiative/mondo"],
         "version": mondo_ver, "version_method": mondo_method, "retrieved_at": now_iso()},
        {"id": "infores:hgnc",
         "name": "HGNC — gene grounding (genenames.org) plus gene node labels and validation (Monarch API)",
         "urls": ["https://www.genenames.org/", "https://api-v3.monarchinitiative.org/"],
         "version": "unknown", "version_method": "unavailable", "retrieved_at": now_iso()},
        {"id": "infores:sri-node-normalizer",
         "name": "SRI Node Normalizer — equivalent-identifier cross-references (node xrefs only)",
         "urls": ["https://nodenormalization-sri.renci.org/status"],
         "version": babel,
         "version_method": "status_endpoint" if babel != "unknown" else "unavailable",
         "retrieved_at": now_iso()},
    ]
