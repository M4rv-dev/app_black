# Work Log — BoneIO fork (M4rv-dev/app_black)

> **Read this first** when starting a new Claude Code session on this repo. It carries
> context that survives across sessions, model switches, and CLI restarts.

---

## Project overview

This is a **fork** of `boneIO-eu/app_black` maintained at `github.com/M4rv-dev/app_black`. The upstream
ships v1.4.0dev2; we extend it with the **expansion-board** feature (adding I²C MCP23017
expanders that double available outputs). The goal is to ship features upstream **doesn't have**,
while staying mergeable with their releases.

### Topology

| Remote | URL | Access |
|--------|-----|--------|
| `origin` | github.com/boneIO-eu/app_black | read-only (upstream) |
| `fork` | github.com/M4rv-dev/app_black | push (our fork) |

| Branch | Purpose |
|--------|---------|
| `dev-debian13` | Tracks upstream main; our base for merges |
| `feat/expansion-board` | Active feature branch (current) |

### Deployment

- **Target device**: BoneIO @ `192.168.1.22` (BeagleBone Debian 13, user `boneio`)
- **Deploy script**: `./deploy_backend.sh` (gitignored, contains password). Rsyncs the whole
  `boneio/` Python package to `/home/boneio/boneio/venv/lib/python3.13/site-packages/boneio/`,
  then restarts `boneio.service`.
- **Frontend**: Vite dev server at `localhost:5173` (proxies to device's API on `:8090` and
  Caddy/Node-RED on `:8091`). `.env.local` has `VITE_API_URL` + `VITE_NODERED_URL`.
- **Web UI on device**: direct Hypercorn on `:8090` OR via Caddy proxy on `:8091` (Caddy proxies
  BoneIO UI + provides Node-RED at `/nodered/`). For Node-RED tab to appear, use `:8091`.

---

## Architecture decisions

### Module pattern (CORE PRINCIPLE)

**BoneIO upstream is treated as core engine; our extensions live in dedicated `modules/` folders
with strict public APIs.** Touching upstream files is allowed only for 1 import + 1-2 use lines.

Why: BoneIO will keep releasing 1.4.x / 1.5; embedding logic in their files = merge conflicts
on every release. The module pattern keeps our merge surface minimal.

```
frontend/src/components/UISettings/modules/<feature>/
├── index.ts            ← public API — upstream imports only from here
├── components/         ← Presentational (sam render)
├── hooks/              ← stateful + side-effects + fetch
├── helpers/            ← pure functions
├── types/              ← TypeScript types
└── constants/

boneio/modules/<feature>/
├── __init__.py         ← public API
├── yaml_util.py        ← pure helpers
└── routes.py           ← endpoints + register_routes(app)
```

### Future re-skin (NOT in current scope)

A future project will provide an alternative UI as a **wrapper layer** over both boneIO
components AND our modules — written as additional modules, never modifying existing code.
Our modules MUST keep logic in hooks/helpers (not in components) so the re-skin can swap
components without touching logic.

### Memory & plans

- **Memory dir**: `~/.claude/projects/-Users-mariuszskupinski-Documents-BoneIO-app-black/memory/`
  (`MEMORY.md` index auto-loaded by Claude)
- **Active plan**: `~/.claude/plans/boardy-s-takie-jakie-starry-sun.md` (the modules refactor)

---

## Active scope

**Current task**: Upstream v1.5.0dev3+ merged into `migrate/v1.5.0dev3`, deployed and verified.
Next: decide whether to merge `migrate/v1.5.0dev3` back into `feat/expansion-board`, plus
follow-ups from §Phase D of `MIGRATION_REPORT.md` (USB-RS485 upstream PR, OLED shutdown
service adoption, schema 3-place sync re-check).

**Earlier task** (completed): Refactor expansion-board feature into `modules/expander/` pattern.

**Why**: After merging upstream v1.4.0dev2 (commit `fbe2140`), audit revealed our code is scattered
across 7+ upstream files. Each future upstream release will conflict on the same spots. Module
pattern eliminates that.

**Phase status** (granular commits, easy to revert each):

| # | Phase | Status |
|---|-------|--------|
| 0a | Scaffold modules/expander/ + types + constants + index.ts | ✅ |
| 0b | Move expanderBoards + outputMcpUtils into module; add isExpanderOutput + getOutputStats; shim old paths | ✅ |
| 0c | Backend scaffold `boneio/modules/expander/` + yaml_util.py + routes.py + register in app.py | ✅ |
| A1 | Extract `useExpanderManager` + `<ExpanderManager />` from `BoneIOForm.tsx` | ✅ |
| A2 | Extract `useMcpHardware` + `<McpHardwareFields />` from `OutputForm.tsx` | ✅ |
| A3 | Extract `useOutputCapacity` + `<OutputAddButton />` from `ArrayTableWidget.tsx` | ✅ |
| A4 | Derive `outputKind` via `useOutputKind` (drop useState) | ✅ |
| B | Dedupe EX_ detection, MCP addresses, remove dead `onExpanderAdded` prop | ✅ |
| — | Verify (tsc + build + python smoke + anti-duplicate greps) | ✅ |
| — | Deploy + manual smoke test in UI | ✅ deployed; UI smoke test confirmed working by user |
| Future | Build/inject script POC (auto-apply modules onto fresh upstream) | 📋 idea, deferred |

---

## Timeline

### 2026-07-21 — Session 7 (upstream v1.5.0dev3 → v1.5.0dev17 migration)

**Zgłoszenie**: użytkownik — "BoneIO dodało nowy update. Potrzebujemy podnieść nasz
core do tej wersji i podłączyć wszystkie nasze aktualne moduły. Dodatkowo powinniśmy
przetestować czy zmiany, które wprowadziło BoneIO nie wpłyną na nasze rozwiązania."
W trakcie sesji dwa dodatkowe wątki: (a) pytanie o output-group toggle bug, (b) obawa
o zachowanie istniejących urządzeń (ROPAM) przy migracji configu.

**Stan na wejściu**:
- Merge-base `f2dd41a` (v1.5.0dev3). Upstream `3b9c664` (v1.5.0dev17) — **+107 commitów**,
  204 pliki, +19.6k/−9.9k. My +55 commitów.
- Upstream big-ticket: config.py split na 5 modułów (`config_core/actions/backups/
  discovery/files`), Teach Mode, Binding Matrix, Quick Action Sheet,
  SearchableEntityPicker, NumericInput, EntityCard/EntityGrid refactor, board v1.0
  (DS2482/buzzer), WLED cache (config_version 4), combined /api/init + AppInitContext,
  MQTT Reference dialog, 2 migracje runtime (config v4, system 1.5.1 UFW).

**Audyt parytetu (Explore agent) — kluczowa decyzja keep/retire**:
- **expander enricher → KEEP na stałe**. Upstream `78b9a2c` uczy OutputGroupForm
  akceptować remote outputs natywnie (`remote_source && device_id`), ale expander
  outputs mają `kind: mcp` BEZ `remote_source` → przepadają w obu gałęziach natywnego
  filtra. Bez naszego `boneio_output` niewidoczne. Upstream nie ma planu wsparcia MCP.
  User potwierdził: BoneIO wycofało expansion board z oferty (kanibalizacja sprzedaży)
  → expander module jest **permanentny** (memory: [[project_expander_permanent]]).
- **remote_mqtt enricher → RETIRED** (decyzja usera "retire od razu"). Upstream `78b9a2c`
  pokrywa remote_outputs natywnie. Usunięto `enrich_config_response`+`strip_for_save`
  z `remote_mqtt/manager_integration.py`.

**Wykonano (Faza 0→E)**:

- ✅ **Faza 0**: tag `pre-v1.5.0dev17-migration` push do fork; commit Session-6d WORK_LOG.
  (Lokalny runtime-backup przez `inv backup` padł — macOS rsync 2.6.9 nie zna
  `--ignore-missing-args`; nieblokujące, bo deploy robi device-side snapshot +
  nie dotyka config.yaml.)
- ✅ **Faza A**: branch `migrate/v1.5.0dev17`, merge `origin/dev-debian13`. **20 konfliktów**
  (4 backend + 16 frontend) rozwiązane wzorcem „zachowaj oba":
  - `config.py` → theirs (shim); enrich/strip przeniesione do `config_core.py`.
  - `yaml_util.py` → nasza logika split-write expandera (board vs EX_* files).
  - `schema_converter.py` → nasz `_get_schema()` (modbus + module extensions).
  - `manager.py` → nasz `try_setup_output` hook + upstreamowy brightness detect (oba).
  - `RemoteOutputForm` → nasze MQTT outputs + upstreamowe WLED segments (oba dropdown).
  - `OutputForm` → nasz `McpHardwareFields` + upstreamowy `SettingsToggleGroup`.
  - `ArrayTableWidget` → nasz inline FormRenderer (threading outputKind+mcp23017);
    NIE adoptowano upstreamowego `EditItemDialog` bo nie forwarduje expander props.
  - `InputsView`/`OutputsView` → upstreamowy EntityCard/EntityGrid/Teach Mode refactor
    + wpięty NASZ search bar (iteruje `filtered*` zamiast `localInputs`/`items`).
  - `EntityCard` (rename z OutputItem), `SensorView` (skeleton+grouped), `App.tsx`
    (AppInitProvider + nasz ToastContainer/ErrorBoundary), locales (unia), select/index.css.
- ✅ **Faza B**: expander enrich/strip re-wired do `config_core.get_parsed_config` (GET) +
  `update_section_content` (PUT); `app.py` cache pre-population hook (L715) intact.
  remote_mqtt enricher usunięty.
- ✅ **Faza C**: `npm run build` zielony (tsc -b + vite, React 19). Post-merge build fixy:
  ArrayTableWidget Dialog importy (upstream je usunął przy EditItemDialog); App.tsx
  4 duplikaty importów (upstream lazy-loaduje). py_compile 66 plików OK. Import smoke:
  expander callable, remote_mqtt retired. **3-place schema sync (USB-RS485) intact**.
- ✅ **Faza D**: `inv deploy` (snapshot `boneio_prev_20260720T232349Z`). **Smoke PASSED**:
  service active, HTTP :8090/:8091 = 200, `/api/version` = **1.5.0dev17**, WebSocket ok,
  log scan clean. Post-restart veryfikacja: 5 remote outputs (ROPAM out5/out6 + reszta),
  4 MCP, expander screens, ROPAM temp sensor 13.5°C — **wszystkie urządzenia przetrwały**.

**Config migration — v4_wled_cache błąd → NAPRAWIONY (commit `d3545bb`)**:
Migracja `v4_wled_cache` rzucała `Failed to strip WLED cache fields: could not determine
a constructor for the tag '!include_files'` — jej `IncludeLoader` rejestrował tylko
konstruktor `!include`, nie NASZ `!include_files` (split-write expandera dla `output:`).
Strip padał i był łapany → **config.yaml nietknięty**, ale `config_version` bumpnięty do 4.
**Fix**: dodano konstruktor `!include_files` (mirror `yaml_util.IncludeLoader`) + obsługę
remote_devices w obu formach include. Zweryfikowane: loader parsuje oba tagi. Deploy +
smoke OK; nowy boot (PID 26324) czysty, bez błędu v4 (config_version=4 → skip). Uwaga:
prawdziwym stripperem WLED przy dodawaniu urządzeń jest ścieżka ZAPISU
(`yaml_util.update_config_section:1319`, ma własny IncludeLoader), więc live-adds WLED
były zawsze obsłużone; fix migracji to poprawność dla fresh install / legacy inline-WLED.

**Odpowiedź na pytanie o output-group toggle** (osobny wątek, bez zmian w kodzie):
Upstream toggluje grupę jako całość (`async_turn_off` = wszystkie OFF). Objaw usera
(1/3 zapalony → toggle → pozostałe 2 się zapalają) to symptom `all_on_behaviour: True`
+ akcja TOGGLE: grupa uznana OFF (bo nie wszystkie ON) → toggle robi turn_on all. Fix
configowy: `all_on_behaviour: False` (domyślne, any-on) LUB akcja `OFF` zamiast TOGGLE.

**Follow-upy — ZROBIONE (commit `<follow-ups>`)**:
- ✅ **OutputForm** advancedTabContent: zaadoptowano upstreamowy zero-clearing UX na
  momentary_turn_on/off + `SettingsToggleGroup` dla adjustable_duration (disabled +
  conflict warning gdy momentary ustawione).
- ✅ **EditItemDialog adopcja**: dodano optional `outputKind`+`mcp23017` do EditItemDialog
  (forward do FormRenderer); ArrayTableWidget przełączony z inline `<Dialog>` na
  `<EditItemDialog>` (usunięta nasza dywergencja — EditItemDialog ma identyczny
  boneio_output title); BindingMatrix output-edit wpięty (outputKind via useOutputKind +
  mcp23017 z formData) → edycja wyjść expandera z macierzy pokazuje pola MCP.
- ✅ **API picker smoke** (substytut manual UI): GET /api/config → **64 expander outputs
  wszystkie enriched `boneio_output`** (native filter branch), **5 remote outputs 0×
  boneio_output** (native `remote_source && device_id` branch) = 69 w pickerze; modbus.uart
  = `/dev/ttyUSB0`. Deploy + smoke OK.

