# Migration Inspection Report — fork → upstream v1.5.0dev3+

**Generated**: 2026-06-23
**Author**: Claude (Opus 4.7) inspection pass, no code modified
**Scope**: Should we migrate `feat/expansion-board` to current `origin/dev-debian13` (v1.5.0dev3+)?

> This is a **read-only** report. No code was changed during its production.
> Use it to decide which of our commits to **keep, drop, or merge** before
> executing the actual merge.

---

## TL;DR

- **Upstream advanced 81 commits** from our merge-base (`8f1a21c` — v1.4.0dev4) to current `origin/dev-debian13` HEAD (`f2dd41a` — v1.5.0dev3 + 4 more dev commits).
- **We're 43 commits ahead** with: expander (flagship), `modules/remote_mqtt/` (MQTT scan + Jinja2 layer on top of upstream's `remote_*`), OLED hardening, USB-RS485 dongle support, ops tooling.
- **34 files touched on both sides** (probable conflict set).
- **Recommendation**: merge is **doable** but non-trivial. None of our work is *obsoleted* by upstream — most is purely additive. Main pain points: schema files, React 19 frontend bump, OLED 2-line fix to port.
- **Suggested execution path**: §6 below — phased merge, no big-bang.

---

## 1. Upstream changes that matter to us

Relevant new features in v1.4.x → v1.5.0dev3+ (not exhaustive, only items that
intersect our work or our deployment):

| Upstream | What | Touches our work? |
|---|---|---|
| **Remote Devices subsystem** (`v1.4.0`+) | ESPHome/MQTT/WLED/CAN drivers, `RemoteDeviceForm`, `RemoteOutputForm`, `RemoteInputForm`, `remote_devices.yaml` + `remote_outputs.yaml` + `remote_inputs.yaml` schemas | **Yes — same files our `modules/remote_mqtt/` extends.** Conflicts inevitable but composable: our module is a *layer on top*, not a replacement. |
| **OLED FIFO permissions migration** `v1_5_0` | Migration ensures correct perms on OLED message FIFO | Independent. Add to our deploy flow. |
| **`boneio-oled-shutdown.service`** (v1.4.3) | Display "Safe to unplug" after network is down on shutdown | Independent. Adopt. |
| **OLED 2-line fix** (`533b9ea`) | `if not self._cancel_sleep_handle and ...` → drops the condition (always restart sleep timer if timeout > 0) | **Same file as our 384-line rewrite** — must port manually. |
| **React 19 / Vite 8 / Tailwind 4.3 / DaisyUI 5.5** (`v1.5.0dev2`) | Major frontend dep bump | **All our 16 frontend modules** must recompile against new APIs. |
| **HA Dashboard Export Wizard** (`v1.5.0dev1`) | Multi-step wizard for Lovelace YAML | Independent. Don't need to integrate but it's new tooling. |
| **System sensors CPU/Disk/Memory + sensor attributes in WS initial states** | Disk/Mem/CPU as % sensors, instant load via WS | Independent. |
| **Template subsystem** (thermostat, alarm panel) | New entity types | Independent — but could replace some `remote_mqtt` usage if you're using it for thermostat-like devices. |
| **Modbus**: `nicer modbus setup experience` (`d4e25b4`) | UI/schema improvements | **Conflicts with our `af4bf08` USB-RS485 schema change** on `boneio/schema/schema.yaml`. |
| **Irrigation**: full overhaul + `start/full_stop` lifecycle fix in `v1.5.0dev3` | Critical irrigation scheduler bugs fixed | Independent. |
| **Cover state retain on MQTT broker restart** (`v1.5.0dev3`) | `retain=True` on cover state/position | Independent. |

---

## 2. Our 43 commits — per-commit verdict

Legend: **KEEP** = pure addition, must survive merge as-is. **MERGE** = both sides
touched same region, manual reconciliation needed. **DROP** = upstream now ships
equivalent that's strictly better; we can delete ours. **DEFER** = decision after
merge surfaces actual conflicts.

### 2.1 Expander (flagship — KEEP all)

