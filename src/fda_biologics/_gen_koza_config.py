"""Expand the kb/biologics/*.yaml glob into a runnable koza config at the repo root.

koza only expands globs in config-free mode (which drops our custom edge columns), so we
generate `.koza.generated.yaml` (paths relative to repo root) that keeps the writer config
from src/fda_biologics/transform.yaml. Run from the repo root (see `just transform`).
"""
import glob

import yaml

cfg = yaml.safe_load(open("src/fda_biologics/transform.yaml"))
cfg["reader"]["files"] = sorted(glob.glob("kb/biologics/*.yaml"))
cfg["transform"]["code"] = "src/fda_biologics/transform.py"

with open(".koza.generated.yaml", "w") as fh:
    yaml.safe_dump(cfg, fh, sort_keys=False)

print(f"{len(cfg['reader']['files'])} curated files -> .koza.generated.yaml")