**Pending (kosmetyczne, do usera)**:
- Manual UI klik: output-group picker (69 wyjść widoczne), Teach Mode, OLED, BindingMatrix
  edycja expandera pokazuje MCP fields.
- Session 6 §Phase D: USB-RS485 upstream PR, itd. (starsze, poza scope).

---

### 2026-06-24 — Session 6 part D (output-groups dropdown + zasada upstream-friendliness)

**Zgłoszenia (w kolejności napływania)**:
1. "w ustawieniach w sekcji modbus system nie wskazuje mojego obecnego portu uart"
2. "w ustawieniach mogę zdefiniować grupy wyjść ale nie widzę tam na liście
   urządzeń z poza boneio. fajnie jakby były tam też urządzenia spoza płytki
   jak np expansion board + wyjścia zdefiniowane w 'zdalnych wyjściach'"
3. "może lepiej nie przerabiać samych output groups tylko da się dodać do
   yamla gdzie są zdefiniowane remote i expansion output jakąś flagę lub
   parametr który pozwoli bez zmian w output group form widzieć te wyjścia?"
4. "niech to będzie nasza główna zasada przy zmianach żeby zachowywać upstream
   jak najbardziej nienaruszony, i ogólnie być upstream-freandly przy każdym
   działaniu."
5. "i zasada, że jeżeli upstream zawiera w którejkolwiek wersji feature
   podobny do naszego musimy każdy taki przypadek głęboko zanalizować… po
   utwierdzeniu się że to działa podobnie lub akceptujemy różnice wtedy
   odłączamy nasz moduł na zawsze i zaczynamy korzystać z tego upstreamowego."

**Wykonano**:

- ✅ **Modbus dropdown** (commit `0c5a021`, frontend-only): `ModbusForm.tsx:24`
  miał `toLowerCase()` które łamało `/dev/ttyUSB0` (Linux paths są
  case-sensitive — `'/dev/ttyusb0'` nie matchował żadnego `<option value>`).
  Fix: lowercase tylko stringi, które NIE zaczynają się od `/dev/`, żeby
  zachować legacy `"UART4" → "uart4"` matching dla starych configów.
- ✅ **Output Groups picker** (commits `0fbf3e6` → revert `c59c53b` → final
  `b07a3ab`/`bdf32fa`/`0a72591`): podejście ewoluowało przez 4 iteracje:
  1. Pierwszy podejście (frontend filter) — zostało revertem cofnięte po
     user's preferencji "lepiej w YAML/danych zamiast formularza".
  2. Final approach: nowy hook **`enrich_config_response`** + **`strip_for_save`**
     w `ModuleRegistry` (nasz `boneio/modules/_registry.py`). Każdy moduł
     dostaje szansę dodać derived fields do GET /api/config response i
     usunąć je przed PUT save do YAML — round-trip clean, user's YAML
     nigdy nie dostaje śmieci.
  3. `expander/__init__.py`: enricher wstrzykuje `boneio_output = id` dla
     entries `output:` które mają `kind: mcp` + `is_expander_output()` + brak
     `boneio_output`. Stripper idempotentnie usuwa pole tylko gdy wciąż
     pasuje do `id`.
  4. `remote_mqtt/manager_integration.py`: enricher wstrzykuje
     `boneio_output = f"{device_id}_{output_id}"` dla CAŁEJ sekcji
     `remote_outputs:` (niezależnie od `remote_source` — mqtt/esphome/wled/can).
     Lokalizacja w `manager_integration.py` (nie `__init__.py`) bo ten
     sub-moduł rejestruje się w `ModuleRegistry`, nie top-level package.
  5. Upstream touch: **`boneio/webui/routes/config.py`** — 4 linijki
     (2 import + 2 dispatcher calls). **`boneio/webui/app.py`** — 3 linijki
     (1 import + 2 lines) w bloku `if initial_config is not None:` żeby
     wzbogacić pre-populated cache też (root cause czemu prvious naprawa
     wydawała się "nie działać": `Config cache pre-populated from
     initial_config` ścieżka omijała endpoint handler).

**Architekturalne pułapki napotkane**:

- **Cache pre-population gap**: `webui/app.py:700-708` pre-populuje
  `_config_cache` przy starcie aplikacji z `initial_config`. To znaczy że
  PIERWSZY i KAŻDY następny GET /api/config trafia w cache hit i NIGDY nie
  uruchamia kodu w endpoint handler'ze. Dodanie enrichera tylko w endpoint
  handler'ze było **no-op w praktyce**. Każdy hook który modyfikuje
  response na ścieżce GET musi też być wpięty w pre-population.
- **`is_expander_output()` API gotcha**: funkcja oczekuje DICT (entry),
  nie ID string'a. Wywołanie z `entry_id` (string) rzucało `AttributeError`,
  który był łapany silently przez `_LOGGER.exception` w
  `ModuleRegistry.enrich_config_response` dispatcher'ze — efekt: enricher
  wywoływany, kod silentnie failuje, journal pusty (bo logger.exception
  na DEBUG level dla `boneio.modules._registry`). One-character fix.
