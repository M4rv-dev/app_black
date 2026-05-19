"""Invoke task collection for BoneIO fork deployment + dev ops.

Replaces the original ``deploy_backend.sh`` (which baked credentials into
the repo). Run ``invoke --list`` to see all tasks.

Quick start::

    pip install invoke fabric keyring                    # one-time
    inv configure                                        # set host + creds
    inv deploy                                           # rsync + restart
    inv logs --follow                                    # tail journal
    inv status                                           # service + http health
    inv regen-schemas                                    # rebuild webui/schema/*.json on device

Secrets policy
--------------
The device password lives in two places, in priority order:

1. ``$BONEIO_DEPLOY_PASSWORD`` env var — handy for CI / one-off shells.
2. System keyring (macOS Keychain / Secret Service) under service name
   ``boneio-deploy``, account = the host alias (e.g. ``boneio@192.168.1.22``).

If neither is set, ``inv configure`` prompts once and stores in the keyring.
Plain-text credentials NEVER live in the repo, in shell history, or in
process env unless the user explicitly exports them.

Host / connection settings live in ``~/.config/boneio-deploy/config.toml``
so the repo carries zero machine-specific data. ``inv configure`` writes it.
"""
from __future__ import annotations

import getpass
import io
import json
import os
import posixpath
import shutil
import sys
import tempfile
import textwrap
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from invoke import task

try:
    import keyring
except ImportError:  # pragma: no cover — only triggers on under-equipped envs
    keyring = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = Path(os.path.expanduser("~/.config/boneio-deploy"))
CONFIG_FILE = CONFIG_DIR / "config.toml"
KEYRING_SERVICE = "boneio-deploy"


# ----------------------------------------------------------------------
# Config + secrets
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class HostConfig:
    """All host-specific settings — loaded from ~/.config/boneio-deploy/config.toml."""
    user: str
    host: str
    site_packages: str
    staging: str = "/tmp/boneio_deploy"
    service: str = "boneio.service"
    port: int = 8090

    @property
    def user_host(self) -> str:
        return f"{self.user}@{self.host}"

    @property
    def ssh_opts(self) -> list[str]:
        return [
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR",
        ]


def _load_config() -> HostConfig:
    """Read ~/.config/boneio-deploy/config.toml or die with a useful hint."""
    if not CONFIG_FILE.is_file():
        sys.exit(
            f"No config at {CONFIG_FILE}.\n"
            f"Run `inv configure` first."
        )
    data = tomllib.loads(CONFIG_FILE.read_text())
    try:
        return HostConfig(**data["device"])
    except (KeyError, TypeError) as exc:
        sys.exit(f"Malformed {CONFIG_FILE}: {exc}\nRe-run `inv configure`.")


def _get_password(cfg: HostConfig) -> str:
    """Resolve device password from env → keyring. Used only for sudo commands."""
    env_pw = os.environ.get("BONEIO_DEPLOY_PASSWORD")
    if env_pw:
        return env_pw
    if keyring is None:
        sys.exit(
            "python-keyring not installed and BONEIO_DEPLOY_PASSWORD is unset.\n"
            "Install with `pip install keyring` or export the env var."
        )
    pw = keyring.get_password(KEYRING_SERVICE, cfg.user_host)
    if pw:
        return pw
    sys.exit(
        f"No password in keyring for {KEYRING_SERVICE}/{cfg.user_host}.\n"
        "Run `inv configure` to store it, or export BONEIO_DEPLOY_PASSWORD."
    )


def _need_tool(cmd: str, install_hint: str) -> None:
    """Bail out with a clear message if a required CLI tool is missing."""
    from shutil import which
    if which(cmd) is None:
        sys.exit(f"Missing required tool: {cmd}\n  → {install_hint}")


# ----------------------------------------------------------------------
# SSH helpers — thin wrappers over ssh/scp/rsync (key auth).
# Plain ssh + key auth; sudo calls still pipe the keyring password via -S.
# Keep it transparent: every helper just builds the argv and exec's it.
# ----------------------------------------------------------------------