| SHA | Subject | Verdict |
|---|---|---|
| `4813cdd` | feat(backend): expansion board endpoints + split-write for !include_files | **KEEP** |
| `1522879` | feat(ui): expansion board management in BoneIO settings | **KEEP** |
| `2a147b9` | feat(ui): unified OutputForm for board + expander outputs | **KEEP** |
| `913f2ee` | fix(ui): polish settings UX | **KEEP** |
| `fab2519` | chore: expander translation keys + ignore deploy script | **KEEP** |
| `96d79b0` | refactor(expander): scaffold modules/expander/ + move helpers | **KEEP** |
| `4fe90a0` | refactor(expander): scaffold boneio/modules/expander/ backend + slim upstream | **KEEP** |
| `d2d6d1e` | refactor(expander): extract useExpanderManager + <ExpanderManager /> | **KEEP** |
| `a6755ae` | refactor(expander): extract useMcpHardware + <McpHardwareFields /> | **KEEP** |
| `bad59e3` | refactor(expander): extract OutputAddButton + derive outputKind via hook | **KEEP** |
| `2eadc44` | refactor(expander): dedupe Mcp23017Form constants + OutputTable EX_ check | **KEEP** |

**Rationale**: upstream has zero MCP23017 expander logic. Pure addition, no overlap.

### 2.2 remote_mqtt (KEEP all — it's an EXTENSION of upstream's `remote_*`, not a parallel)

| SHA | Subject | Verdict |
|---|---|---|
| `bec28bb` | feat(remote_mqtt): scaffold modules/remote_mqtt foundation | **KEEP** |
| `95c1b16` | feat(remote_mqtt): MQTT topic scanner + POST /api/mqtt/scan endpoint | **KEEP** |
| `3c20007` | feat(remote_mqtt): MqttScanDialog + Scan broker button in RemoteDeviceForm | **KEEP** |
| `4ffc39b` | feat(remote_mqtt): Jinja2 template engine + JSON inspector with live preview | **KEEP** |
| `0ec5d61` | feat(remote_mqtt): MQTTGenericInput — wire generic MQTT topics into InputManager | **KEEP** |
| `c1ba5b9` | feat(remote_mqtt): MQTTGenericOutput — publish commands to arbitrary MQTT topics | **KEEP** |
| `0d57bd3` | feat(remote_mqtt): topic+template form fields for remote inputs/outputs | **KEEP** |
| `1d3140f` | fix(remote_mqtt): MqttTopicDispatcher — multi-subscriber per topic + scan-safe | **KEEP** |
| `c0ceb22` | refactor(remote_mqtt): pivot to device-centric ESPHome-style pattern | **KEEP** |
| `437ebd8` | polish(remote_mqtt): id uniqueness + translations + WORK_LOG pivot rationale | **KEEP** |
| `03fa8a3` | fix(remote_mqtt): generic devices in Remote Outputs dropdown + output command_template + input diagnostics | **KEEP** |
| `91b89a5` | refactor(remote_mqtt): isolate full MQTT remote stack into modules/remote_mqtt/ | **KEEP** |
| `f308b2e` | feat(remote-mqtt + navigation + ui): MqttDeviceEntitiesEditor improvements, …, locales | **KEEP** |
| `401eb65` | ui(modules): visual consistency pass — drop dead scan dialog, promote browse CTA | **KEEP** |
| `c874e45` | refactor(registry): replace hardcoded remote_mqtt imports in core with ModuleRegistry hooks | **KEEP** |

**Critical finding**: Upstream's `remote_*` subsystem (ESPHome/MQTT/WLED/CAN
drivers) already existed at our **merge-base v1.4.0dev4**. Our `modules/remote_mqtt/`
was built *on top of* that — it adds: MQTT topic scanner, Jinja2 template engine
for arbitrary topic payloads (ROPAM `n64/88/temp1 = {"val": 6.5, ...}`-style),
generic MQTT inputs/outputs, multi-subscriber dispatcher. Upstream's later
remote_* changes (WLED, brightness, interlock, republish on reconnect) are
**complementary** — they don't replace what we built.

**Verdict**: all 15 commits KEEP. Merge mechanics will be the work.

### 2.3 OLED hardening (KEEP all + port their 2-line fix)

| SHA | Subject | Verdict |
|---|---|---|
| `0b04e8f` | fix(display): kill i2c race on OLED — lock, retry, handoff before first draw | **KEEP** |
| `3bb43c3` | fix(display): more retries + clear-before-paint + soft-fail first frame | **KEEP** |
| `a46e564` | fix(display): kill "second click clears" ghost-pixel bug + harden sleep callback | **KEEP** |
| `9244c6d` | fix(display): harden init_early_oled with retry+backoff + visible logs | **KEEP** |
| `ff26393` | fix(display): widen _safe_draw budget + retry clear_display + deferred re-paint | **KEEP** |

Upstream `oled.py` is 675 lines; ours is 907 lines (mostly retry/lock/timing
hardening). Upstream's only OLED touch since merge-base is `533b9ea` (2-line
change at `oled.py:541` removing `not self._cancel_sleep_handle` condition).
**Port that one line manually** during merge; our hardening stays.