- **Logger level w testach poza service'em**: `boneio.modules.*` ma
  effective level WARNING w izolowanym `python3` REPL (bo configurator
  loggerów `boneio.core.utils.logger` jest aktywowany tylko podczas startu
  service'u). To utrudniało diagnostykę przez ssh debug.
- **Sub-module vs top-level rejestracja w ModuleRegistry**: `expander`
  rejestruje `boneio.modules.expander` (top-level), `remote_mqtt` rejestruje
  `boneio.modules.remote_mqtt.manager_integration` (sub-module). Hook
  attributes muszą siedzieć na zarejestrowanym object'cie. Albo zunifikuj
  rejestrację, albo pamiętaj że dla `remote_mqtt` hooks muszą iść do
  `manager_integration.py`. Wybrane: zostawić jak jest.

**Architekturalne zasady utrwalone do memory** (`feedback_module_pattern.md`):

- **Session 6c — upstream-friendly nawet dla bug fixów**: przed *każdą*
  edycją upstream'owego pliku ask "czy ModuleRegistry hook + helper na
  module side mógłby to zrobić?". Acceptable touch: 1 import + 1 call site
  delegujący do ModuleRegistry / module API.
- **Session 6d — upstream feature parity audit**: gdy upstream w jakiejś
  wersji dodaje feature podobny do naszego, **głęboko zanalizować** czy
  zachowania są identyczne lub akceptujemy różnice, i jeśli tak —
  **retire'ować nasz moduł permanently** przez gut do shim re-exportującego
  upstream'owe API. Nie utrzymywać dual implementations.

**Wynik użytkownika** (potwierdzony "wszystko działa"):
- Modbus dropdown pokazuje `/dev/ttyUSB0 (USB-RS485 dongle)` jako wybrany.
- Output Groups → Member outputs picker: 69 outputów (32 board + 32 expansion
  + 5 remote, minus cover'y). Wcześniej: 32 (tylko board).
- YAML user'a nietknięty — round-trip GET → edit → PUT nie wstrzykuje
  `boneio_output` do plików `expansion_board_output_*.yaml` ani do sekcji
  `remote_outputs:`.

**Commits** (na `migrate/v1.5.0dev3`):
- `0c5a021` — fix(modbus-ui): preserve case on /dev/tty… UART paths
- `0fbf3e6` — fix(output-groups): include exp+remote… [REVERTED przez `c59c53b`]
- `c59c53b` — Revert (zmiana podejścia na YAML/dane side)
- `b07a3ab` — fix(remote_mqtt): relocate enrich/strip hooks to manager_integration
- `bdf32fa` — fix(expander): pass dict (not id string) to is_expander_output
- `0a72591` — fix(module-registry): also enrich the pre-populated config cache
- (+ feat(module-registry) commit z hookami + enricherami)

---

### 2026-06-23 — Session 6 part B (i2c-hardening po migracji)

**Zgłoszenie**: użytkownik — "mcp_left (0x21): [Errno 110] Connection timed out
+ 16 outputs Expander not available", a chwilę później "OLED Display (0x3c):
I2C device not found on address: 0x3C / Nie udało się zainicjalizować
expanderów sprzętowych. Sprawdź adresy I2C w konfiguracji MCP23017/PCF8575/
PCA9685".

**Diagnostyka**:

1. `git log` na `boneio/hardware/gpio/expanders/`, `boneio/components/mcp23017`,
   `boneio/core/manager/outputs.py` od merge-base do upstream HEAD **był pusty**
   → kod, który zawiódł, jest identyczny jak przed migracją. **Nie regresja.**
2. 3 z 4 MCP wstały (0x20, 0x22, 0x23), tylko 0x21 padł. Typowa cecha bus
   arbitration loss, nie strukturalnego buga.
3. W tej samej minucie ten sam errno 110 zadławił też OLED i2c — wspólne
   źródło: gorąca magistrala podczas startupu (gdzie LM75, INA219, OLED,
   sibling MCPs równolegle sondują bus).
4. 3 nowe migracje runtime v1.5.0dev3 (1.4.3, 1.4.4, 1.5.0) używały
   sudo + systemctl podczas startupu, przedłużając warm-bus window do
   ~5s → race trafiał regularnie.
5. `inv restart` (bus stygnie ~7s) → 0x21 wstało **jako pierwsze z 4 MCP**.
   Potwierdziło transient race, nie hardware fault.
6. **Druga sprawa, po restarcie**: `ERROR Unexpected error configuring OLED:
   I2C device not found on address: 0x3C`. Diagnostyka:
   - `luma.core.error.DeviceNotFoundError` MRO: `Error → Exception →
     BaseException`. **Nie jest podtypem OSError.**
   - Nasz soft-fail handler w `display.py:215` (z commitu `3bb43c3`) łapał
     tylko `OSError` → na gorącym busie `DeviceNotFoundError` spadał do
     generic `except Exception`, logował "Unexpected error" i wpychał do
     `_hardware_errors` → UI renderował generyczny banner
     "MCP23017/PCF8575/PCA9685" mimo że źródłem był OLED 0x3C.

**Wykonano** (commit `3a9788b` "fix(i2c-hardening)"):

- ✅ **`display.py`**: Dodano `DeviceNotFoundError` do tuple soft-fail
  handler'a obok `OSError`. Pierwsza klatka OLED na hot bus → soft-fail
  WARNING (nie ERROR), periodic refresh odtwarza. Banner nie pokazuje się.
- ✅ **`mcp23017.py`**: 10-attempt retry + linear backoff 0.2s→2.0s
  na `__init__`, 1:1 mirror `early_oled.py` z `9244c6d`. Bus lock acquired
  per-attempt, sleep poza lockiem (siblings mogą sondować podczas backoff).
  Sukces po retry → INFO "Initialized MCP23017 at address 0x{X} after N
  retries". Terminal fail → WARNING + raise.

**Weryfikacja (deploy o `00:39:08`, BoneIO 1.5.0dev4)**:

| Sygnał | Stan |
|---|---|
| Early OLED initialized after 1 retries | ✅ (early_oled retry działa) |
| 4 MCP wstały (0x21, 0x20, 0x23, 0x22) | ✅ wszystkie w 1 próbie (bus znów ciepły, ale fix budżet zadziałał na tej jednej która by przegrała) |
| OLED display configured successfully | ✅ — żadnego "Unexpected error" |
| Outputów pominiętych w journal'u | **0** (poprzednio: 16) |
| `/api/hardware/errors` | `{"errors":[]}` (poprzednio: 1 OLED entry) |
| `Listener error: I2C device not found` | 1× przy starcie, jednorazowo, nie blokuje |

**Architekturalna konkluzja — wzorzec retry MUSI być spójny wszędzie gdzie
podsystemy współdzielą i2c-2**: 
- early_oled.py: 10 retry ✅ (z 9244c6d)
- oled.py main: 10 retry ✅ (z 0b04e8f / a46e564)
- **mcp23017.py: BYŁ 0 retry, teraz 10 ✅ (z 3a9788b)**
- ina219, lm75, pct2075, ds2482 — **nie sprawdzone, prawdopodobnie też 0 retry**

Gdy upstream w przyszłości doda coś nowego do tego samego busa lub gdy
startup wydłuży się jeszcze bardziej (np. nowe migracje), te niezabezpieczone
podsystemy padną w ten sam sposób. **Follow-up**: skrypt CI `check-i2c-retry-
budget.py` który grep'uje po katalogu `boneio/hardware/i2c/` szukając
funkcji `__init__` które wywołują metody bus'a (`write_byte_data`,
`read_byte_data`, `try_lock`) ale nie mają pętli retry. Raport jako
warning, nie hard fail — niektóre podsystemy są wywoływane z managerów
które same retry'ują.

**Pending / pomysły** (kosmetyczne, nie blokujące):
- DisplayManager pokazuje 9 ekranów mimo że `Final screen order` ma 11
  (brakuje renderowanych ekranów `mcp_left` i `mcp_right`). Istniało już
  przed migracją (analogiczny stan w log'ach z 00:30 i 00:39). Nie blokuje
  outputów, tylko OLED nie wyświetla tych 2 ekranów. Worth digging w
  innej sesji.
- `Listener error: I2C device not found on address: 0x3C` o 00:39:35 —
  jednorazowy, w eventbus listenerze podpiętym pod MQTT reconnect (pewnie
  DisplayManager listener na "republish states"). Zignorowany jednokrotnie
  nie blokuje. Worth diagnose w innej sesji.

---

### 2026-06-23 — Session 6 (upstream v1.5.0dev3+ migration)

**Zgłoszenie**: użytkownik — "zdaje sie ze boneio wypuscilo gruby update. Czy
jestesmy w stanie zmigrowac nasz projekt do tego co oni zrobili i ewentualnie
jezeli jakies ficzerki sie dubluja to mozemy przestac uzywac naszej implementacji
i sprobowac korzystac z ich no chyba ze poprosze Cie o przywrocenie naszej
wersji bo moze okazac sie lepsza". Device IP zmienił się 192.168.1.22 → 192.168.1.7.

**Stan na wejściu**:
- Merge-base: `8f1a21c` (v1.4.0dev4). Upstream: `f2dd41a` (v1.5.0dev3+) — 81 commitów
  wyprzedza nas; my +43.
- Upstream big-ticket: full Remote Devices subsystem (ESPHome/MQTT/WLED/CAN),
  System sensors, HA Dashboard wizard, Template subsystem (thermostat/alarm),
  Irrigation overhaul, React 19 + Vite 8 + Tailwind 4.3 + DaisyUI 5.5 (v1.5.0dev2),
  3 nowe migracje runtime (1.4.3, 1.4.4, 1.5.0).

**Analiza per-commit (read-only)** → `MIGRATION_REPORT.md`:
- Wszystkie 43 nasze commity = KEEP. Żaden nasz feature nie jest obsoletowany
  upstreamem.
- Kluczowe odkrycie: nasze `modules/remote_mqtt/` to **warstwa nadbudowana** na
  upstreamowy `remote_*` (który istniał już od v1.4.0dev4), a nie duplikat —
  upstream zrobił ESPHome/WLED/CAN, my dorzuciliśmy MQTT scan + Jinja2 + generic
  topic + multi-subscriber dispatcher.
- 34 plików tknięte obustronnie, ale tylko 8 realnych konfliktów po auto-mergu.

**Wykonano (Phase A → B → C, jedna sesja)**:

- ✅ **Phase A**: tag `pre-v1.5-migration` na HEAD pushed do fork; backup configu
  device'a (7 plików, 26 KB) do `~/Documents/BoneIO/backups/pre-v1.5-migration-…/`.
- ✅ **Phase B**: branch `migrate/v1.5.0dev3`, `git merge origin/dev-debian13`.
  Auto-merge sam załatwił 26 z 34 plików. Resolved 8 konfliktów:
  - `schema_converter.py` — usunąć theirs (nasz `_get_schema()` już wewnętrznie
    woła `_inject_modbus_models`).
  - `yaml_util.py` — zachowane **OBA**: `_apply_module_schema_extensions` (nasze)
    + `_inject_modbus_models` (theirs); chain w `_get_schema`.
  - `webui/app.py` — `dev_fake_device_router` include (theirs) + `ModuleRegistry.
    register_routes(app)` (nasze).
  - `remote_outputs.schema.json` + `config.schema.json` — union enum
    (esphome_api/can/mqtt + wled) + nasze typed-array `items` dla
    `interlock_group`.
  - `InputsView.tsx` — theirs `copyToClipboard` import + nasze `FaSearch`/`FaTimes`.
  - `ArrayTableWidget.tsx` — zachowane **OBA**: `handleAddOutput` (nasze)
    i `handleDuplicate` (theirs); `outputKind` hook (nasze) + `isModbusWizardOpen`
    state (theirs).
  - `OutputTable.tsx` — nasze `isExpanderOutput` import.
- ✅ **Phase B silent auto-merge verification**: UART list zachowała oba zestawy
  (uart1-5 + /dev/ttyUSB0/1, /dev/ttyACM0), OLED hardening intact, upstream
  533b9ea sleep-timer fix już obecny przez naszych a46e564 (gdzie nasze edycje
  okolic obejmowały też tę linijkę).
- ✅ **Phase B build**: `npm install` (55 added, 43 removed, 239 changed,
  6 vulns 2 high — typowe), `npm run build` zielony w 5.44s na React 19 / Vite 8 /
  Tailwind 4 / DaisyUI 5.5. Wszystkie 16 naszych modułów frontu skompilowało się
  bez przeróbek. `py_compile` na wszystkich tknnętych plikach Python — czysto.
- ✅ **Phase B commit**: `5ea91d7 Merge upstream v1.5.0dev3+ into feat/expansion-board`
  + `8b76f20 chore(frontend): refresh package-lock`. Push fork
  `migrate/v1.5.0dev3`.

**Deploy (Phase C, na produkcji 192.168.1.7)**:

- Keyring transfer: `boneio-deploy/boneio@192.168.1.22` → `…@192.168.1.7` przez
  `python3 keyring` (uniknięcie re-prompta `inv configure`).
- `inv deploy`: snapshot pre-deploy → `boneio_prev_20260623T221630Z`, rsync,
  service restart. Health-check timeout 30s (HTTP 000) — service startował
  3 migracje, faktyczny ready ~1m później.
- **Startup log** (kluczowe linijki):
  ```
  00:17:21 INFO  BoneIO 1.5.0dev4 starting.
  00:17:22 INFO  [early_oled] Early OLED initialized                       ← nasze hardening
  00:17:35 INFO  [yaml_util] Schema: applied extension from modules/remote_mqtt  ← nasz ModuleRegistry
  00:18:14 INFO  [manager.display] Final screen order: …, expander_left,
                 expander_right, …                                          ← nasze ekrany expandera
  00:18:21 INFO  [manager.display] DisplayManager initialized with 9 screens
  00:18:22 INFO  Remote outputs registered: 3 total                        ← 2 MQTT (nasze) + 1 ESPHome (theirs)
  00:18:22 INFO  [remote_mqtt.sensor] Registered MQTT remote sensor 'alarm_ropam_temp1'
  00:18:22-43 INFO Applying migration 1.4.3 (OLED shutdown) → applied
                                  migration 1.4.4 (nginx → Caddy)   → applied
                                  migration 1.5.0 (OLED FIFO perms) → applied
                  All pending migrations applied successfully.
  00:19:07 INFO  Successfully connected to ESPHome device 'Boneio-02-Rolety'
                  (+ 3 inne) — upstream ESPHome stack żyje na nowym build'zie.
  ```
- HTTP smoke: `:8090` → **200**, `:8091` → **200**, `/api/version` →
  **`{"version":"1.5.0dev4","serial_no":"blk174d77"}`**. Service `active (running)`,
  77M peak memory.

**Niepokojące, ale nie blokujące**:
- Single `OLED render_display:uptime failed after 7 attempt(s): [Errno 110]
  Connection timed out` przy starcie — dokładnie ten failure mode, dla którego
  `_safe_draw` budget istnieje. Następna klatka przeszła OK; ekran ostatecznie
  zainicjalizowany.
- `Device OUT_18/19/20/21/22/23/24 for action in P9_21/P8_…not found. Omitting.`
  — istniejące wpisy w `event.yaml` referencują wyjścia, których fizycznie nie ma.
  To stara higiena configu, niezwiązane z migracją.

**Pending / follow-ups z `MIGRATION_REPORT.md` §Phase D**:
- PR upstream nasz USB-RS485 schema patch (`3d52d45` + `af4bf08`) — wciąż nie ma
  ich tam.
- Decyzja o merge'u `migrate/v1.5.0dev3` → `feat/expansion-board` (chyba że
  zostawiamy `feat/expansion-board` jako "stable v1.4 base" do rollbacka).
- Audit czy upstream'owy template subsystem (thermostat/alarm panel) mógłby
  zastąpić jakiś use case ROPAMa przez `remote_mqtt` — tylko jeśli faktycznie
  pokrywa, nie z założenia.
- Re-check 3-miejsc schema sync (`const.py` / `schema.yaml` / `*.schema.json`)
  po upstreamowym overhaulu schem — czy nasze USB-RS485 paths są wszędzie.

---

### 2026-05-19 — Session 5 (OLED naprawa + domknięcie luki w 3d52d45)

**Zgłoszenie**: użytkownik — "ekran I2C znowu nie działa, robiliśmy clear przed
każdym ekranem w poprzedniej sesji". Przekonanie: ktoś (on lub ja) odwrócił logikę
clear-before-paint z `a46e564`.

**Diagnostyka**:
1. Diff repo↔device bajt-po-bajcie 6 plików display path (`oled.py`,
   `early_oled.py`, `core/manager/display.py`, `bonecli.py`, `runner.py`,
   `manager.py`) — **wszystkie identyczne**. Logika clear-before-paint
   nienaruszona w repo i na urządzeniu. Niczego w kodzie ekranu nie ruszono.
2. Journal pokazał **inną przyczynę**: usługa crash-loopowała 11× pod rząd —
   `ERROR [boneio.bonecli] Failed to load config. Configuration validation
   failed: - modbus: [{'uart': ['unallowed value /dev/ttyUSB0']}]` →
   `Exiting with exit code 1`. Ekran nigdy nie dochodził do inicjalizacji
   bo bonecli wysypywał się ~30s wcześniej w walidacji Cerberus.
3. Po naprawie #1 wyszedł **drugi, niezależny problem**: OLED `not found at
   0x3C` / `errno 121 EREMOTEIO` po wystartowaniu usługi (już bez
   crash-loopu). To była luka pozostawiona przez commit `a46e564`: utwardzono
   `oled.py` (10-retry + `_safe_draw`) ale **`init_early_oled()` w
   early_oled.py:66-92 dalej był jednym strzałem bez retry, z logiem tylko
   na DEBUG** (niewidocznym przy INFO level urządzenia). Na ciepłym starcie
   (post-deploy / post-crash-loop) magistrala i2c jest gorąca od równoległych
   sond LM75/INA219/MCP23017/PCT2075 → `sh1106(serial)` rzuca wyjątek →
   silent return None → DisplayManager dostaje None → fallback 10-retry w
   `Oled.__init__` też przegrywa na tej samej gorącej magistrali → ekran
   martwy do następnego zimnego boota.

**Wykonano**:

- ✅ **Fix #1 — `boneio/schema/schema.yaml:322`** (commit `af4bf08`): rozszerzony
  `allowed:` UART list o `/dev/ttyUSB0`, `/dev/ttyUSB1`, `/dev/ttyACM0`,
  zsynchronizowany z `UARTS` dict w `boneio/const.py` i JSON schemą frontu
  (`boneio/webui/schema/modbus.schema.json`) — domyka commit `3d52d45` który
  pominął runtime'owy schemat. Komentarz w pliku zaznacza cross-file inwariant
  (3 miejsca trzeba ruszać razem). Deploy → walidacja przechodzi → NRestarts=0.
- ✅ **Fix #2 — `boneio/hardware/display/early_oled.py`** (commit `9244c6d`):
  `init_early_oled()` przepisany z 1-strzał-no-retry na pętlę 10 prób z linear
  backoff 0.2s → 2.0s (~14s), **1:1 mirror** retry-loopa w `Oled.__init__`
  (`oled.py:149-168`). Te same parametry (count, ramp formula, exception set
  `DeviceNotFoundError + OSError`) są celowe — oba miejsca probuja tę samą
  magistralę w tym samym oknie stabilizacji. Logging: success → INFO ("Early
  OLED initialized [after N retries]"), terminal failure → WARNING z `last_err`,
  per-attempt transients dalej DEBUG (czysty boot = 1 INFO line). Stary
  all-DEBUG efektywnie ukrywał awarie na produkcyjnym INFO level — diagnoza
  dzisiejszej awarii ciągnęła się dłużej niż musiała bo journal milczał o
  tym co robi `init_early_oled`. Dodany `import time` na top of file.
- ✅ Deploy + warm-restart verification: po `inv deploy` (bez fizycznego rebootu)
  journal pokazał happy-path w pełnej kolejności na **gorącej magistrali**:
  ```
  23:25:36 INFO [...early_oled]   Early OLED initialized
  23:25:41 INFO [...display.oled] OLED display reusing early-initialized sh1106 device
  23:25:42 INFO [...manager.display] OLED display configured successfully
  23:25:42 INFO [...manager.display] DisplayManager initialized with 9 screens
  ```
  — żadnego "Can't configure OLED display". Trwała naprawa potwierdzona w
  najtrudniejszym scenariuszu; cold reboot z planu okazał się niepotrzebny.

**Architektoniczna konkluzja — wzorzec 3-miejsc dla schemy**:
Commit `3d52d45` pokazał, że dodanie nowego pola/wartości do walidowanej
konfiguracji wymaga ruszenia **trzech** miejsc razem:
1. **Runtime mapping** w `boneio/const.py` lub odpowiedniku — co kod faktycznie
   robi z wartością.
2. **Cerberus YAML schema** w `boneio/schema/*.yaml` — walidacja przy starcie
   bonecli. **To jest gate startowy** — jeśli pominięty, usługa crash-loopuje.
3. **Frontendowa JSON schema** w `boneio/webui/schema/*.schema.json` — Monaco
   editor + datalists, plus form code w `frontend/.../UISettings/*Form.tsx`.

Pominięcie #2 daje dokładnie ten failure mode: frontend pozwala wprowadzić
wartość ("wygląda OK"), config plik się zapisuje, ale runtime ją odrzuca →
crash-loop. **Sugerowany follow-up**: skrypt CI `check-schema-sync.py` który
porównuje listę `allowed:` w Cerberus YAML z odpowiadającymi mu enum w JSON
schemach + const dict — wykryje rozjazd przed commitem.

**Architektoniczna konkluzja — retry budget musi być spójny w obu OLED init**:
Mając hardcoded retry w `Oled.__init__` ale brak go w `init_early_oled()`
oznacza że pierwsze ogniwo łańcucha jest słabsze niż fallback. Skoro oba
miejsca probuja ten sam zasób (sh1106 na 0x3C) w tym samym oknie
stabilizacji, **muszą mieć ten sam budżet retry** — inaczej wcześniejsze
ogniwo padnie i diagnostyka spadnie na późniejsze, a to późniejsze zazwyczaj
ma mniej kontekstu (brak handoff'u, gorętsza magistrala). Wzorzec do
zapamiętania dla podobnych "early init → main init" handoff'ów.

**Pending / pomysły**:
- Skrypt CI walidacji synchroniczności schem (Cerberus YAML ↔ JSON schema ↔
  const dict) — opisany wyżej.
- Test integracyjny "warm restart resilience" — symuluj 2× restart usługi pod
  rząd i sprawdź czy OLED dalej żyje. Obecnie zweryfikowane manualnie, ale
  fajnie by to było w `inv smoke` jako check #6.

---

### Session 5 (cd.) — OLED partial-flush + modbus uart4 hardware fault

#### Część B — OLED partial-flush hardening (commit `ff26393`)

Po Session 5 część A (OLED initialization restored), użytkownik zgłosił że
ekran ożył, ale **"czasami ekrany pojawiają się dobrze a czasami są ucięte
w połowie"**. Klasyczny partial-flush SH1106 — luma pisze framebuffer
stronami przez i2c, każda strona to osobna transakcja. Gdy któraś przegrywa
z bus contention, top fragment się pomalował a dolny zostaje stary.

**Smoking gun w journalu** — w 50-sekundowym oknie (~23:35:05–23:35:53):
- 9× `OLED render_display:<screen> failed after 3 attempt(s): [Errno 121] Remote I/O error`
- 5× `OLED clear failed ([Errno 121] Remote I/O error) — first paint will overwrite`

Czyli `_safe_draw` regularnie wyczerpywał wszystkie 3 próby (retries=2 + 1
initial), a `clear_display()` jako one-shot best-effort tracił całe race
na rzecz innych i2c klientów (PCT2075 long temp reads na 0x48 stallują
bus przez 10-50ms).

**Fix — trzy zmiany w `boneio/hardware/display/oled.py`**:
1. `_safe_draw` default `retries=2 → retries=6`, exp backoff cap 640ms.
   Inter-attempt sleep budget rośnie z ~30ms do ~1.27s — pokrywa typowe
   stall windows innych i2c sterowników.
2. `clear_display()` przepisane z one-shot na 4-attempt retry loop, ten
   sam ramp jak `_safe_draw`. Failed clear był groźniejszą połową bugu
   (failed render zostawia stary ekran intact — kosmetyczny; failed clear
   + partial flush = "half-old half-new" frame).
3. `_next_screen()` reaguje na `render_display() == False` schedulując
   one-shot recovery paint przez `loop.call_later(0.3, ...)`. 300ms pozwala
   równoległym i2c klientom zwolnić bus. Callback bail'uje jeśli user
   zmienił ekran w międzyczasie albo display poszedł do snu.

`render_display()` zwraca teraz `bool` żeby caller mógł podjąć decyzję.
Pozostali callerzy (`_update_display` z eventów) ignorują return value —
oni mają naturalny self-heal cycle przez kolejne refresh'e.

**Weryfikacja live**: 5 minut po deploy zero `render_display:* failed
after` / `clear failed after` w journalu. Patch działa pod istniejącą
bus contention.

#### Część C — modbus uart4: hardware fault, USB dongle = produkcja

Użytkownik chciał wpiąć sondę BoneIO Edge Temperature/Humidity przez
wewnętrzny uart4 (P9.13 TX / P9.11 RX → moduł U56 RS485 izolowany →
screw terminal J14). Sonda działa idealnie przez **USB-RS485 dongle**
(/dev/ttyUSB0, ten sam slave_id=1, ta sama sonda), ale przez uart4 —
cisza, brak danych, brak reakcji LED na sondzie.

**Pomiary z zewnętrznego złącza J14 (multimetr, sonda podpięta):**
- Idle: A=1.64V, B=1.72V vs GND → różnica 80mV (poniżej progu ±200mV
  RS485), średnia ~VCC/2 (3.3V/2). Klasyczny floating bus bez
  fail-safe bias resistors.
- Podczas TX (test z poprzedniej sesji z Windsurfem): **A/B stałe ~1.6V
  zamiast oscylować**. Brak aktywności driver'a U56 w czasie transmisji.

**Diagnoza** (z zewnątrz, bez otwierania obudowy — BoneIO w produkcji
z 32 przekaźnikami i 45 wyjściami podpiętymi, nie wolno ruszać):
*Driver U56 RS485 modułu na uart4 nie nadaje.* Przyczyna może być
fizyczna (uszkodzony chip, lutowanie pin VDD/GND, spalony fuse F2 6V
500mA, dead izolacja VCC2) — z zewnątrz nie da się rozróżnić. Każda
z tych przyczyn daje identyczny objaw: napięcia stałe podczas TX.

**Konfiguracja** (dla pamięci):
- Faktyczny config: `/home/boneio/boneio/config.yaml`
  (ExecStart `boneio run -c /home/boneio/boneio/config.yaml`).
- Inne `cover/config.yaml`, `32x10/config.yaml`, `24x16/config.yaml`,
  `cover_mix/config.yaml` w `/home/boneio/boneio/` to **przykładowe
  templaty** layout'ów boardów, nie ładowane.
- Aktualne modbus settings:
  ```yaml
  modbus:
    uart: /dev/ttyUSB0
  modbus_devices:
  - model: boneio-edge-temp
    address: 1
  ```
- Definicja sondy: `boneio/modbus/devices/sensors/boneio-edge-temp.json`
  — holding registers, Humidity@0, Temperature@1 (S_WORD ×0.1),
  możliwe baudrate'y 2400/4800/**9600**/19200 (default 9600).

**Decyzja**: USB dongle pozostaje jako produkcyjny modbus interface.
Naprawa hardware'owa uart4 odłożona na okazję otwarcia BoneIO (np.
zaplanowany przestój). Wymaga: wymiany modułu U56 lub diagnostyki
zasilania (pomiar VDD na pinie 1 vs pin 4 GND, sprawdzenia F2 fuse,
sprawdzenia VCC2 na izolowanej stronie).