def _ssh(cfg: HostConfig, password: str | None, remote_cmd: str, *, ctx, hide: bool = False) -> object:
    """Run ``remote_cmd`` on the device via ssh (key auth). Returns Invoke's Result."""
    argv = ["ssh", *cfg.ssh_opts, cfg.user_host, remote_cmd]
    return ctx.run(" ".join(_shell_quote(a) for a in argv), hide=hide, pty=False, warn=True)


def _ssh_sudo(cfg: HostConfig, password: str, remote_cmd: str, *, ctx, hide: bool = False) -> object:
    """Run ``remote_cmd`` with sudo on the device (password piped via -S)."""
    wrapped = f"echo {_shell_quote(password)} | sudo -S bash -c {_shell_quote(remote_cmd)}"
    return _ssh(cfg, None, wrapped, ctx=ctx, hide=hide)


def _rsync(cfg: HostConfig, password: str | None, src: str, dst_rel: str, *, ctx) -> None:
    """rsync local src → host:staging/dst_rel, with sane defaults (key auth)."""
    ssh_cmd = f"ssh {' '.join(cfg.ssh_opts)}"
    argv = [
        "rsync", "-az",
        "--exclude=__pycache__/", "--exclude=*.pyc", "--exclude=*.pyo",
        "--exclude=.DS_Store",
        "-e", ssh_cmd,
        src,
        f"{cfg.user_host}:{cfg.staging}/{dst_rel}",
    ]
    ctx.run(" ".join(_shell_quote(a) for a in argv), pty=False)


def _shell_quote(s: str) -> str:
    """Single-quote for POSIX shell, escaping any embedded single quotes."""
    if not s:
        return "''"
    if all(c.isalnum() or c in "-_./=@:," for c in s):
        return s
    return "'" + s.replace("'", "'\\''") + "'"


# ----------------------------------------------------------------------
# Tasks
# ----------------------------------------------------------------------

