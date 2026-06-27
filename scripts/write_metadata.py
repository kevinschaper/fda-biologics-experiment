"""Compose + validate output/release-metadata.yaml via the kozahub-metadata-schema package.

Uses the canonical kozahub writer (build_version/transform_version/biolink_version/tools) and then
verifies the emitted receipt against the package's own LinkML schema (class Release), so our
metadata conforms to the shared kozahub standard. Run by `just metadata`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from kozahub_metadata_schema import write_metadata
from kozahub_metadata_schema import writer as _writer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "fda_biologics"))

from versions import get_source_versions  # noqa: E402


def main() -> int:
    src = ROOT / "src" / "fda_biologics"
    transform_paths = list(src.rglob("*.py")) + list(src.rglob("*.yaml"))
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    artifacts = sorted(p.name for p in out.glob("*.jsonl"))

    metadata = write_metadata(
        ingest_name="fda-biologics-ingest",
        source_versions=get_source_versions(),
        transform_paths=transform_paths,
        artifacts=artifacts,
        output_dir=out,
    )
    receipt = out / "release-metadata.yaml"
    print(f"Wrote {receipt}")
    print(f"  build_version: {metadata['build_version']}")
    print(f"  sources: {len(metadata['sources'])}, artifacts: {len(artifacts)}")

    # Verify the receipt against the canonical kozahub metadata schema (class Release).
    schema = Path(_writer.__file__).parent / "schema" / "kozahub_metadata_schema.yaml"
    result = subprocess.run(
        ["linkml-validate", "-s", str(schema), "-C", "Release", str(receipt)],
        capture_output=True, text=True,
    )
    print((result.stdout + result.stderr).strip())
    if result.returncode != 0:
        print("❌ release-metadata.yaml does not conform to kozahub_metadata_schema")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