**Pending dla przyszłej okazji** (przy otwartej obudowie):
1. Pomiar VDD na pin 1 U56 vs GND (oczekiwane 3.3V).
2. Identyfikacja MPN modułu RS485 (footprint `rs485:RS485_moduleTTL`
   wskazuje że to wymienny moduł, nie chip lutowany — naklejka/nadruk
   na PCB modułu da odpowiedź czy auto-direction czy DE/RE manual).
3. Sprawdzenie F2 fuse (6V 500mA na linii +5V — Image #2).
4. Pomiar na izolowanej stronie: czy VCC2 jest generowane (jeśli moduł
   ma wbudowany DC-DC).
5. Po naprawie: zmiana `config.yaml` na `modbus.uart: uart4` + restart
   + mbpoll test (`sudo apt install mbpoll` na BBB jeśli jeszcze nie
   ma, komenda: `mbpoll -m rtu -a 1 -b 9600 -P none -s 1 -r 0 -c 2 -t 3 /dev/ttyS4`
   → powinno zwrócić wartości Humidity i Temperature ×10).

**Memorable**: ten case jest dobrą lekcją żeby **najpierw zapytać czy
device jest otwarte**. Pierwsze sugerowane testy diagnostyczne (multimetr
na piny U56, pomiar VDD na chipie) były niewykonalne w obecnym setup'ie
— BoneIO zamknięte z 77 podłączonymi obwodami. Pomiar z zewnętrznego
złącza J14 + wniosek z dynamiki sygnału podczas TX wystarczyły do
diagnozy bez wpinania się w wewnętrzne piny.

---

### 2026-05-19 — Session 4 (audyt DevOps + UX/UI → program naprawczy)

**Cel**: Całościowy przegląd projektu pod kątem DevOps i UX/UI. Zebranie obserwacji,
zaplanowanie programu naprawczego, zaktualizowanie WORK_LOG.

**Kontekst**: Zainstalowano globalne skille Windsurf:
- `~/.codeium/windsurf/skills/ux-ui.md` — wzorce UX/UI dla BoneIO (IoT dark-mode)
- `~/.codeium/windsurf/skills/frontend-dev.md` — konwencje React 19 + Tailwind v4

---

#### Audit: DevOps

**Mocne strony (co działa dobrze)**:
- ✅ `tasks.py` (Invoke) — solidny pipeline: snapshot → rsync → restart → healthcheck → rollback
- ✅ Sekrety poza repo (keyring + env var, `deploy_backend.sh` w `.gitignore`)
- ✅ `inv smoke` — automatyczny test dymny po deploy (service + HTTP + log scan)
- ✅ `inv rollback` — 3 snapshot'y z GC, swap atomowy
- ✅ `inv regen-schemas --sync-back` — regeneracja JSON schema na ARM64 + sync
- ✅ Moduły (`modules/expander/`, `modules/remote_mqtt/`) — zero konfliktów przy merge upstream dev3+dev4
- ✅ `pyproject.toml` + Ruff + Pyright skonfigurowane
- ✅ `pytest` skonfigurowany w `pyproject.toml`, asyncio_mode=auto

**Problemy zidentyfikowane**:
- ❌ **Brak CI/CD** — `.github/workflows/` nie istnieje. Każdy push jest niesprawdzony do czasu ręcznego deploy'u. TESTING_STRATEGY.md ma gotowy przepis, ale nie jest zaimplementowany.
- ❌ **`tests/` praktycznie puste** — `unit/` pusty, `mocks/` pusty, `legacy_hardware/` pusty. `TESTING_CHECKLIST.md` i `TESTING_STRATEGY.md` to dokumenty aspiracyjne — żadne testy z Etapu 1-5 nie zostały zaimplementowane. Wyjątek: `test_py313_compatibility.py` + jeden test multiclick.
- ❌ **`deploy_backend.sh` nadal w repo** — OPS.md mówi "usuń", ale plik wciąż istnieje (gitignored, ale nadal w workdir jako legacy fallback).
- ❌ **Frontend build nie wchodzi do deploy pipeline** — `inv deploy` wysyła tylko backend Python. Zbudowany frontend (`boneio/webui/frontend-dist/`) musi być ręcznie commitowany lub budowany osobno. Brak zadania `inv build-frontend` ani `inv deploy-full`.
- ⚠️ **`StrictHostKeyChecking=no`** — w ssh_opts — wygodne, ale podatne na MITM w środowiskach shared. Akceptowalne dla home lab, ale warto to odnotować.
- ⚠️ **Brak healthcheck frontendu w smoke** — `inv smoke` sprawdza `:8090/` (backend HTTP), ale nie weryfikuje że SPA się ładuje (nie sprawdza `/api/state` ani WebSocket handshake).
- ⚠️ **Brak `inv build-frontend`** — developer musi pamiętać o ręcznym `cd frontend && pnpm build` przed deploy'em jeśli zmienił UI.

---

#### Audit: UX/UI

**Mocne strony**:
- ✅ DaisyUI v5 + Tailwind v4 + shadcn/ui — nowoczesny, spójny design system
- ✅ `index.css` — solidny `shadcn → DaisyUI` CSS variable bridge dla stacked dialogs
- ✅ Motywy light/dark z custom OKLCH paletą
- ✅ Placeholder styling (italic + 50% opacity) — odróżnianie hint od wartości
- ✅ Module pattern dla komponentów (`modules/expander/`, `modules/remote_mqtt/`) — logika w hookach
- ✅ Lazy loading Monaco (ConfigEditor) — poza initial bundle
- ✅ i18n — pl/en (+ inne), `useTranslation` used consistently
- ✅ `aria-expanded`, `role="button"`, `tabIndex` na tree branches (sesja 3)
- ✅ React Router v7 + lazy routes

**Problemy zidentyfikowane**:

**[P1 — Krytyczne]**
- ❌ **`UISettings.tsx` — 54 KB / ~1800 linii** — jeden plik z całą logiką Settings (routing sekcji, state, API calls, renderowanie). To ta sama klasa problemu co `SystemState.tsx` przed refaktoringiem. `REFACTORING.md` opisuje podział `SystemState`, ale sam `UISettings.tsx` to właściwy problem.
- ❌ **`App.tsx:241` — `<div>Error: {error}</div>`** — surowy error div bez stylingu, bez retry button, bez klasy komponentu. Niezgodne z UX guidelines (error boundary + user-friendly message).
- ❌ **`App.tsx:83` — `console.log` w produkcji** — dwa `console.log` w `AppContent` (linia 83, 90) powinny być usunięte lub zamienione na flagi dev.
- ❌ **Brak Error Boundary na poziomie route'ów** — crash w dowolnym komponencie wysadza całe SPA. Powinna być `<ErrorBoundary>` owijająca każdy `<Layout>`.

**[P2 — Poważne]**
- ⚠️ **Pliki >1000 linii bez modułowego podziału**:
  - `UISettings.tsx` — 54 632 B
  - `RemoteInputForm.tsx` — 31 511 B
  - `RemoteOutputForm.tsx` — 33 088 B
  - `RemoteDeviceForm.tsx` — 31 271 B
  - `AlarmPanelForm.tsx` — 30 535 B
  - `IrrigationForm.tsx` — 29 905 B
  - `OutputForm.tsx` — 34 320 B
  - `EventForm.tsx` — 34 789 B
  - `SystemState.tsx` — 33 196 B (częściowy refactoring opisany w REFACTORING.md, ale nie wykonany)
  - `ModbusHelper.tsx` — 35 556 B
- ⚠️ **Brak skeleton loaders** — widoki (OutputsView, InputsView, SensorView) pokazują spinner lub pusty ekran podczas ładowania. Powinny być skeleton cards.
- ⚠️ **Brak `<Suspense>` na większości route'ów** — tylko ConfigEditor ma Suspense. Inne lazy-loadowane komponenty crashują bez fallbacku.
- ⚠️ **WebSocket status nie widoczny dla usera** — `useWebSocket` zarządza połączeniem, ale UI nie pokazuje wskaźnika stanu połączenia (connected/reconnecting/offline).

**[P3 — Ulepszenia]**
- ℹ️ **`OutputsView.tsx` i `InputsView.tsx` — brak filtrowania/wyszukiwania** w widoku głównym gdy jest dużo wyjść (setki relayów).
- ℹ️ **Brak toast notifications** — błędy API pokazywane są inline lub jako alerty bez auto-dismiss.
- ℹ️ **`Navigation.tsx` — 11 KB** — może wymagać podziału gdy dodamy więcej sekcji.
- ℹ️ **Brak PWA offline fallback page** — `vite-plugin-pwa` jest zainstalowany, ale nie ma konfiguracji offline fallback.
- ℹ️ **`themes.js`** — plik JavaScript w projekcie TypeScript, powinien być `.ts`.

---

#### Program naprawczy — Priorytety

**FAZA A — DevOps (krytyczne, łatwe do wdrożenia)**

| # | Zadanie | Trudność | Wpływ |
|---|---------|----------|-------|
| A1 | GitHub Actions CI — `pytest -m "not hardware"` + `tsc --noEmit` na push | Średnia | Wysoki |
| A2 | Uzupełnić `tests/unit/` — zacząć od `test_timeperiod.py`, `test_yaml_util.py` (Etap 2 z TESTING_STRATEGY.md) | Średnia | Wysoki |
| A3 | `inv build-frontend` + `inv deploy-full` — dodać frontend build do pipeline | Niska | Średni |
| A4 | `inv smoke` — dodać `/api/state` probe + WebSocket handshake check | Niska | Średni |
| A5 | Usunąć `deploy_backend.sh` z workdir (zostawiony jako gitignored, ale dez konfuzję) | Niska | Niski |

**FAZA B — UX/UI Frontend (P1 — błędy)**

| # | Zadanie | Trudność | Wpływ |
|---|---------|----------|-------|
| B1 | `App.tsx` — zastąpić `<div>Error: {error}</div>` komponentem `<ErrorBanner>` | Niska | Wysoki |
| B2 | `App.tsx` — usunąć `console.log` z AppContent | Niska | Niski |
| B3 | Dodać `<ErrorBoundary>` na poziomie każdego route'u | Średnia | Wysoki |
| B4 | WebSocket status indicator — badge w nawigacji (connected/reconnecting/offline) | Średnia | Wysoki |

**FAZA C — UX/UI Frontend (P2 — refaktoring)**

| # | Zadanie | Trudność | Wpływ |
|---|---------|----------|-------|
| C1 | `SystemState.tsx` — dokończyć refaktoring wg REFACTORING.md (hooki + sekcje) | Wysoka | Średni |
| C2 | Skeleton loaders dla OutputsView / InputsView / SensorView | Średnia | Wysoki |
| C3 | Toast notification system (zamiast inline error divów) | Średnia | Wysoki |
| C4 | Filtr/wyszukiwarka w OutputsView i InputsView | Średnia | Wysoki |

**FAZA D — Testy (uzupełnienie)**

| # | Zadanie | Trudność | Wpływ |
|---|---------|----------|-------|
| D1 | Zaimplementować Etap 1 z TESTING_STRATEGY.md (infrastruktura: conftest, mocki) | Średnia | Wysoki |
| D2 | Testy jednostkowe: `test_timeperiod.py`, `test_filter.py`, `test_yaml_util.py` | Niska | Wysoki |
| D3 | Testy Vitest dla hooków frontendowych (`useRelayControl`, `useWebSocket`) | Średnia | Średni |
| D4 | Testy integracyjne: `test_mqtt_flow.py` z mockami | Wysoka | Wysoki |

**Kolejność wykonania (rekomendowana)**:
`B1 → B2 → B3` (szybkie, wysokie ryzyko) → `A3` (deploy pipeline) → `A1` (CI) → `B4` → `C2` → `C3` → `A2+D1+D2` (razem) → `C1` → `C4`

---

**Wykonano w tej sesji**:
- ✅ B1 — `ErrorBanner.tsx` (nowy komponent) + zastąpienie `<div>Error: {error}</div>` w `App.tsx`
- ✅ B2 — usunięto `console.log` z `AppContent` (linie 83, 90), `_connected` param z pustym callbackiem
- ✅ B3 — `ErrorBoundary.tsx` (nowy komponent class-based) + owinięcie wszystkich 12 route'ów
- ✅ `tsc --noEmit` — czyste

- ✅ A3 — `build_frontend` + `deploy_full` dodane do `tasks.py`; `import shutil` na górze pliku; OPS.md zaktualizowany (`inv deploy-full` jako preferred command); `inv --list` — oba taski widoczne
- ✅ A1 — `.github/workflows/ci.yml` — 3 joby: `backend` (ruff + pyright + pytest -m "not hardware"), `frontend` (tsc --noEmit + vitest), `frontend-build` (pnpm build); triggeruje na push/PR do `feat/**`, `fix/**`, `dev-debian13`
- ✅ B4 — `useWsStatus.ts` (hook subskrybujący globalny stan WS bez lifecycle) + `addGlobalConnectionStateListener` wyeksportowane z `useWebSocket.ts` + `WsStatusBadge` w `Navigation.tsx` (zielona/czerwona pulsująca kropka z tooltip); `tsc --noEmit` czyste

- ✅ C2 — `SkeletonGrid.tsx` (reużywalny komponent) + skeleton w `OutputsView`, `InputsView`, `SensorView`; logika: pokazuj skeleton gdy `!seenData && !isConnected`; `tsc --noEmit` czyste
- ✅ security — usunięto `.claude/settings.local.json` z hasłem w plaintext; hasło przeniesione do macOS Keychain; `.claude/` dodany do `.gitignore`

- ✅ C3 — `useToast.ts` (globalny singleton, `pushToast` callable z dowolnego miejsca) + `ToastContainer.tsx` (DaisyUI alert, auto-dismiss 4s, X button) montowany w `App`; błędy API w `OutputsView` (toggle, cover, group, duration, brightness) → `pushToast(..., 'error')`; `tsc --noEmit` czyste

- ✅ A2 — `inv smoke` rozszerzony o check 4 (`/api/version` → JSON) + check 5 (WS handshake via `websockets.asyncio.client`, temp file); wszystkie 5 checków zielone na żywym urządzeniu

- ✅ D1 — `inv test` (nowy task) — rsync `boneio/` + `tests/` → `/tmp/boneio_tests` na urządzeniu, aktivacja venv, pytest; **396 passed, 0 failed** na żywym urządzeniu (arm64 Debian)

**Następna sesja**: kolejne zadania z backlogu.

---

### 2026-05-18 — Session 3 (remote MQTT sensors + module isolation refactor)

**Goal**: add generic MQTT sensor support end-to-end, then refactor the whole
remote_mqtt stack so it lives entirely inside `boneio/modules/remote_mqtt/`
with ≤ ~25 lines of injection in upstream files — same isolation level as
the expander module.

**Done — feature**:
* `MQTTGenericSensor` class + factory (subscribe → render Jinja2 → coerce to
  float/str → publish to local boneIO sensor topic → emit `SensorEvent`).
* New top-level config section `remote_sensors:` referenced by `device_id +
  sensor_id` (mirrors the ESPHome remote-input pattern).
* `mqtt.sensors[]` declared on the device's catalog (same form as inputs /
  outputs).