@task(help={
    "user": "Device SSH username (e.g. boneio).",
    "host": "Device IP or hostname (e.g. 192.168.1.22).",
    "site-packages": "Absolute path to the boneio package on the device.",
})
def configure(c, user="boneio", host="192.168.1.22",
              site_packages="/home/boneio/boneio/venv/lib/python3.13/site-packages/boneio"):
    """Interactive: write ~/.config/boneio-deploy/config.toml + stash password in keyring."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config_text = (
        "# Generated by `inv configure` — edit by hand to taste.\n"
        "[device]\n"
        f'user = "{user}"\n'
        f'host = "{host}"\n'
        f'site_packages = "{site_packages}"\n'
        'staging = "/tmp/boneio_deploy"\n'
        'service = "boneio.service"\n'
        'port = 8090\n'
    )
    CONFIG_FILE.write_text(config_text)
    print(f"✓ wrote {CONFIG_FILE}")

    if keyring is None:
        print("⚠ python-keyring not installed — skipping password prompt.")
        print("  Install with `pip install keyring`, then re-run `inv configure`.")
        return

    user_host = f"{user}@{host}"
    existing = keyring.get_password(KEYRING_SERVICE, user_host)
    if existing:
        confirm = input(f"Password for {user_host} already in keyring. Replace? [y/N] ").strip().lower()
        if confirm != "y":
            print("Keeping existing keyring entry.")
            return

    pw = getpass.getpass(f"Password for {user_host}: ")
    if not pw:
        print("Empty password — nothing stored.")
        return
    keyring.set_password(KEYRING_SERVICE, user_host, pw)
    print(f"✓ stored password in system keyring as {KEYRING_SERVICE}/{user_host}")


SNAPSHOT_RETENTION = 3  # keep last N snapshots for rollback


def _snapshot_install(cfg: HostConfig, password: str, *, ctx) -> str:
    """Snapshot the current site-packages/boneio dir to a sibling with timestamp.

    Returns the snapshot path on the device. Garbage-collects snapshots older
    than SNAPSHOT_RETENTION. Snapshots live on the device, NOT in git — they're
    the rollback source for ``inv rollback``.
    """
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parent = os.path.dirname(cfg.site_packages.rstrip("/"))
    snap = f"{cfg.site_packages.rstrip('/')}_prev_{ts}"
    # Use cp -a to preserve perms/times; less surprising than rsync for this.
    cmd = (
        f"cp -a {cfg.site_packages} {snap} && "
        # GC: keep newest N snapshots, rm older.
        f"ls -1dt {parent}/boneio_prev_* 2>/dev/null | tail -n +$(( {SNAPSHOT_RETENTION} + 1 )) | xargs -r rm -rf"
    )
    res = _ssh_sudo(cfg, password, cmd, ctx=ctx, hide=True)
    if res.exited != 0:
        sys.exit(f"!! snapshot failed (deploy aborted before any change):\n{res.stderr or res.stdout}")
    return snap


@task(help={
    "fast": "Skip service restart (rsync only — for hot-reloadable changes).",
    "no-health": "Skip post-deploy health check.",
    "no-snapshot": "Skip the pre-deploy snapshot (FAST but no rollback path).",
})
def deploy(c, fast=False, no_health=False, no_snapshot=False):
    """Rsync boneio/ to the device, install into site-packages, restart service.

    Default flow is atomic + recoverable:
      1. snapshot current install → boneio_prev_<UTC-timestamp>
      2. rsync local → staging dir on device
      3. cp staging → site-packages, restart service
      4. healthcheck waits for HTTP 2xx, reports service state

    On healthcheck failure, ``inv rollback`` restores the snapshot.
    """
    cfg = _load_config()
    pw = _get_password(cfg)
    _need_tool("rsync", "install via your package manager")

    src = REPO_ROOT / "boneio"
    if not src.is_dir():
        sys.exit(f"!! {src} does not exist — are you in the repo root?")

    if not no_snapshot and not fast:
        print("→ Snapshotting current install (for rollback) …")
        snap = _snapshot_install(cfg, pw, ctx=c)
        print(f"  snapshot: {snap}")

    print(f"→ Staging on {cfg.user_host} …")
    _ssh(cfg, pw, f"rm -rf {cfg.staging} && mkdir -p {cfg.staging}", ctx=c)

    print(f"→ rsyncing {src.name}/ to {cfg.staging}/ …")
    _rsync(cfg, pw, f"{src}/", "", ctx=c)

    print(f"→ Installing into {cfg.site_packages}/ …")
    install_cmd = f"cp -r {cfg.staging}/. {cfg.site_packages}/ && rm -rf {cfg.staging}"
    if not fast:
        install_cmd += f" && systemctl restart {cfg.service}"
    res = _ssh_sudo(cfg, pw, install_cmd, ctx=c, hide=True)
    if res.exited != 0:
        sys.exit(f"!! install/restart failed:\n{res.stderr or res.stdout}")

    if fast:
        print("✓ Files installed (service NOT restarted — use `inv restart` if needed).")
    else:
        print("✓ Files installed, service restarted.")

    if not no_health and not fast:
        health(c)


@task(help={"keep-snapshot": "Keep the snapshot dir after rollback (default: kept; pass --no-keep-snapshot to delete)."})
def rollback(c, keep_snapshot=True):
    """Restore the most recent pre-deploy snapshot + restart service.

    Lists snapshots, picks the newest, swaps it back into site-packages,
    restarts. Verifies with healthcheck. Bails noisily if no snapshots exist.
    """
    cfg = _load_config()
    pw = _get_password(cfg)

    parent = os.path.dirname(cfg.site_packages.rstrip("/"))
    list_cmd = f"ls -1dt {parent}/boneio_prev_* 2>/dev/null | head -1"
    res = _ssh_sudo(cfg, pw, list_cmd, ctx=c, hide=True)
    snap = (res.stdout or "").strip()
    if not snap:
        sys.exit(f"!! No snapshots found under {parent}/boneio_prev_* — nothing to roll back to.")

    print(f"→ Rolling back to {snap}")
    # Move current → broken_<ts>, snap → current, then optionally remove broken.
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    broken = f"{cfg.site_packages.rstrip('/')}_broken_{ts}"
    cmd = (
        f"mv {cfg.site_packages} {broken} && "
        f"cp -a {snap} {cfg.site_packages} && "
        f"systemctl restart {cfg.service}"
    )
    if not keep_snapshot:
        cmd += f" && rm -rf {snap}"
    res = _ssh_sudo(cfg, pw, cmd, ctx=c, hide=True)
    if res.exited != 0:
        sys.exit(f"!! rollback failed:\n{res.stderr or res.stdout}")

    print(f"✓ Restored snapshot, service restarted.")
    print(f"  Broken install kept at: {broken} (delete manually if rollback is good).")
    health(c)


@task
def snapshots(c):
    """List pre-deploy snapshots on the device, newest first."""
    cfg = _load_config()
    pw = _get_password(cfg)
    parent = os.path.dirname(cfg.site_packages.rstrip("/"))
    res = _ssh_sudo(
        cfg, pw, f"ls -1dt {parent}/boneio_prev_* 2>/dev/null || echo '(none)'",
        ctx=c, hide=True,
    )
    print(res.stdout.rstrip() or "(none)")


@task(help={
    "out": "Local directory to write the backup into (default: ./backups/<timestamp>/).",
})
def backup(c, out=""):
    """Pull device state (config + state.json + cached validated config) to local dir.

    Lets you keep a recoverable copy of the device's RUNTIME state — not
    captured by git. Snapshot dir lives outside the repo by default (gitignored
    if inside it). Pair with `inv rollback` for full disaster recovery.
    """
    from datetime import datetime, timezone
    cfg = _load_config()
    pw = _get_password(cfg)
    _need_tool("rsync", "install via your package manager")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst = Path(out) if out else REPO_ROOT.parent / "boneio_backups" / ts
    dst.mkdir(parents=True, exist_ok=True)

    # Pull each known interesting path. Use rsync --ignore-missing-args so a
    # not-yet-existing cache file doesn't break the whole backup.
    paths = [
        "/home/boneio/boneio/config.yaml",
        "/home/boneio/boneio/state.json",
        "/home/boneio/boneio/config.yaml.cache.pkl",
    ]
    for p in paths:
        argv = [
            "rsync", "-az", "--ignore-missing-args",
            "-e", f"ssh {' '.join(cfg.ssh_opts)}",
            f"{cfg.user_host}:{p}", str(dst) + "/",
        ]
        c.run(" ".join(_shell_quote(a) for a in argv), pty=False, warn=True)

    files = sorted(p.name for p in dst.iterdir() if p.is_file())
    print(f"✓ Backup written to {dst}")
    for f in files:
        print(f"  - {f}")


@task
def smoke(c):
    """Post-deploy smoke test — service active + HTTP 200 + no fatal errors in last 60s.

    Returns non-zero exit if any check fails so it's easy to use in scripts.
    """
    cfg = _load_config()
    pw = _get_password(cfg)
    ok = True

    # 1. Service active.
    res = _ssh_sudo(cfg, pw, f"systemctl is-active {cfg.service}", ctx=c, hide=True)
    state = (res.stdout or res.stderr).strip()
    print(f"[{'✓' if state == 'active' else '✗'}] service is-active: {state}")
    ok &= state == "active"

    # 2. HTTP probe.
    res = c.run(
        f"curl -sS -o /dev/null -w '%{{http_code}}' --max-time 5 http://{cfg.host}:{cfg.port}/",
        hide=True, warn=True, pty=False,
    )
    code = (res.stdout or "").strip()
    http_ok = code.startswith(("2", "3"))
    print(f"[{'✓' if http_ok else '✗'}] HTTP :{cfg.port}: {code or 'unreachable'}")
    ok &= http_ok

    # 3. No fatal errors in journal over last 60s.
    res = _ssh_sudo(
        cfg, pw,
        f"journalctl -u {cfg.service} --since '60 seconds ago' --no-pager 2>&1 | "
        f"grep -E 'CRITICAL|Traceback|Error.*boot|cannot start' | grep -v modbus | head -5",
        ctx=c, hide=True,
    )
    fatal = (res.stdout or "").strip()
    has_fatal = bool(fatal)
    print(f"[{'✗' if has_fatal else '✓'}] fatal log scan: {'errors found' if has_fatal else 'clean'}")
    if has_fatal:
        for line in fatal.splitlines():
            print(f"    {line}")
    ok &= not has_fatal

    # 4. /api/version returns valid JSON.
    res = c.run(
        f"curl -sS --max-time 5 http://{cfg.host}:{cfg.port}/api/version",
        hide=True, warn=True, pty=False,
    )
    try:
        ver_data = json.loads(res.stdout or "{}")
        ver_ok = isinstance(ver_data, dict) and "version" in ver_data
        ver_str = ver_data.get("version", "?") if isinstance(ver_data, dict) else "?"
        print(f"[{'✓' if ver_ok else '✗'}] /api/version: {ver_str if ver_ok else (res.stdout or '').strip()[:80]!r}")
        ok &= ver_ok
    except ValueError:
        print(f"[✗] /api/version: invalid JSON ({(res.stdout or '').strip()[:80]!r})")
        ok = False

    # 5. WebSocket handshake — connect, wait for first message, disconnect.
    ws_url = f"ws://{cfg.host}:{cfg.port}/ws/state"
    ws_script = textwrap.dedent(f"""
        import asyncio, sys
        async def _check():
            try:
                import websockets.asyncio.client as _w
                async with _w.connect({ws_url!r}, open_timeout=5) as ws:
                    await asyncio.wait_for(ws.recv(), timeout=5)
                    print("ok")
            except Exception as e:
                print("err", e)
                sys.exit(1)
        asyncio.run(_check())
    """)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
        tmp.write(ws_script)
        tmp_path = tmp.name
    res = c.run(f"python3 {tmp_path}", hide=True, warn=True, pty=False)
    Path(tmp_path).unlink(missing_ok=True)
    ws_ok = "ok" in (res.stdout or "")
    ws_detail = (res.stdout or res.stderr or "").strip()[:80]
    print(f"[{'✓' if ws_ok else '✗'}] WebSocket handshake {ws_url}: {ws_detail or 'no output'}")
    ok &= ws_ok

    if not ok:
        sys.exit("\n!! Smoke test FAILED — investigate before considering deploy successful.")
    print("\n✓ Smoke test passed.")


@task
def restart(c):
    """Restart the boneio.service (no file transfer)."""
    cfg = _load_config()
    pw = _get_password(cfg)
    res = _ssh_sudo(cfg, pw, f"systemctl restart {cfg.service}", ctx=c, hide=True)
    if res.exited != 0:
        sys.exit(f"!! restart failed:\n{res.stderr or res.stdout}")
    print("✓ Restart issued.")
    health(c)


@task(help={"timeout": "Max seconds to wait for healthy response."})
def health(c, timeout=30):
    """Wait until the device webui responds 2xx, then report service status."""
    cfg = _load_config()
    pw = _get_password(cfg)

    print(f"→ Waiting (up to {timeout}s) for http://{cfg.host}:{cfg.port}/ …")
    deadline = time.time() + timeout
    last_err: str | None = None
    while time.time() < deadline:
        res = c.run(
            f"curl -sS -o /dev/null -w '%{{http_code}}' --max-time 3 http://{cfg.host}:{cfg.port}/",
            hide=True, warn=True, pty=False,
        )
        code = (res.stdout or "").strip()
        if code.startswith(("2", "3")):
            print(f"✓ http://{cfg.host}:{cfg.port}/ returned HTTP {code}")
            break
        last_err = code or res.stderr.strip()
        time.sleep(1.5)
    else:
        print(f"⚠ health check timed out (last response: {last_err!r})")

    # systemctl status for context — short form, no pager.
    res = _ssh_sudo(cfg, pw, f"systemctl is-active {cfg.service}", ctx=c, hide=True)
    state = (res.stdout or res.stderr).strip()
    print(f"  service state: {state}")


@task(help={
    "follow": "Tail -f the journal instead of dumping the last N lines.",
    "lines": "How many recent lines to fetch when not following (default 60).",
    "grep": "Optional grep pattern (case-insensitive).",
})
def logs(c, follow=False, lines=60, grep=""):
    """Stream / fetch boneio.service logs from the device."""
    cfg = _load_config()
    pw = _get_password(cfg)
    base = f"journalctl -u {cfg.service} --no-pager"
    if follow:
        base += " -f"
    else:
        base += f" -n {int(lines)}"
    if grep:
        base += f" | grep -i {_shell_quote(grep)}"
    # For -f we want streaming output, so we drop hide=True and let stdout flow.
    _ssh_sudo(cfg, pw, base, ctx=c, hide=False)


@task
def status(c):
    """Quick summary: service active state + HTTP code + last 5 log lines."""
    cfg = _load_config()
    pw = _get_password(cfg)

    # Service state.
    res = _ssh_sudo(cfg, pw, f"systemctl is-active {cfg.service}", ctx=c, hide=True)
    print(f"service:  {(res.stdout or res.stderr).strip()}")

    # HTTP probe.
    res = c.run(
        f"curl -sS -o /dev/null -w '%{{http_code}}' --max-time 3 http://{cfg.host}:{cfg.port}/",
        hide=True, warn=True, pty=False,
    )
    print(f"http :{cfg.port}: {(res.stdout or '').strip() or 'unreachable'}")

    # Last 5 log lines for quick context.
    res = _ssh_sudo(
        cfg, pw, f"journalctl -u {cfg.service} -n 5 --no-pager",
        ctx=c, hide=True,
    )
    print("recent log:")
    for line in (res.stdout or "").splitlines():
        print(f"  {line}")


@task(help={
    "no-install": "Skip copying built assets into boneio/webui/frontend-dist/ (build only).",
})
def build_frontend(c, no_install=False):
    """Build the Vite frontend and install it into boneio/webui/frontend-dist/.

    Requires pnpm (or npm) installed locally. Run before ``inv deploy`` when
    frontend files changed. The built assets are committed to the repo so the
    backend can serve them without a build step on the device.
    """
    frontend_dir = REPO_ROOT / "frontend"
    if not frontend_dir.is_dir():
        sys.exit(f"!! {frontend_dir} does not exist.")

    _need_tool("pnpm", "npm install -g pnpm  (or use npm/yarn)")

    print("→ installing frontend dependencies …")
    c.run("pnpm install --frozen-lockfile", cwd=str(frontend_dir), pty=False)

    print("→ building frontend (tsc + vite) …")
    c.run("pnpm run build", cwd=str(frontend_dir), pty=False)

    if no_install:
        print("✓ frontend built (assets in frontend/dist/).")
        return

    dist_src = frontend_dir / "dist"
    dist_dst = REPO_ROOT / "boneio" / "webui" / "frontend-dist"

    if not dist_src.is_dir():
        sys.exit(f"!! Build output not found at {dist_src} — did the build succeed?")

    print(f"→ installing built assets into {dist_dst.relative_to(REPO_ROOT)}/ …")
    if dist_dst.exists():
        shutil.rmtree(dist_dst)
    shutil.copytree(dist_src, dist_dst)
    print(f"✓ frontend installed into {dist_dst.relative_to(REPO_ROOT)}/")


@task(help={
    "fast": "Skip service restart on backend deploy.",
    "no-health": "Skip post-deploy health check.",
    "no-snapshot": "Skip pre-deploy snapshot (no rollback path).",
    "frontend-only": "Only build + install frontend, skip backend rsync.",
    "backend-only": "Only rsync backend, skip frontend build.",
})
def deploy_full(c, fast=False, no_health=False, no_snapshot=False,
                frontend_only=False, backend_only=False):
    """Build frontend + deploy backend in one command.

    Full flow:
      1. pnpm build → copy to boneio/webui/frontend-dist/
      2. snapshot current install (rollback source)
      3. rsync boneio/ to device
      4. restart service + healthcheck

    Use ``--frontend-only`` when only UI files changed (skips rsync + restart).
    Use ``--backend-only`` to skip frontend build (same as ``inv deploy``).
    """
    if not backend_only:
        build_frontend(c)

    if not frontend_only:
        deploy(c, fast=fast, no_health=no_health, no_snapshot=no_snapshot)
    else:
        print("✓ Frontend built and installed. Backend not deployed (--frontend-only).")


@task
def regen_schemas(c, sync_back=False):
    """Re-run schema_converter on the device + optionally rsync results back.

    The module-extended schemas are generated by Python on arm64 (your mac
    can't run psutil x86_64). After bigger refactors run this to keep
    boneio/webui/schema/*.json in sync.
    """
    cfg = _load_config()
    pw = _get_password(cfg)

    venv_python = "/home/boneio/boneio/venv/bin/python3"
    cmd = f"cd {cfg.site_packages}/.. && {venv_python} -m boneio.core.config.schema_converter"
    print("→ regenerating schemas on device …")
    res = _ssh_sudo(cfg, pw, cmd, ctx=c, hide=True)
    if res.exited != 0:
        sys.exit(f"!! schema regen failed:\n{res.stderr or res.stdout}")

    if not sync_back:
        print("✓ schemas regenerated on device.")
        print("  Pass `--sync-back` to rsync them into the local repo.")
        return

    _need_tool("rsync", "install via your package manager")
    src = f"{cfg.user_host}:{cfg.site_packages}/webui/schema/"
    dst = REPO_ROOT / "boneio" / "webui" / "schema"
    argv = [
        "rsync", "-az",
        "-e", f"ssh {' '.join(cfg.ssh_opts)}",
        src, str(dst) + "/",
    ]
    c.run(" ".join(_shell_quote(a) for a in argv), pty=False)
    print(f"✓ synced regenerated schemas into {dst.relative_to(REPO_ROOT)}/")


@task(help={
    "path": "Test path / pattern to run (default: tests/unit/core/).",
    "markers": "Pytest -m expression (default: 'not hardware').",
    "verbose": "Pass -v to pytest for detailed output.",
})
def test(c, path="tests/unit/core/", markers="not hardware", verbose=False):
    """Sync tests to the device and run pytest inside the device venv.

    Copies ``tests/`` and ``pyproject.toml`` to the device, installs
    pytest into the existing venv (one-time), then runs the suite.
    Results are streamed back via SSH.
    """
    cfg = _load_config()
    pw = _get_password(cfg)
    # site_packages = .../venv/lib/python3.xx/site-packages/boneio
    # device_base   = grandparent of venv/ = 5 levels up
    venv_dir = posixpath.dirname(  # site-packages
        posixpath.dirname(          # python3.xx
        posixpath.dirname(          # lib
        posixpath.dirname(          # venv
        posixpath.dirname(cfg.site_packages)))))
    device_base = venv_dir
    venv_python = posixpath.join(venv_dir, "venv", "bin", "python")

    # Use a dedicated staging dir on device — keeps it separate from the live install.
    test_dir = "/tmp/boneio_tests"
    _ssh(cfg, pw, f"mkdir -p {test_dir}", ctx=c, hide=True)

    # Sync boneio source + tests + pyproject via scp.
    print("→ syncing boneio source + tests/ to device …")
    for local, remote in [
        (str(REPO_ROOT / "boneio"), f"{cfg.user_host}:{test_dir}/"),
        (str(REPO_ROOT / "tests"), f"{cfg.user_host}:{test_dir}/"),
        (str(REPO_ROOT / "pyproject.toml"), f"{cfg.user_host}:{test_dir}/pyproject.toml"),
    ]:
        argv = ["scp", "-r"] + cfg.ssh_opts + [local, remote]
        c.run(" ".join(_shell_quote(a) for a in argv), pty=False, warn=True)

    # Ensure pytest is installed in device venv.
    print("→ ensuring pytest is installed in device venv …")
    res = _ssh(cfg, pw,
        f"{venv_python} -m pip install --quiet pytest pytest-asyncio",
        ctx=c, hide=True,
    )
    if res.exited != 0:
        sys.exit(f"!! pip install pytest failed:\n{res.stderr or res.stdout}")

    # Run pytest from test_dir with venv activated.
    verbosity = "-v" if verbose else "-q"
    pytest_cmd = (
        f"cd {test_dir} && "
        f". {venv_dir}/venv/bin/activate && "
        f"pytest {path} -m {_shell_quote(markers)} {verbosity} --tb=short --no-header"
    )

    print(f"→ running: pytest {path} -m '{markers}' on {cfg.host} …\n")
    _ssh(cfg, pw, pytest_cmd, ctx=c, hide=False)
