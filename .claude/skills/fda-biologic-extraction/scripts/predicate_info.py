#!/usr/bin/env python
"""Look up Biolink predicate definitions and hierarchy LIVE from the installed model.

Never hardcode predicate definitions in curation prose or records — call this so the
skill stays in sync with whatever Biolink version is pinned in the environment.

Usage:
  predicate_info.py biolink:treats
      -> curie, verbatim definition, is_a, mixins, children (each with its definition)

  predicate_info.py --family treats
      -> the full family (mixin-aware descendants) with definitions

  predicate_info.py --check biolink:ameliorates_condition --within treats_or_applied_or_studied_to_treat
      -> exit 0 if the predicate is a (mixin-aware) member of the family, else exit 1

Backend: Biolink Model Toolkit (bmt). bmt wraps linkml-runtime's SchemaView; if bmt is
unavailable the import error tells you to `uv add bmt`.
"""
from __future__ import annotations

import argparse
import json
import sys


def _toolkit():
    try:
        from bmt import Toolkit
    except ImportError:
        sys.exit("bmt not installed — run `uv add bmt` (Biolink Model Toolkit).")
    return Toolkit()


def _resolve(tk, token: str):
    """Resolve a name or CURIE (biolink:treats / treats / treats_or_..._treat) to an element."""
    base = token.replace("biolink:", "")
    for cand in (token, base, base.replace("_", " ")):
        el = tk.get_element(cand)
        if el is not None:
            return el
    return None


def _info(tk, el) -> dict:
    return {
        "name": el.name,
        "curie": getattr(el, "slot_uri", None),
        "definition": (el.description or "").strip(),
        "is_a": getattr(el, "is_a", None),
        "mixins": list(getattr(el, "mixins", []) or []),
        "children": tk.get_children(el.name),
    }


def cmd_describe(tk, token: str) -> int:
    el = _resolve(tk, token)
    if el is None:
        print(json.dumps({"error": f"unknown element: {token}"}))
        return 1
    info = _info(tk, el)
    info["children_detail"] = []
    for child in info["children"]:
        cel = tk.get_element(child)
        if cel is not None:
            info["children_detail"].append(
                {"name": cel.name, "curie": getattr(cel, "slot_uri", None),
                 "definition": (cel.description or "").strip()}
            )
    print(json.dumps(info, indent=2))
    return 0


def cmd_family(tk, root: str) -> int:
    rel = _resolve(tk, root)
    if rel is None:
        print(json.dumps({"error": f"unknown element: {root}"}))
        return 1
    members = []
    for name in tk.get_descendants(rel.name, reflexive=True):
        el = tk.get_element(name)
        if el is None:
            continue
        members.append({"name": el.name, "curie": getattr(el, "slot_uri", None),
                        "definition": (el.description or "").strip()})
    print(json.dumps({"root": rel.name, "members": members}, indent=2))
    return 0


def cmd_check(tk, predicate: str, within: str) -> int:
    pel = _resolve(tk, predicate)
    rel = _resolve(tk, within)
    if pel is None or rel is None:
        print(json.dumps({"error": "unknown predicate or family root",
                          "predicate": predicate, "within": within}))
        return 1
    family = set(tk.get_descendants(rel.name, reflexive=True))
    ok = pel.name in family
    print(json.dumps({"predicate": pel.name, "curie": getattr(pel, "slot_uri", None),
                      "within": rel.name, "member": ok}))
    return 0 if ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Live Biolink predicate definitions / hierarchy.")
    p.add_argument("predicate", nargs="?", help="predicate name or CURIE to describe")
    p.add_argument("--family", metavar="ROOT", help="list the mixin-aware family under ROOT")
    p.add_argument("--check", metavar="CURIE", help="check that CURIE is within --within")
    p.add_argument("--within", metavar="ROOT", help="family root for --check")
    args = p.parse_args(argv)

    tk = _toolkit()
    if args.check:
        if not args.within:
            p.error("--check requires --within")
        return cmd_check(tk, args.check, args.within)
    if args.family:
        return cmd_family(tk, args.family)
    if args.predicate:
        return cmd_describe(tk, args.predicate)
    p.error("give a predicate, or --family ROOT, or --check CURIE --within ROOT")


if __name__ == "__main__":
    raise SystemExit(main())