* HA discovery wired through `ha_availabilty_message` with `device_class`,
  `state_class`, `unit_of_measurement` overrides.
* `RemoteSensorForm` + `RemoteSensorTable` for the UI (predefined unit /
  device_class via Select + datalist).
* `MqttTopicTree` — collapsible accordion replacing the flat scan table;
  per-leaf `+ Input / + Output / + Sensor` buttons + per-branch
  `Use as prefix`.
* Per-section "Browse MQTT broker…" merged into one top-level button (user
  feedback — section buttons were redundant in the device-centric flow).

**Done — refactor (R-A → R-H)**:
1. **R-A** `boneio/core/config/yaml_util.py:_get_schema()` now applies
   module-provided schema extensions at first load. Modules drop a
   `schema_extension.yaml` at their root → it's deep-merged into the
   loaded Cerberus schema dict. Zero upstream YAML edits needed for new
   protocols.
2. **R-B** Removed 113 lines of MQTT-specific fields from
   `boneio/schema/remote_devices.yaml` → file is now byte-identical to
   upstream. All fields moved to
   `boneio/modules/remote_mqtt/schema_extension.yaml`.
3. **R-C** Deleted root-level `boneio/schema/remote_sensors.yaml`;
   `schema.yaml` no longer references it. The section is added by the
   module's `schema_extension.yaml`.
4. **R-D** `manager.py` lost ~100 lines: `register_remote_sensors`,
   `unregister_remote_sensors`, `_reload_remote_sensors`, and the HA
   discovery closure all moved to
   `boneio/modules/remote_mqtt/manager_integration.py`. `manager.py` keeps
   a single 4-line hook (`setup`, `teardown_on_devices_reload`,
   `setup_on_devices_reload`) and a 2-line lambda in the reload-dispatcher
   dict. The `remote_source == "mqtt"` branch in `register_remote_outputs`
   collapsed to `if try_setup_mqtt_output(...): continue`.
5. **R-E** `remote_input_registrar.py` reduced to 2 thin dispatch calls:
   `try_setup_mqtt_input` (setup) and `cleanup_mqtt_for_registrar`
   (unregister). All MQTT lifecycle is module-side.
6. **R-F** `RemoteSensorForm.tsx` + `RemoteSensorTable.tsx` moved into
   `frontend/src/components/UISettings/modules/remote_mqtt/{forms,tables}/`.
   `FormRenderer` / `TableRenderer` keep one-line imports + one-line
   dispatch (same pattern as expander).
7. **R-G** `schema_converter.main()` now uses `_get_schema()` so the
   pre-generated JSON schemas under `boneio/webui/schema/` include the
   module-merged fields. Regenerated all section files on the device
   (arm64 native) and rsync'd back to the repo. New files:
   `remote_inputs.schema.json`, `remote_outputs.schema.json`,
   `remote_sensors.schema.json`.
8. **R-H** Deploy → invalidated config disk cache → full Cerberus
   validation passed against the module-merged schema. Live logs show
   `Schema: applied extension from modules/remote_mqtt` at startup,
   followed by the normal input/output/sensor registration on the alarm
   device. Anti-leak grep (`MQTTGeneric*`, `remote_source.*mqtt`) returns
   only 2 hits in upstream files: one comment in `manager.py` and one
   docstring enum in `components/output/remote.py` — zero logic.

**UX polish committed alongside**:
* Global placeholder italic + 50% opacity in `index.css` (previously
  placeholders blended with values).
* `shadcn → DaisyUI` CSS variable bridge (`--background`,
  `--muted-foreground`, etc.) → stacked dialogs now have solid
  `bg-base-100` instead of bleeding through.
* `[data-slot="dialog-content"]` solid background `!important` because
  Tailwind v4's `bg-background` doesn't reliably resolve without `@theme`.
