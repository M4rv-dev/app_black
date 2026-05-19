# Ops — deploy, observe, recover

Operational runbook for this BoneIO fork. **For development workflow see CLAUDE.md / WORK_LOG.md.** This file is what you read at 2 AM when something's on fire.

## One-time setup (per machine)

```bash
pip install invoke keyring          # deploy CLI + secret store
inv configure                       # interactive: host + creds → keyring
brew install hudochenkov/sshpass/sshpass   # macOS prereq (rsync over ssh-with-password)
pip install pre-commit && pre-commit install   # blocks credential leaks on commit
```

Secrets policy: **the device password never lives in the repo or in a tracked file**. It's pulled (in priority order) from `$BONEIO_DEPLOY_PASSWORD` env var, then the macOS Keychain / Linux Secret Service under service name `boneio-deploy`. `inv configure` stashes it once.

Config (host, paths) lives in `~/.config/boneio-deploy/config.toml`, written by `inv configure`.

## Daily verbs

| Command | When |
|---|---|
| `inv deploy-full` | **Preferred** — build frontend + snapshot → rsync → restart → healthcheck in one command. |
| `inv deploy-full --backend-only` | Python-only change — skips frontend build (same as `inv deploy`). |
| `inv deploy-full --frontend-only` | UI-only change — builds + installs frontend, no device rsync or restart. |
| `inv deploy` | Backend-only deploy (no frontend build). |
| `inv deploy --fast` | Only hot-reloadable changes (e.g. config UI), skips restart. |
| `inv build-frontend` | Build Vite + copy to `boneio/webui/frontend-dist/` without deploying. |
| `inv restart` | Config-only fix, no file changes. |
| `inv status` | "Is it up?" — service state + HTTP 200 + last 5 log lines. |
| `inv logs --follow` | Live tail. Add `--grep PATTERN` to filter. |
| `inv logs --lines 200` | Recent N lines. |
| `inv smoke` | Stronger than `status`: scans for fatal errors in last 60s. Exits non-zero on failure (script-friendly). |
| `inv health` | Just the HTTP probe + wait-for-up. |
| `inv regen-schemas --sync-back` | After backend schema refactor — regenerates JSON schemas on device (arm64 native) + pulls into repo. |

## When a deploy goes wrong

1. **First, observe**: `inv logs --lines 100 | head -50` — pick up the actual error.
2. **If clearly broken**: `inv rollback` — restores the previous snapshot, restarts, healthchecks. Each `inv deploy` writes a snapshot at `…/site-packages/boneio_prev_<UTC-timestamp>` before touching the install dir; up to 3 are kept (`inv snapshots` lists them).
3. **If state is hosed too**: `inv backup` *first* (to capture the bad state for analysis), *then* fix `~/.boneio/state.json` or the config on the device, then `inv restart`.
4. **If you can't even ssh**: physical access to the BBB + serial console. Logs are at `/var/log/boneio/` (overrides via journald).

## When upstream releases a new version

We're a fork. New upstream features live in upstream's repo; ours add `modules/expander/` + `modules/remote_mqtt/` + a small set of injection points. To merge a new upstream tag:

1. `git fetch origin && git merge origin/dev-debian13` — apply normal git conflict resolution for any of OUR upstream-side touches. Most conflicts will be in `frontend/src/components/UISettings/*` and `boneio/core/manager/manager.py`.
2. Run `python tools/build_modules_payload.py --baseline <new-upstream-tag>` to verify our patches still apply cleanly post-merge.
3. `inv deploy` + `inv smoke`. If smoke fails → `inv rollback`.

Detailed merge runbook lives in `WORK_LOG.md` ("How to handle the next upstream merge — practical runbook").

## What is NOT in this file

- **Plain ops architecture / why we picked Invoke over Ansible** → tasks.py docstring.
- **Backend module design / what each module does** → WORK_LOG.md.
- **Frontend component conventions** → CLAUDE.md.
- **The deprecated bash deploy** (`deploy_backend.sh`) — kept for now as a fallback but the next person to touch it must delete it.
