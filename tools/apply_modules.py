#!/usr/bin/env python3
"""Apply a module payload (built by build_modules_payload.py) onto a fresh tree.

Workflow:
    # On developer machine, build the payload from current fork HEAD:
    python tools/build_modules_payload.py --baseline 8f1a21c --out tools/payload

    # Ship payload/ to wherever (commit, tarball, scp …).

    # On a fresh upstream checkout (any tag ≥ baseline, ideally the baseline
    # itself for a clean POC):
    python tools/apply_modules.py --payload tools/payload --target /path/to/upstream

What it does, in order:
1. Reads payload/MANIFEST.json.
2. Verifies the target is a git tree (so we get a clean apply trail and can
   roll back on failure).
3. Copies every module dir into target/<same path>.
4. Applies every patch with ``git apply --3way`` so context shifts in
   upstream get a chance to be auto-merged; on failure prints which patch
   failed and exits non-zero so you know exactly what to investigate.

Idempotency: applying twice in a row is a no-op for module-dir copies (we
overwrite), and patches will fail the second time (already applied) — that's
the safe behaviour, you should re-build the payload against the new baseline
instead.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def assert_git_tree(target: Path) -> None:
    """Refuse to apply onto a non-git tree (we want a rollback path)."""
    try:
        run(["git", "rev-parse", "--git-dir"], cwd=target)
    except subprocess.CalledProcessError:
        sys.exit(f"!! {target} is not a git tree — refuse to apply (no rollback path).")


def copy_module_dirs(payload: Path, target: Path, module_dirs: list[str]) -> int:
    """Copy each module dir from payload/modules/<path> over target/<path>."""
    total = 0
    for mod_rel in module_dirs:
        src = payload / "modules" / mod_rel
        if not src.is_dir():
            print(f"  ⚠ payload missing module dir: {mod_rel}")
            continue
        dst = target / mod_rel
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        n = sum(1 for _ in dst.rglob("*") if _.is_file())
        total += n
        print(f"  copied {n:>4} files → {mod_rel}")
    return total


def apply_patches(payload: Path, target: Path, patches: list[dict]) -> tuple[int, list[str]]:
    """Apply each patch via ``git apply --3way``. Return (ok, [failed_targets])."""
    ok = 0
    failed: list[str] = []
    for entry in patches:
        patch_file = payload / entry["patch"]
        if not patch_file.is_file():
            print(f"  ⚠ patch file missing: {entry['patch']}")
            failed.append(entry["target"])
            continue
        # `--3way` lets git auto-merge if the upstream file shifted but the
        # blob still has compatible context. Falls back to a hard fail with
        # conflict markers in the file (apply_modules then bails).
        res = run(
            ["git", "apply", "--3way", "--whitespace=nowarn", str(patch_file)],
            cwd=target,
            check=False,
        )
        if res.returncode == 0:
            ok += 1
            print(f"  ✓ applied: {entry['target']}")
        else:
            failed.append(entry["target"])
            print(f"  ✗ FAILED:  {entry['target']}")
            if res.stderr.strip():
                # Indent stderr so it's easy to read in the log.
                for line in res.stderr.splitlines():
                    print(f"      {line}")
    return ok, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--payload", required=True, help="Path to payload dir built by build_modules_payload.py.")
    parser.add_argument("--target", required=True, help="Path to a fresh upstream checkout (must be a git tree).")
    args = parser.parse_args()

    payload = Path(args.payload).resolve()
    target = Path(args.target).resolve()

    manifest_file = payload / "MANIFEST.json"
    if not manifest_file.is_file():
        sys.exit(f"!! {manifest_file} not found — was the payload built?")

    manifest = json.loads(manifest_file.read_text())
    print(f"Applying payload built at HEAD={manifest['built_at_head'][:10]} "
          f"(baseline={manifest['baseline_sha']}) onto {target}\n")

    assert_git_tree(target)

    # 1) Module dirs first — patches may reference symbols defined in them.
    print("Copying module dirs:")
    n_files = copy_module_dirs(payload, target, manifest["module_dirs"])
    print(f"  total module files: {n_files}\n")

    # 2) Then patches onto upstream files.
    print(f"Applying {len(manifest['patches'])} patches with `git apply --3way`:")
    ok, failed = apply_patches(payload, target, manifest["patches"])
    print(f"\n  applied: {ok} / {len(manifest['patches'])}")

    if failed:
        print("\n✗ Some patches FAILED — re-run after fixing upstream conflicts:")
        for f in failed:
            print(f"    {f}")
        print("\nTip: run `git -C {target} diff` to see partial state, then either")
        print("     hand-resolve the .rej/conflict markers or rebuild the payload")
        print("     against a newer baseline.")
        return 1

    print("\n✓ All patches applied cleanly. The tree is ready to build/deploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