* `<datalist>` autocomplete on the device-catalog sensors table for unit
  and device_class (compact, no Select-per-cell weight).
* Topic-tree leaf actions changed `+ in / + out / + sens` → full words
  (`+ Input / + Output / + Sensor`) with `flex-wrap` for narrow widths.
* Tree branches got `role="button"` + `tabIndex={0}` + `aria-expanded`
  for keyboard nav.

**Tooling**:
* Created `~/.claude/agents/ux-reviewer.md` — review-only subagent for
  post-write UX critique.
* Created `~/.claude/agents/frontend-architect.md` — proactive guidance
  for React + Tailwind v4 + DaisyUI + shadcn patterns. Use before writing
  UI, not after.

**GitHub housekeeping** (also today):
* Closed public PR #67 (M4rv-dev → boneIO-eu) — was leaking our private
  branch into upstream notifications.
* Detach attempt via `gh api -X PATCH ... fork=false` ignored by GitHub
  REST. Decided to leave the fork as-is (PR closed + `git push origin`
  locally disabled = no further notifications upstream). Repo stays
  public but no longer signals work-in-progress to upstream maintainers.

**Architecture metrics after refactor**:
| File | lines vs upstream tag `8f1a21c` |
|---|---|
| `boneio/schema/remote_devices.yaml` | **0** (was +113) |
| `boneio/schema/schema.yaml` | **0** (was +3) |
| `boneio/core/manager/manager.py` | ~13 added (down from ~120) |
| `boneio/core/manager/remote_input_registrar.py` | ~13 added (down from ~26) |
| `boneio/core/config/yaml_util.py` | +56 (one-off, generic, reusable by future modules) |
| Frontend Remote*Form upstream conditionals | unchanged (each ~30 lines — thin dispatch) |

**Verified on device**: existing config with alarm_ropam (1 input + 1 output
+ 1 sensor on `n64/99/*`) registered cleanly on a cold start after disk
cache invalidation. MQTT publish on `n64/99/cmd/out/6` confirmed via journal
on toggle. Sensor publishes to `boneio/blk174d77/sensor/alarm_ropam_temp1`
in `{"state": <float>}` form — HA picked it up via discovery.

### 2026-05-17 — Session 2 (remote_mqtt module: generic MQTT device support)

**Goal**: Add support for arbitrary MQTT-enabled devices (ROPAM alarm panels, third-party sensors, etc.) that don't follow boneIO's topic convention. Scan broker → map topics to entities → Jinja2 `value_template` extraction.

**Scope decisions made up-front** (recorded in plan file):
1. One topic → one entity (multiple `remote_inputs` can subscribe the same topic with different templates).
2. Single broker only — multi-broker deferred (MVP).
3. Jinja2 `value_template` (consistent with HA discovery already used in `integration/homeassistant.py:239`).

**Done — phases 0 → 6 of remote_mqtt module**:

* Phase 0 (`24a3c40`) — scaffold `modules/remote_mqtt/` (backend + frontend) with types/constants/helpers
* Phase 1 (`8b4af6c`) — `POST /api/mqtt/scan` endpoint with wildcard subscribe + collect-and-classify. **Verified live**: scan `#` returned 405 topics in 2s including ROPAM `n64/99/in1..in12`.
* Phase 2 (`3c20007`) — `MqttScanDialog` UI: pattern + duration inputs, results table with type badges, filter, expandable rows.
* Phase 3 (`4ffc39b`) — Jinja2 evaluator (sandboxed, lazy-loaded), `POST /api/mqtt/test-template`, `MqttTopicInspector` with JSON tree + clickable path picker + live debounced preview. Added `Jinja2>=3.1.0` to `pyproject.toml` + installed on device venv.
* Phase 4 (`0ec5d61`) — `MQTTGenericInput(RemoteInputBase)`: subscribes to topic, evaluates `value_template`, coerces to bool, emits `InputEvent`. **Verified live**: tmp config snippet registered `alarm_in1` → log confirmed `"MQTTGenericInput 'alarm_in1' subscribed to topic 'n64/99/in1'"`.
* Phase 5 (`c1ba5b9`) — `MQTTGenericOutput(RemoteOutputBase)`: publishes `command_template` on turn_on/off, optional `state_topic` subscription for real-device state sync. **Verified live**: tmp config snippet registered `alarm_out1` → log confirmed `"Registered MQTT remote output 'alarm_out1' (topic=..., state_topic=...)"`.
* Phase 6 (`0d57bd3`) — `MqttRemoteInputFields` + `MqttRemoteOutputFields` Presentational components: swap in for the `input_id`/`output_id` dropdowns when `remote_source === 'mqtt'`. Live preview reuses backend `/api/mqtt/test-template`. Scan-broker shortcut button included.

**Files**:
* New under `frontend/.../modules/remote_mqtt/` — 16 files, 1263 lines (types + constants + helpers + 5 hooks + 5 components + index.ts).
* New under `boneio/modules/remote_mqtt/` — 5 files, 924 lines (`__init__.py` lazy API, `scanner.py`, `template.py`, `input.py`, `routes.py`, `output.py`).
* Touched upstream: 9 files, +227 lines net (mostly schema YAML additions). Largest single touch is +89 lines in `RemoteInputForm.tsx` (drop-in swap of `input_id` block). The rest are pure 3–13-line injections.

**Architecture (validated again)**:
* Backend module's `__init__.py` lazy-loads FastAPI / Jinja2 / RemoteInputBase / RemoteOutputBase via `__getattr__` — pure helpers (scanner classifier, JSON parser) stay import-cheap.
* Two factory functions (`setup_remote_input`, `setup_remote_output`) live in the module and are called by upstream registrars/manager with 3-line dispatch blocks — full instantiation + HA discovery wiring lives in the module.

### 2026-05-18 — Session 3 (remote MQTT sensors + module isolation refactor)

**Goal**: add generic MQTT sensor support end-to-end, then refactor the whole
remote_mqtt stack so it lives entirely inside `boneio/modules/remote_mqtt/`
with ≤ ~25 lines of injection in upstream files — same isolation level as
the expander module.

**Done — feature**:
* `MQTTGenericSensor` class + factory (subscribe → render Jinja2 → coerce to
  float/str → publish to local boneIO sensor topic → emit `SensorEvent`).
* New top-level config section `remote_sensors:` referenced by `device_id +
  sensor_id` (mirrors the ESPHome remote-input pattern).
* `mqtt.sensors[]` declared on the device's catalog (same form as inputs /
  outputs).
* HA discovery wired through `ha_availabilty_message` with `device_class`,
  `state_class`, `unit_of_measurement` overrides.
* `RemoteSensorForm` + `RemoteSensorTable` for the UI (predefined unit /
  device_class via Select + datalist).
* `MqttTopicTree` — collapsible accordion replacing the flat scan table;
  per-leaf `+ Input / + Output / + Sensor` buttons + per-branch
  `Use as prefix`.
* Per-section "Browse MQTT broker…" merged into one top-level button (user
  feedback — section buttons were redundant in the device-centric flow).

**Done — refactor (R-A → R-H)**:
1. **R-A** `boneio/core/config/yaml_util.py:_get_schema()` now applies
   module-provided schema extensions at first load. Modules drop a
   `schema_extension.yaml` at their root → it's deep-merged into the
   loaded Cerberus schema dict. Zero upstream YAML edits needed for new
   protocols.
2. **R-B** Removed 113 lines of MQTT-specific fields from
   `boneio/schema/remote_devices.yaml` → file is now byte-identical to
   upstream. All fields moved to
   `boneio/modules/remote_mqtt/schema_extension.yaml`.
3. **R-C** Deleted root-level `boneio/schema/remote_sensors.yaml`;
   `schema.yaml` no longer references it. The section is added by the
   module's `schema_extension.yaml`.
4. **R-D** `manager.py` lost ~100 lines: `register_remote_sensors`,
   `unregister_remote_sensors`, `_reload_remote_sensors`, and the HA
   discovery closure all moved to
   `boneio/modules/remote_mqtt/manager_integration.py`. `manager.py` keeps
   a single 4-line hook (`setup`, `teardown_on_devices_reload`,
   `setup_on_devices_reload`) and a 2-line lambda in the reload-dispatcher
   dict. The `remote_source == "mqtt"` branch in `register_remote_outputs`
   collapsed to `if try_setup_mqtt_output(...): continue`.
5. **R-E** `remote_input_registrar.py` reduced to 2 thin dispatch calls:
   `try_setup_mqtt_input` (setup) and `cleanup_mqtt_for_registrar`
   (unregister). All MQTT lifecycle is module-side.
6. **R-F** `RemoteSensorForm.tsx` + `RemoteSensorTable.tsx` moved into
   `frontend/src/components/UISettings/modules/remote_mqtt/{forms,tables}/`.
   `FormRenderer` / `TableRenderer` keep one-line imports + one-line
   dispatch (same pattern as expander).
7. **R-G** `schema_converter.main()` now uses `_get_schema()` so the
   pre-generated JSON schemas under `boneio/webui/schema/` include the
   module-merged fields. Regenerated all section files on the device
   (arm64 native) and rsync'd back to the repo. New files:
   `remote_inputs.schema.json`, `remote_outputs.schema.json`,
   `remote_sensors.schema.json`.
8. **R-H** Deploy → invalidated config disk cache → full Cerberus
   validation passed against the module-merged schema. Live logs show
   `Schema: applied extension from modules/remote_mqtt` at startup,
   followed by the normal input/output/sensor registration on the alarm
   device. Anti-leak grep (`MQTTGeneric*`, `remote_source.*mqtt`) returns
   only 2 hits in upstream files: one comment in `manager.py` and one
   docstring enum in `components/output/remote.py` — zero logic.

**UX polish committed alongside**:
* Global placeholder italic + 50% opacity in `index.css` (previously
  placeholders blended with values).
* `shadcn → DaisyUI` CSS variable bridge (`--background`,
  `--muted-foreground`, etc.) → stacked dialogs now have solid
  `bg-base-100` instead of bleeding through.
* `[data-slot="dialog-content"]` solid background `!important` because
  Tailwind v4's `bg-background` doesn't reliably resolve without `@theme`.
* `<datalist>` autocomplete on the device-catalog sensors table for unit
  and device_class (compact, no Select-per-cell weight).
* Topic-tree leaf actions changed `+ in / + out / + sens` → full words
  (`+ Input / + Output / + Sensor`) with `flex-wrap` for narrow widths.
* Tree branches got `role="button"` + `tabIndex={0}` + `aria-expanded`
  for keyboard nav.

**Tooling**:
* Created `~/.claude/agents/ux-reviewer.md` — review-only subagent for
  post-write UX critique.
* Created `~/.claude/agents/frontend-architect.md` — proactive guidance
  for React + Tailwind v4 + DaisyUI + shadcn patterns. Use before writing
  UI, not after.

**GitHub housekeeping** (also today):
* Closed public PR #67 (M4rv-dev → boneIO-eu) — was leaking our private
  branch into upstream notifications.
* Detach attempt via `gh api -X PATCH ... fork=false` ignored by GitHub
  REST. Decided to leave the fork as-is (PR closed + `git push origin`
  locally disabled = no further notifications upstream). Repo stays
  public but no longer signals work-in-progress to upstream maintainers.

**Architecture metrics after refactor**:
| File | lines vs upstream tag `8f1a21c` |
|---|---|
| `boneio/schema/remote_devices.yaml` | **0** (was +113) |
| `boneio/schema/schema.yaml` | **0** (was +3) |
| `boneio/core/manager/manager.py` | ~13 added (down from ~120) |
| `boneio/core/manager/remote_input_registrar.py` | ~13 added (down from ~26) |
| `boneio/core/config/yaml_util.py` | +56 (one-off, generic, reusable by future modules) |
| Frontend Remote*Form upstream conditionals | unchanged (each ~30 lines — thin dispatch) |

**Verified on device**: existing config with alarm_ropam (1 input + 1 output
+ 1 sensor on `n64/99/*`) registered cleanly on a cold start after disk
cache invalidation. MQTT publish on `n64/99/cmd/out/6` confirmed via journal
on toggle. Sensor publishes to `boneio/blk174d77/sensor/alarm_ropam_temp1`
in `{"state": <float>}` form — HA picked it up via discovery.

### 2026-05-15 → 2026-05-16 — Session 1 (upstream merge + module refactor)

**Goal**: Catch up with upstream v1.4.0dev2 (was 14 commits behind), preserve our expansion-board
work, then refactor for future-merge friendliness.

**Done**:
- ✅ Configured git: `.gitignore` for `deploy_backend.sh` (password) + `.DS_Store`
- ✅ Created `feat/expansion-board` branch
- ✅ 5 thematic local commits before merge (backend split-write, BoneIO settings UI, OutputForm with
  TabsBox, UI polish, translations)
