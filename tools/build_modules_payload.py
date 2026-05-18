#!/usr/bin/env python3
"""Build a deployable payload of our modules + upstream patches.

Given the current fork tree at HEAD, produce a self-contained ``payload/``
directory that can later be applied onto a fresh upstream checkout via
``apply_modules.py``. Output layout::

    payload/
      MANIFEST.json
      modules/<dst-path>/...            # full copies of our module dirs
      patches/<dst-path>.patch          # unified diffs vs the baseline tag

The payload is the "deliverable" — apply_modules.py only consumes payload/
and never reads the fork. That separation lets us hand the same payload to
multiple upstream tags (apply on v1.5, then v1.6) without re-running build.

Usage:
    python tools/build_modules_payload.py --baseline 8f1a21c --out tools/payload

Excluded paths (we don't ship them — they're either local dev artefacts or
state that varies per-machine):
* deploy_backend.sh   (contains plaintext device password)
* WORK_LOG.md         (our project log, not part of the deliverable)
* .gitignore          (local additions)
* boneio/webui/schema/*.schema.json  (regenerated post-apply by
  schema_converter on the target machine)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Module dirs we ship in full (backend + frontend). Path is relative to repo root.
MODULE_DIRS = [
    "boneio/modules/expander",
    "boneio/modules/remote_mqtt",
    "frontend/src/components/UISettings/modules/expander",
    "frontend/src/components/UISettings/modules/remote_mqtt",
]

# Files we never ship — local-only or regenerated.
EXCLUDE_PATHS = {
    "deploy_backend.sh",
    "WORK_LOG.md",
    ".gitignore",
    ".DS_Store",
}
EXCLUDE_PREFIXES = (
    "boneio/webui/schema/",
    "tools/payload/",
    "tools/build_modules_payload.py",
    "tools/apply_modules.py",
    ".claude/",
)


def run_git(args: list[str], cwd: Path = REPO_ROOT) -> str:
    """Run a git command and return stdout (strip trailing newline)."""
    res = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout.rstrip("\n")


def is_module_path(path: str) -> bool:
    """True if path belongs to one of our shipped module dirs."""
    return any(path == d or path.startswith(d + "/") for d in MODULE_DIRS)


def is_excluded(path: str) -> bool:
    if path in EXCLUDE_PATHS:
        return True
    return any(path.startswith(p) for p in EXCLUDE_PREFIXES)


def list_diff_files(baseline: str) -> list[str]:
    """Return all file paths that differ between baseline and HEAD."""
    raw = run_git(["diff", "--name-only", f"{baseline}..HEAD"])
    return [line for line in raw.splitlines() if line]


def file_patch(baseline: str, path: str) -> str:
    """Return unified diff for one file (baseline -> HEAD)."""
    try:
        return run_git(["diff", f"{baseline}..HEAD", "--", path])
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"!! git diff failed for {path}: {exc.stderr}\n")
        return ""


def copy_module_dir(src_rel: str, payload_root: Path) -> int:
    """Copy a module dir into payload/modules/<src_rel>/. Returns file count."""
    src = REPO_ROOT / src_rel
    if not src.is_dir():
        sys.stderr.write(f"!! module dir missing: {src_rel}\n")
        return 0
    dst = payload_root / "modules" / src_rel
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )
    return sum(1 for _ in dst.rglob("*") if _.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--baseline",
        default="8f1a21c",
        help="Upstream commit/tag the patches are taken against (default: 8f1a21c = v1.4.0dev4).",
    )
    parser.add_argument(
        "--out",
        default="tools/payload",
        help="Output directory (relative to repo root). Will be wiped+recreated.",
    )
    args = parser.parse_args()

    payload_root = (REPO_ROOT / args.out).resolve()

    # Wipe + recreate the output dir so stale entries from older runs disappear.
    if payload_root.exists():
        shutil.rmtree(payload_root)
    (payload_root / "patches").mkdir(parents=True)
    (payload_root / "modules").mkdir(parents=True)

    # 1) Copy all our module dirs verbatim.
    module_summary = {}
    for mod_path in MODULE_DIRS:
        n = copy_module_dir(mod_path, payload_root)
        module_summary[mod_path] = n
        print(f"  copied {n:>4} files from {mod_path}")

    # 2) Diff every other touched file → unified diff in patches/.
    diff_files = list_diff_files(args.baseline)
    print(f"\nDiffing {len(diff_files)} touched files vs {args.baseline} …")
    patch_index: list[dict] = []
    skipped: list[str] = []

    for path in diff_files:
        if is_module_path(path):
            continue  # shipped via copy, not patch
        if is_excluded(path):
            skipped.append(path)
            continue
        diff_text = file_patch(args.baseline, path)
        if not diff_text.strip():
            continue
        patch_rel = f"patches/{path}.patch"
        out_file = payload_root / patch_rel
        out_file.parent.mkdir(parents=True, exist_ok=True)
        # `git apply` likes a trailing newline; ensure one.
        if not diff_text.endswith("\n"):
            diff_text += "\n"
        out_file.write_text(diff_text)
        patch_index.append({"target": path, "patch": patch_rel})

    # 3) Manifest — single source of truth for apply_modules.py.
    head_sha = run_git(["rev-parse", "HEAD"])
    manifest = {
        "schema_version": 1,
        "baseline_sha": args.baseline,
        "built_at_head": head_sha,
        "module_dirs": MODULE_DIRS,
        "patches": patch_index,
        "excluded": sorted(skipped),
    }
    (payload_root / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"\n✓ Payload written to {payload_root.relative_to(REPO_ROOT)}")
    print(f"  module dirs:   {len(MODULE_DIRS)} ({sum(module_summary.values())} files)")
    print(f"  patches:       {len(patch_index)}")
    print(f"  excluded:      {len(skipped)} (deploy script, log, schema JSONs, …)")
    print(f"  baseline:      {args.baseline}")
    print(f"  built at HEAD: {head_sha[:10]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
