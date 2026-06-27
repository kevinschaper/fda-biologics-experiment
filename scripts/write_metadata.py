"""Write output/release-metadata.yaml — the build receipt (kozahub style, run by `just metadata`).

Records the build version, source/ontology versions used for grounding + node enrichment, and a
checksum/record count for each KGX artifact. FDA labels are versioned per-record (see versions.py).
"""
from __future__ import annotations

import datetime
import glob
import hashlib
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "fda_biologics"))

from versions import get_source_versions, now_iso  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    out = ROOT / "output"
    out.mkdir(exist_ok=True)

    artifacts = [
        {"name": p.name, "sha256": _sha256(p), "records": sum(1 for _ in open(p))}
        for p in sorted(out.glob("*.jsonl"))
    ]
    record_count = len(glob.glob(str(ROOT / "kb" / "biologics" / "*.yaml")))

    metadata = {
        "ingest_name": "fda-biologics-ingest",
        "build_version": datetime.date.today().isoformat(),
        "built_at": now_iso(),
        "record_count": record_count,
        "sources": get_source_versions(),
        "artifacts": artifacts,
        "notes": ("FDA labels are versioned per record (SPL setid + optional source_version/retrieved "
                  "in each kb/biologics/*.yaml provenance.sources)."),
    }

    path = out / "release-metadata.yaml"
    with open(path, "w") as fh:
        yaml.safe_dump(metadata, fh, sort_keys=False, allow_unicode=True)

    print(f"Wrote {path}")
    print(f"  build_version: {metadata['build_version']}  records: {record_count}  artifacts: {len(artifacts)}")
    for s in metadata["sources"]:
        print(f"  {s['id']}: {s['version']} ({s['version_method']})")


if __name__ == "__main__":
    main()