Also note: upstream now ships `boneio-oled-shutdown.service` (v1.4.3) and
`v1_5_0_fix_oled_fifo_permissions` migration. Both are independent infrastructure
we should adopt (deploy script + migration runner) — no code conflict.

### 2.4 USB-RS485 dongle support (KEEP — and consider upstreaming)

| SHA | Subject | Verdict |
|---|---|---|
| `3d52d45` | feat(modbus): add USB-RS485 dongle support (ttyUSB0/1, ttyACM0) to UART list | **KEEP** |
| `af4bf08` | fix(modbus): extend Cerberus schema allowed UARTs to include USB-RS485 paths | **KEEP** |

Upstream still has `allowed: ['uart1', 'uart2', 'uart3', 'uart4', 'uart5']` in
`boneio/schema/schema.yaml` — our USB-RS485 paths are **not in upstream**.
Will conflict with upstream's `d4e25b4` "nicer modbus setup experience" on
the same UART block. After this merge, **strong candidate to PR upstream** so
we don't carry it forever.

### 2.5 Ops / tools / docs (KEEP all)

| SHA | Subject | Verdict |
|---|---|---|
| `c97fe9d` | ops(deploy): replace bash deploy with Invoke + secrets via keyring/env | **KEEP** |
| `514b58c` | tools: POC build/inject system — payload + applier for clean upstream merges | **KEEP** |
| `869b32e` | docs: add WORK_LOG.md | **KEEP** |
| `431c2a9`, `6d76247`, `1613569`, `30aee66`, `c5b468c` | WORK_LOG updates | **KEEP** |

### 2.6 Past merge commits (no action needed)

| SHA | Subject |
|---|---|
| `fbe2140` | Merge upstream v1.4.0dev2 | Historical, irrelevant after new merge |
| `ce3d42a` | Merge upstream v1.4.0dev4 | Historical, irrelevant after new merge |

---

## 3. Conflict heatmap — 34 shared files, ranked by impact

Total touched: ours = 216 files, theirs = 153 files, intersection = 34 files
(diff lines counted = added+removed since merge-base).

| File | Ours Δ | Theirs Δ | Type | Strategy |
|---|---:|---:|---|---|
| `boneio/webui/schema/config.schema.json` | 1480 | 1209 | Aggregate JSON Schema | Likely auto-aggregated from sub-schemas; **regenerate after merge** if there's a build step. Otherwise: take upstream version + diff our additions back in (mostly module schemas). |
| `boneio/webui/schema/event.schema.json` | 391 | 391 | JSON Schema | Equal counts ≈ both probably copied/regenerated full file. Investigate — could be near-identical. |
| `boneio/hardware/display/oled.py` | 384 | 2 | Python | **Keep ours**, manually port `533b9ea` (sleep timer always-restart at line ~541). |
| `boneio/webui/schema/remote_devices.schema.json` | 229 | 1 | JSON Schema | Take ours (their 1 line is trivial; we extended it for MQTT scan). |
| `boneio/webui/schema/remote_outputs.schema.json` | 228 | 226 | JSON Schema | **Real overlap**. Both extended their schema heavily. Careful 3-way merge. |
| `frontend/src/locales/{pl,en}/common.json` | 202 each | 211 each | i18n JSON | Translation keys are mergeable by key — write a merge script if many conflicts (or sort+manual). |
| `boneio/webui/schema/remote_inputs.schema.json` | 197 | 197 | JSON Schema | **Real overlap**. Same as remote_outputs. |
| `boneio/webui/schema/binary_sensor.schema.json` | 131 | 131 | JSON Schema | Investigate — equal counts. |
| `boneio/core/config/yaml_util.py` | 145 | 55 | Python | **Significant code merge**. |
| `frontend/src/components/OutputsView.tsx` | 81 | 8 | TSX | Their 8 likely small fix; our 81 = expander/remote_mqtt integration. Take ours + verify their fix. |
| `boneio/webui/schema/lox_udp.schema.json` | 64 | 64 | JSON Schema | Investigate. |
| `frontend/src/components/InputsView.tsx` | 59 | 14 | TSX | Take ours + verify theirs. |
| `frontend/src/components/UISettings/UISettings.tsx` | 58 | 3 | TSX | Take ours (we register modules); their 3 lines likely a small tweak. |
| `frontend/src/components/UISettings/ArrayTableWidget.tsx` | 43 | 52 | TSX | **Real overlap**. |
| `boneio/core/manager/manager.py` | 32 | 70 | Python | **Real overlap** — their irrigation/sensors/template changes vs our ModuleRegistry hooks. Tricky. |
| `frontend/src/components/UISettings/RemoteInputForm.tsx` | 32 | 4 | TSX | Take ours. |
| `boneio/webui/routes/config.py` | 31 | 7 | Python | Take ours. |
| `boneio/webui/schema/mqtt.schema.json` | 22 | 22 | JSON Schema | Investigate. |
| `boneio/webui/schema/cover.schema.json` | 22 | 22 | JSON Schema | Investigate. |
| `boneio/webui/schema/template.schema.json` | 18 | 27 | JSON Schema | Take theirs (new feature for them; our changes were probably structural). |
| `boneio/webui/schema/irrigation.schema.json` | 18 | 27 | JSON Schema | Take theirs (they overhauled irrigation). |
| `frontend/src/components/SensorView.tsx` | 15 | 1 | TSX | Take ours. |
| `boneio/core/config/schema_converter.py` | 14 | 5 | Python | Take ours + verify. |
| `frontend/src/hooks/useWebSocket.ts` | 13 | 1 | TS | Take ours. |
| `frontend/src/components/UISettings/tables/OutputTable.tsx` | 13 | 2 | TSX | Take ours. |
| `boneio/webui/app.py` | 6 | 28 | Python | Take theirs + replay our 2 lines (ModuleRegistry registration). |
| `boneio/schema/schema.yaml` | 5 | 47 | YAML | **Overlap on `uart:` allowed list**. Take theirs + add our USB paths. |
| `boneio/schema/remote_outputs.yaml` | 5 | 7 | YAML | Small overlap. Merge by hand. |
| `frontend/src/components/UISettings/components/TableRenderer.tsx` | 3 | 4 | TSX | Tiny — merge by hand. |
| `boneio/core/manager/sensors.py` | 3 | 51 | Python | Take theirs (they did system sensors); replay our 3 lines. |
| `frontend/vite.config.ts` | 2 | 20 | Build config | Take theirs (React 19 / Vite 8 changes); replay our 2 lines if related to modules. |
| `boneio/webui/schema/modbus_devices.schema.json` | 2 | 15 | JSON Schema | Take theirs. |
| `pyproject.toml` | 1 | 1 | Build config | Trivial. |