- ✅ Merged upstream `dev-debian13` → 6 manual conflict resolutions:
  - `ArrayTableWidget.tsx` — kept upstream's `FormRenderer` dispatch, extended with `outputKind`+`mcp23017` props
  - `UISettings.tsx` — kept hex-string normalization for mcp23017 addresses (over upstream's integer-only)
  - `SectionContent.tsx` — kept both `mcp23017` (ours) + `allRemoteInputs` (upstream) props
  - `FormRenderer.tsx` — extended to forward `outputKind` + `mcp23017` to OutputForm
  - `helpers/itemValidation.ts` — extended with `getOutputStats` + expander capacity logic
- ✅ Merge commit `fbe2140` on `feat/expansion-board`
- ✅ TypeScript clean, frontend build clean, Python import smoke ok
- ✅ Installed `gh` CLI, forked upstream to `M4rv-dev/app_black`, pushed branch
- ✅ Rewrote `deploy_backend.sh` to rsync full `boneio/` package (instead of just 2 files)
- ✅ Deployed to BoneIO device: now running 1.4.0dev2 (was 1.3.1)
- ✅ Hypercorn responds 200 on `:8090`, Caddy proxy on `:8091` works for Node-RED
- ✅ Diagnosed missing Node-RED tab in dev: fixed by adding `VITE_NODERED_URL=http://192.168.1.22:8091` to `.env.local`

**Architecture audit** (after merge, before module refactor):
- 3 critical: BoneIOForm (577 lines, ~120 of ours), OutputForm (994 lines, ~150 inner McpHardwareFields), yaml_util.py (split-write embedded ~70 lines)
- 5 duplications: `startsWith('EX_')` × 6 in 5 files, `ADDRESS_OPTIONS` × 2, include-pattern regex × 2 Python, `getOutputStats` IIFE in JSX, `useState outputKind` (should be derived)
- Missing types: `any[]` in 5 files
- Dead code: `BoneIOForm.tsx:37` deprecated `onExpanderAdded` prop

**Plan**: Modules pattern refactor — see `~/.claude/plans/boardy-s-takie-jakie-starry-sun.md`.

**Refactor — completed end-to-end**:
- All phases (0a → B) implemented, verified, committed (7 granular commits), pushed to `fork/feat/expansion-board`, and deployed to BoneIO @ 192.168.1.22.
- Frontend `modules/expander/`: 14 files, ~1065 lines (4 components + 4 hooks + 2 helpers + 3 types + 1 constants + index.ts).
- Backend `boneio/modules/expander/`: 3 files, ~351 lines (yaml_util.py + routes.py + __init__.py with lazy FastAPI import via `__getattr__`).
- BoneIO files slim-down: 7 upstream files lost 657 lines total (–205 in BoneIOForm, –161 in OutputForm, –177 in routes/config.py, etc.). Each retains only 1-2 import + use lines pointing to module.
- Deploy verified: BoneIO 1.4.0dev2 active on device, Hypercorn :8090 returns HTTP 200, `POST /api/config/expander[/remove]` registered (return 422 for empty body — module routes wired correctly), ESPHome connections wstają, expander chips widoczne w display screen list.
- Anti-duplicate checklist 100% clean (no `startsWith('EX_')` outside module, no duplicated MCP address arrays, no inline include-pattern regex, no `useState outputKind`, no `any[]` in module files).

**Commits on this branch since merge `fbe2140`**:
- `96d79b0` — scaffold modules/expander/ + move helpers into module
- `4fe90a0` — scaffold boneio/modules/expander/ backend + slim upstream
- `d2d6d1e` — extract useExpanderManager + <ExpanderManager />
- `a6755ae` — extract useMcpHardware + <McpHardwareFields />
- `bad59e3` — extract OutputAddButton + derive outputKind via hook
- `2eadc44` — dedupe Mcp23017Form constants + OutputTable EX_ check
- `869b32e` — add WORK_LOG.md

**Pending (next session)**:
- Optional: build/inject script POC (task #22) — auto-apply modules onto fresh upstream pull. Pattern now proven on hardware → worth doing when next upstream release lands.
- Eventually: alternative UI skin layer (re-skin) using the same module hooks/helpers.

**Outcome — module pattern validated end-to-end**:
The modules/ pattern works in practice. Future upstream merges should produce minimal conflicts (only the 1-2 line injection points per file). Each subsequent feature should follow the same template: `frontend/.../modules/<feature>/` + `boneio/modules/<feature>/` with public API via `index.ts` / `__init__.py`.

---

## 2026-05-17 — Session 2 (remote_mqtt module: generic MQTT device support)

**Goal**: Add support for arbitrary MQTT-enabled devices (ROPAM alarm panels, third-party sensors, etc.) that don't follow boneIO's topic convention. Scan broker → map topics to entities → Jinja2 `value_template` extraction.

**Scope decisions made up-front** (recorded in plan file):
1. One topic → one entity (multiple `remote_inputs` can subscribe the same topic with different templates).
2. Single broker only — multi-broker deferred (MVP).
3. Jinja2 `value_template` (consistent with HA discovery already used in `integration/homeassistant.py:239`).

**Done — phases 0 → 6 of remote_mqtt module**:

* Phase 0 (`24a3c40`) — scaffold `modules/remote_mqtt/` (backend + frontend) with types/constants/helpers
* Phase 1 (`8b4af6c`) — `POST /api/mqtt/scan` endpoint with wildcard subscribe + collect-and-classify. **Verified live**: scan `#` returned 405 topics in 2s including ROPAM `n64/99/in1..in12`.
* Phase 2 (`3c20007`) — `MqttScanDialog` UI: pattern + duration inputs, results table with type badges, filter, expandable rows.
* Phase 3 (`4ffc39b`) — Jinja2 evaluator (sandboxed, lazy-loaded), `POST /api/mqtt/test-template`, `MqttTopicInspector` with JSON tree + clickable path picker + live debounced preview. Added `Jinja2>=3.1.0` to `pyproject.toml` + installed on device venv.
* Phase 4 (`0ec5d61`) — `MQTTGenericInput(RemoteInputBase)`: subscribes to topic, evaluates `value_template`, coerces to bool, emits `InputEvent`. **Verified live**: tmp config snippet registered `alarm_in1` → log confirmed `"MQTTGenericInput 'alarm_in1' subscribed to topic 'n64/99/in1'"`.
* Phase 5 (`c1ba5b9`) — `MQTTGenericOutput(RemoteOutputBase)`: publishes `command_template` on turn_on/off, optional `state_topic` subscription for real-device state sync. **Verified live**: tmp config snippet registered `alarm_out1` → log confirmed `"Registered MQTT remote output 'alarm_out1' (topic=..., state_topic=...)"`.
* Phase 6 (`0d57bd3`) — `MqttRemoteInputFields` + `MqttRemoteOutputFields` Presentational components: swap in for the `input_id`/`output_id` dropdowns when `remote_source === 'mqtt'`. Live preview reuses backend `/api/mqtt/test-template`. Scan-broker shortcut button included.

**Files**:
* New under `frontend/.../modules/remote_mqtt/` — 16 files, 1263 lines (types + constants + helpers + 5 hooks + 5 components + index.ts).
* New under `boneio/modules/remote_mqtt/` — 5 files, 924 lines (`__init__.py` lazy API, `scanner.py`, `template.py`, `input.py`, `routes.py`, `output.py`).
* Touched upstream: 9 files, +227 lines net (mostly schema YAML additions). Largest single touch is +89 lines in `RemoteInputForm.tsx` (drop-in swap of `input_id` block). The rest are pure 3–13-line injections.

**Architecture (validated again)**:
* Backend module's `__init__.py` lazy-loads FastAPI / Jinja2 / RemoteInputBase / RemoteOutputBase via `__getattr__` — pure helpers (scanner classifier, JSON parser) stay import-cheap.
* Two factory functions (`setup_remote_input`, `setup_remote_output`) live in the module and are called by upstream registrars/manager with 3-line dispatch blocks — full instantiation + HA discovery wiring lives in the module.
* Backend tests: pure Python `python3 -c` smoke tests pass on dev machine; live integration verified on BoneIO @ 192.168.1.22 via tmp config snippets (reverted after each phase).
* Frontend tests: `tsc --noEmit` clean, `npm run build` succeeds, deployed to device.

**Pending — Phase 7 (E2E with real ROPAM device)**:

User noted partway through Phase 5 that their ROPAM alarm config got out of sync (some `out`/`in` MQTT publishes/subscribes missing). The runtime classes (`MQTTGenericInput` / `MQTTGenericOutput`) registered cleanly on tmp configs, but full round-trip with the real alarm wasn't validated. **Phase 7 task**: once ROPAM is re-synced, follow the runbook below to validate the full path.

### Runbook — configure ROPAM via the new UI (Phase 7 validation)

1. **Re-sync the ROPAM alarm** so it publishes/subscribes on its expected topics again (`n64/99/in{1..N}`, `n64/99/temp{1..N}`, `n64/99/status`, `n64/99/out_{1..N}`).
2. **Open BoneIO UI** at `http://192.168.1.22:8091/` (Caddy proxy — for Node-RED tab) and go to **Settings → Remote Devices**.
3. **Add a remote device**:
   * `id: alarm_ropam`, `name: ROPAM Alarm`, `protocol: mqtt`
   * Click **🔍 Scan broker** in the MQTT Settings section, pattern `n64/99/#`, duration 10s — confirm you see all the expected topics with classified types (binary for `in*`, json for `temp*` and `status`).
   * Save.
4. **Add binary-sensor inputs** (Settings → Remote Inputs):
   * For each `n64/99/in{N}`: Add new, pick `alarm_ropam` (auto-sets `remote_source: mqtt`), the form will swap `input_id` for the MQTT fields. Fill `topic: n64/99/inN`, leave `value_template` as default (`{{ value }}`), `payload_on: 1`, `payload_off: 0`. Mode: binary_sensor.
   * Use the test field with payload `1` or `0` to confirm the preview goes green with the right TRUE/FALSE badge.
5. **Add sensor inputs** for `temp*` JSON payloads:
   * For each `n64/99/temp{N}`: Add new, `topic: n64/99/tempN`, `value_template: {{ value_json.val }}`, mode: binary_sensor (or sensor if/when a non-bool extraction is supported by the registrar). Open scan dialog → click the row → click `val` in the JSON tree to auto-fill the template.
   * For `fail` flag of the same temp: separate `remote_input` with same topic, `value_template: {{ value_json.fail }}`, `payload_on: 1`, `payload_off: 0`.
6. **Add `status.zones[0]` flag** (and similar):
   * `topic: n64/99/status`, `value_template: {{ value_json.zones[0] }}`, `payload_on: 1`, `payload_off: 0`.
   * Or AC status: `{{ value_json.ac }}` with same payload mapping.
7. **Add output for relay control**:
   * Settings → Remote Outputs → Add new → `alarm_ropam` device → form swaps to command-topic mode.
   * `topic: n64/99/out_1/cmd`, `command_template: {{ state }}`, `state_topic: n64/99/out_1`, `state_value_template: {{ value }}`, `state_payload_on: 1`, `state_payload_off: 0`.
   * QoS 0, retain off.
8. **Validate end-to-end**:
   * Use `mosquitto_pub -h 192.168.1.4 -u homeassistant -P <pwd> -t n64/99/in1 -m 1` and watch the boneIO log/UI — the input should toggle to active immediately.
   * From boneIO UI, toggle the remote output ON — `mosquitto_sub -h 192.168.1.4 -u ... -t 'n64/99/out_1/+' -v` should see the published command on `out_1/cmd`.
   * If state_topic is wired up, ROPAM republishing `1` on `n64/99/out_1` should pull the boneIO output back in sync.

**If anything in this flow fails** — most likely places to investigate (in order):
1. Topic mismatch (ROPAM publishes `in_1` vs `in1`, or `temp_1` vs `temp1`) — scan output is authoritative, use exactly what the scan shows.
2. JSON payload structure differs from expected (`{"val":6.5,...}` vs `{"value":6.5}`) — open inspector, click in the tree, regenerate template.
3. Cerberus validation reject — drop `/home/boneio/boneio/config.yaml.cache.pkl` and restart so the new schema is re-validated.
4. MQTT subscribe overlap — `MQTTGenericInput` and an existing static subscription on the same topic conflict (one callback per topic key in current bus). Workaround documented in `scanner.py`: use device-specific topic prefixes instead of `#`.

**Commits this session (on `feat/expansion-board`, pushed to fork)**:
* `24a3c40` — `feat(remote_mqtt): scaffold modules/remote_mqtt foundation`
* `8b4af6c` — `feat(remote_mqtt): MQTT topic scanner + POST /api/mqtt/scan endpoint`
* `3c20007` — `feat(remote_mqtt): MqttScanDialog + Scan broker button in RemoteDeviceForm`
* `4ffc39b` — `feat(remote_mqtt): Jinja2 template engine + JSON inspector with live preview`
* `0ec5d61` — `feat(remote_mqtt): MQTTGenericInput — wire generic MQTT topics into InputManager`
* `c1ba5b9` — `feat(remote_mqtt): MQTTGenericOutput — publish commands to arbitrary MQTT topics`
* `0d57bd3` — `feat(remote_mqtt): topic+template form fields for remote inputs/outputs`

**Open follow-ups** (added to task list):
* Phase 7 hardware E2E once ROPAM is re-synced
* Build/inject script POC (task #22) — still deferred, threshold not yet reached.

---

## 2026-05-17 (later) — Pivot to ESPHome-style device-centric pattern

**Why this pivot**: The Phase 0-6 design was *topic-centric* — each `remote_input` row declared its own topic + value_template + payload_on/off inline. User feedback: "stworzyliśmy coś dziwnego" — every other remote device (ESPHome, WLED, boneIO black) is *device-centric*: the device declares its entity catalog, then `remote_inputs` / `remote_outputs` reference entries by `device_id + input_id`. The dropdown UX users expect when adding a remote input (pick from a list of entities the device exposes) didn't work for MQTT because nothing was declared on the device.

**What changed**:

* `boneio/schema/remote_devices.yaml` — for `protocol: mqtt`, the device's `mqtt` block now accepts:
  - `topic_prefix` (display/scope hint)
  - `inputs: [{id, name, topic, value_template, payload_on, payload_off, qos}]`
  - `outputs: [{id, name, topic, command_template, state_topic, state_value_template, state_payload_on/off, qos, retain, output_type}]`

  These extend the existing `{id, name}` schema for boneIO-style devices — the extra fields are simply unused when `device_type=boneio_black`.

* `boneio/schema/remote_inputs.yaml` / `remote_outputs.yaml` — dropped the inline mqtt fields (topic, value_template, payload_*, command_template, state_*, qos, retain). Pure routing rows now: `device_id + input_id/output_id + actions/mode/area/...` — identical to ESPHome remote inputs.

* `boneio/modules/remote_mqtt/input.py` / `output.py` — `setup_remote_input/output` now look up topic + template + payload mapping by `device_id + input_id/output_id` on the remote device's catalog (`_find_device_input` / `_find_device_output`). Friendly log when the device or referenced id is missing.

* `frontend/src/components/UISettings/RemoteInputForm.tsx` / `RemoteOutputForm.tsx` — dropped the topic-centric swap. Standard input_id / output_id dropdown reused; for MQTT devices the option list comes from `selectedDevice.mqtt.inputs` / `.mqtt.outputs` (parallel to ESPHome's `_discovered_binary_sensors`). Hint shows "managed on the device" below the dropdown.

* `frontend/src/components/UISettings/modules/remote_mqtt/components/MqttDeviceEntitiesEditor.tsx` (new) — rendered inside `RemoteDeviceForm.tsx` when `device_type=generic`. Two editable tables (Inputs + Outputs) plus a "Scan & import" workflow: scan dialog opens with the device's topic_prefix, user multi-selects topics, system imports them as inputs with auto-classified templates (`{{ value }}` + `payload_on: "1"` / `payload_off: "0"` for binary, `{{ value_json }}` for JSON, etc.).

* Removed `MqttRemoteInputFields.tsx` + `MqttRemoteOutputFields.tsx` — no longer needed.

* `frontend/src/types/config.ts` — extended `RemoteDeviceEntity.mqtt` with the new `topic_prefix` + `inputs[]` + richer `outputs[]` shapes.

* Polish: id-uniqueness validation in `MqttDeviceEntitiesEditor` (duplicate IDs highlighted red, row tinted, tooltip explains); proper translations for all editor UI strings (en/pl, ~14 keys each).

**What's preserved**: scanner endpoint + UI dialog (now powers Scan & import), Jinja2 evaluator + live preview backend, `MQTTGenericInput` / `MQTTGenericOutput` runtime classes, `MqttTopicDispatcher` (multi-subscriber per topic — now more relevant since one device may have many inputs pointing at the same topic with different templates).

**Verified end-to-end on BoneIO**: tmp `generic_mqtt` device + `remote_inputs` row → service registered `"Registered MQTT remote input 'pivot_test_input' (device=pivot_test_device/ping_in, topic=boneio_test/ping)"` and `"MQTTGenericInput 'pivot_test_input' subscribed to topic 'boneio_test/ping'"` — confirms the device-catalog lookup path works correctly. Test config reverted after.

**Commits**:
* `c0ceb22` — `refactor(remote_mqtt): pivot to device-centric ESPHome-style pattern`
* `437ebd8` — `polish(remote_mqtt): id uniqueness + translations + WORK_LOG pivot rationale`

**Upstream status note**: boneIO has pushed v1.4.0dev3 + v1.4.0dev4 (commits `957a7bd..8f1a21c`) — merged in `ce3d42a`. Module pattern paid off:
* **Zero conflicts** in `modules/expander/` (5 files) and `modules/remote_mqtt/` (8 files) — all 24 module-owned files survived untouched. ~3500 lines of our logic, no manual work needed.
* **6 conflicts**, all small + predictable, all in injection-point files: `schema/remote_outputs.yaml` (kept BOTH our generic-mqtt note AND their momentary/interlock fields), `locales/{en,pl}/common.json` (JSON namespace merge), `SectionContent.tsx` (3 lines: kept mcp23017 prop + savedOutputs extension), `OutputForm.tsx` (kept our `advancedTabContent` extracted-const — DRY), `RemoteOutputForm.tsx` (bigger: adopted their TabsBox restructure, re-applied our MQTT dropdown section + "managed-on-device" hint).
* **Bonus for free**: `MQTTGenericOutput` extends `RemoteOutputBase`, so it now inherits upstream's new `momentary_turn_on/off`, `adjustable_duration`, `interlock_group`, etc. automatically — no module change required. User configures these on the remote_output row; runtime classes pick them up via inheritance.

**Post-merge live verification on BoneIO**:
* Service active, Hypercorn :8090 returns HTTP 200
* `POST /api/mqtt/scan` → 200 (scanner module)
* `POST /api/mqtt/test-template` → 200 (Jinja2 evaluator)
* `POST /api/config/expander` → 422 (route registered, validates payload — both modules wired through)

**Merge commit**: `ce3d42a` on `feat/expansion-board`. Branch now contains 14 commits since base `957a7bd`. The injection-point list above is the runbook for the next upstream merge.

---

## Runbook — next upstream merge

When boneIO releases the next dev tag (1.4.0dev3, 1.4.0, 1.5.x …), follow this. The
goal: pull their changes, re-apply ours, deploy, ship — without re-inventing the wheel.

### Step 1 — pull upstream

```bash
git checkout dev-debian13
git pull origin dev-debian13            # fast-forwards to upstream HEAD
git log --oneline HEAD ^feat/expansion-board | head -30   # what's new
```

### Step 2 — merge into our feature branch

```bash
git checkout feat/expansion-board
git merge dev-debian13                   # produces merge commit; expect SMALL conflicts
git status                               # see unmerged paths
```

### Step 3 — resolve conflicts (the predictable ones)

Conflicts will almost always land at our **7 injection sites**. For each, the goal
is to **keep upstream's new structure** and **re-apply our 1-2 line injection** in
the right place. Our injection points are marked by comments — search for them:

| File | Our injection (marker to look for) |
|------|-------------------------------------|
| `frontend/.../BoneIOForm.tsx` | `import { ExpanderManager } from './modules/expander';` + `<ExpanderManager allOutputs={...} />` after `{/* Expansion board — fully encapsulated module */}` |
| `frontend/.../OutputForm.tsx` | `import { McpHardwareFields, EXPANDER_BOARDS, EXPANDER_OUTPUT_PREFIX, isExpanderOutput, type ExpanderBoardType } from './modules/expander';` + `<McpHardwareFields ... />` call |
| `frontend/.../ArrayTableWidget.tsx` | `import { OutputAddButton, isExpanderOutput, useOutputKind, EXPANDER_OUTPUT_PREFIX } from './modules/expander';` + `<OutputAddButton ... />` + `const outputKind = useOutputKind(editingItem);` |
| `frontend/.../Mcp23017Form.tsx` | `import { MCP_ADDRESS_OPTIONS, MANAGED_EXPANDER_IDS, DEFAULT_ADDRESSES, DEFAULT_ADDRESS_INTEGERS, isExpanderOutput, ... } from './modules/expander';` |
| `frontend/.../helpers/itemValidation.ts` | `import { getOutputStats, isExpanderOutput } from '../modules/expander';` + `isExpanderOutput(dataToSave)` in output validation |
| `frontend/.../tables/OutputTable.tsx` | `import { isExpanderOutput } from '../modules/expander';` + `isExpanderOutput(item)` for badge |
| `frontend/.../components/SectionContent.tsx` | Just `mcp23017` prop passed through to BoneIOForm (no expander call here) |
| `boneio/core/config/yaml_util.py` | `from boneio.modules.expander import split_outputs_for_includes, dedup_outputs_prefer_named` + the 4-line split-write block in `update_config_section()` |
| `boneio/webui/app.py` | `from boneio.modules.expander import register_routes as register_expander_routes` + `register_expander_routes(app)` at end of router registration |
| `boneio/webui/routes/config.py` | Nothing (endpoints moved to module) — if upstream re-introduces an expander endpoint there, decide whether to remove and keep ours |

Tip: `git diff fbe2140..HEAD -- <file>` shows exactly what our refactor put there.

### Step 4 — verify with the anti-duplicate checklist

After resolving conflicts, run these greps to catch any inline duplicates upstream
might have re-introduced (e.g. a fresh `startsWith('EX_')` they added):

```bash
# Must return empty (with the SHIM files exception in #2 — that's intentional)
grep -rn "startsWith.*EX_\|startswith.*EX_" frontend/src/ boneio/ \
  --include="*.ts" --include="*.tsx" --include="*.py" 2>/dev/null \
  | grep -v "modules/expander" | grep -v "__pycache__"

grep -rn "'0x20'.*'0x21'.*'0x22'" frontend/src/ \
  --include="*.ts" --include="*.tsx" 2>/dev/null \
  | grep -v "modules/expander"

grep -rn "^output:.*!include" boneio/ --include="*.py" 2>/dev/null \
  | grep -v "modules/expander" | grep -v "__pycache__"

grep -rn "useState.*outputKind\|setOutputKind" frontend/src/ \
  --include="*.ts" --include="*.tsx" 2>/dev/null

grep -rn "any\[\]" frontend/src/components/UISettings/modules/ \
  --include="*.ts" --include="*.tsx" 2>/dev/null
```

If anything new pops up, fix it (replace with module helper) before committing.

### Step 5 — build chain

```bash
cd frontend && npx tsc --noEmit && npm run build
cd .. && python3 -c "from boneio.bonecli import main; print('bonecli ok')"
python3 -c "from boneio.modules.expander.yaml_util import is_expander_output; print('module ok')"
```

### Step 6 — finalise merge commit

```bash
git commit                # opens editor with merge message; summarise conflicts resolved
git push fork feat/expansion-board
```

### Step 7 — deploy + smoke test

```bash
./deploy_backend.sh                              # full rsync of boneio/ + service restart
sshpass -p '...' ssh boneio@192.168.1.22 "systemctl is-active boneio.service"
curl -sS http://192.168.1.22:8090/ -o /dev/null -w "HTTP %{http_code}\n"
```

Then in UI (`localhost:5173`): regression suite — Add/Remove Expander, edit EX_OUT_*,
badge "expander", dropdown counters, plus a quick poke at any NEW upstream features
to confirm they work.

### Edge cases the module pattern still can't dodge

1. **Upstream renames a file we inject into.** Git marks it as renamed+modified, our
   injection lands in the wrong place or gets dropped. Recovery: `git log --follow`
   the old path, re-apply the injection to the new file.
2. **Upstream changes a function signature we depend on** (e.g. `update_config_section()`
   gets new args). Our backend module helper call breaks. Recovery: adapt the module's
   call site to the new signature; the module's INTERNAL logic stays unchanged.
3. **Upstream ships their own version of our feature** (e.g. their own expander UI).
   Decide: remove ours, merge concepts, or keep both with namespacing. Module isolation
   makes "remove ours" trivial (`rm -rf modules/expander/` + revert injection lines).
4. **Upstream changes Cerberus schema in a way that rejects our EX_* outputs**. Recovery:
   add schema overrides in `boneio/modules/expander/schema_patches.py` (new file, not
   yet built) and apply during boot.

### Threshold for investing in build/inject automation (task #22)

Stop doing manual merges and build the inject script if **any of**:
- More than 2 of our 7 injection points conflict in a single upstream release
- Upstream renames an injection-point file (high-friction recovery)
- We add a 2nd module (e.g. cloud_sync) — automation amortises across modules
- We start managing 3+ branches (e.g. dev + stable backport)

Until then: manual merges with this runbook are cheaper than maintaining a patch system.

---

## How to update this log

After each meaningful work block (typically end of a session, or when finishing a phase):

1. **Update "Active scope"** — current task, phase status table
2. **Append to "Timeline"** — new dated entry with:
   - Goal of the session
   - What was done (✅ bullets)
   - Any decisions made / patterns introduced
   - Current state at end (so next session picks up cleanly)
3. **Mention any new files of architectural significance** in "Architecture decisions"
4. **Don't delete history** — append, don't rewrite. Old entries are evidence of why decisions were made.

Update this file **even if user didn't ask** — it's the persistent context source. Memory pointer
to it in `~/.claude/projects/.../memory/project_work_log.md`.