**Pattern observed**: most of our changes are *additive* (new module wiring,
new schema fields). Most of upstream's changes are *also additive* (new features
in different domains). The "real overlap" zone is essentially:
1. `remote_outputs/remote_inputs.schema.json` (we both edit the remote subsystem)
2. `schema.yaml` modbus uart block
3. `yaml_util.py`, `manager.py`, `ArrayTableWidget.tsx` (small genuine overlap)

The rest is regenerable / take-one-side.

---

## 4. Hard risks (not file-level, system-level)

1. **React 19 + Vite 8 + Tailwind 4.3 + DaisyUI 5.5** (v1.5.0dev2): All 16 of
   our frontend modules need to recompile against new APIs. React 19 has subtle
   breaking changes (refs, JSX runtime, `use()` hook), and Tailwind 4 changed
   class scanning. **Plan a `npm install && npm run build` smoke pass right
   after merge** before touching anything else.
2. **Cerberus schema gate**: Our `af4bf08` was triggered by a real crash-loop
   when frontend schema and runtime YAML schema diverged. The "3-place schema
   sync" rule (`const.py` / `schema.yaml` / `*.schema.json`) is now even more
   important — upstream added more schema files and we have to keep all of them
   in sync. **Re-run smoke test #1 (config valid) after merge.**
3. **OLED FIFO permissions migration**: `v1_5_0_fix_oled_fifo_permissions` will
   run on first boot after upgrade — make sure it runs cleanly on the device.
   Recommend: read the migration code before deploy, then deploy with `systemctl
   status` watching for migration errors.
4. **ModuleRegistry vs upstream's direct imports**: `c874e45` replaced hardcoded
   `from boneio.modules.remote_mqtt import …` with a registry pattern. Upstream
   meanwhile added more direct hooks in `manager.py`. **Must reconcile** —
   probably extend our registry to cover what upstream now calls directly.
5. **Translations**: 200+ added keys each side in `en/pl/common.json`. Hand-merging
   200-key JSON files is error-prone. Suggest: write a small Python `dict-merge`
   script.

---

## 5. Recommended overlap decisions (with your override veto)

The user's instruction: *"jeżeli jakieś ficzerki się dublują to możemy
przestać używać naszej implementacji i spróbować korzystać z ich, no chyba że
poproszę Cię o przywrócenie naszej wersji"*.

Applying that rule:

| Our feature | Upstream equivalent? | Recommendation |
|---|---|---|
| `modules/expander/` (MCP23017) | None | **Keep ours** (no choice). |
| `modules/remote_mqtt/` (MQTT scan + Jinja2 + generic topic) | None — upstream's `remote_*` is ESPHome/WLED/CAN-centric; doesn't do MQTT topic scanning, doesn't do Jinja2 templating of arbitrary payloads | **Keep ours**. No overlap to drop. |
| OLED hardening (5 commits) | Upstream `533b9ea` (2-line fix) | **Keep ours**, port their 2 lines. (Reverse possible only if you want to drop OLED resilience.) |
| USB-RS485 dongle | None | **Keep ours**. PR candidate upstream. |
| ModuleRegistry pattern | None | **Keep ours**. Required for our `modules/` architecture. |
| Invoke-based deploy | None | **Keep ours**. |
| Build/inject tools POC | None | **Keep ours** (just our internal tooling). |
| WORK_LOG | None | **Keep ours**. |

**Bottom line**: there is **no commit where upstream now does the same thing
better**. The "drop ours, use theirs" path you offered doesn't apply on any
individual feature today. All of our 43 commits stay; the work is in
*merging* upstream's parallel additions in.

If at any point during the actual merge I find that one of our features now
mirrors something upstream does cleaner, I'll **ask before dropping**.

---

## 6. Suggested execution path

Three phases, each ends in a known-good state (revertable):

### Phase A — Pre-merge safety net (~10 min, no code changes)

1. Tag current HEAD: `git tag pre-v1.5-migration` for one-command rollback.
2. Push the tag to `fork` so it's recoverable from anywhere.
3. Confirm device backup of `/etc/boneio/config.yaml` and current YAML config
   pulled to `~/Documents/BoneIO/backups/` (in case migration mangles it).

### Phase B — Merge in a sandbox branch (~1–2 h)

1. `git checkout -b migrate/v1.5.0dev3 feat/expansion-board`
2. `git merge origin/dev-debian13` — let Git auto-merge what it can.
3. Resolve conflicts in this order (least painful first):
   1. `pyproject.toml` (trivial)
   2. `vite.config.ts` (take theirs, replay our deps)
   3. Locale JSON (dict-merge script)
   4. `schema.yaml` modbus block (take theirs, add USB paths)
   5. `manager.py`, `yaml_util.py`, `app.py` (real Python merge)
   6. Frontend conflict files in order: `UISettings.tsx` → `OutputsView/InputsView/SensorView` → `ArrayTableWidget`
   7. JSON Schema files: regenerate if possible, otherwise structural diff
   8. `oled.py`: keep ours, port 1-line change at `:541`
4. `npm install && npm run build` — smoke React 19 / Tailwind 4 / DaisyUI 5.5.
5. `python -m pytest tests/` — backend smoke.
6. Commit: `Merge upstream v1.5.0dev3 into feat/expansion-board`.

### Phase C — Device verification (~30 min)

1. `inv deploy` (now points to 192.168.1.7).
2. Watch journal: `journalctl -fu boneio.service` while it boots.
3. Verify:
   - Cerberus schema validation passes (no crash-loop)
   - OLED comes up (early + main)
   - Expander outputs show in UI
   - Remote MQTT scan still works (test ROPAM topic if accessible)
   - System sensors (CPU/Disk/Mem) appear (new upstream feature)
   - Irrigation schedules tick (if irrigation is configured on device)
   - HA dashboard export wizard opens (new feature, smoke only)

If Phase C fails: `git reset --hard pre-v1.5-migration` → diagnose → retry.

### Phase D — Follow-ups (post-merge, separate session)

1. PR upstream the USB-RS485 schema change.
2. Audit if upstream's template subsystem (thermostat/alarm) could replace any
   ROPAM remote_mqtt usage on your device — *only if it actually does the same
   thing*, otherwise leave alone.
3. Adopt `boneio-oled-shutdown.service` in deploy script.
4. Re-run the 3-place schema sync check (`const.py` / `schema.yaml` /
   `*.schema.json`) for the USB-RS485 paths — make sure upstream's schema
   overhaul didn't reset our work.

---

## 7. Decision points for the user

Before running Phase B, please confirm:

1. **Approval to merge** — green light to start Phase A/B?
2. **Test window for Phase C** — when is it OK to deploy to device for verification?
3. **Branch naming** — `migrate/v1.5.0dev3` OK or do you want a different name?
4. **Anything in this report you disagree with** — especially the "all 43
   commits KEEP" verdict. If you'd rather drop `remote_mqtt` entirely (e.g.
   because you no longer use ROPAM), say so now; merging will be faster.
