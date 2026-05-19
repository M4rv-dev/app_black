# BoneIO App Black — Coding Guidelines

> **Dla ludzi i modeli językowych.**  
> Ten dokument opisuje czym jest projekt, jak jest zorganizowany, jak pisać
> nowy kod i kiedy alarmować użytkownika o zmianach w upstream.

---

## 1. Czym jest ten projekt

**`app_black`** to **fork + warstwa rozszerzeń** na projekt
[boneIO-eu/app_black](https://github.com/boneIO-eu/app_black).

- **upstream (`origin`)** — oficjalny boneIO, zarządzany przez boneIO-eu.
  Regularnie dostaje nowe funkcje i bugfixy.  
- **nasz fork (`fork`)** — zawiera wszystkie zmiany tego projektu.
  Gałąź robocza: `feat/expansion-board`.

Celem jest **maksymalna izolacja naszych zmian od upstream core**, żeby
`git merge origin/dev-debian13` wymagał jak najmniej ręcznej pracy.

---

## 2. Struktura — co nasze, co upstream

```
boneio/
  core/          ← UPSTREAM. Nie modyfikować bez powodu.
  hardware/      ← UPSTREAM. Nie modyfikować bez powodu.
  components/    ← UPSTREAM. Nie modyfikować bez powodu.
  modules/       ← NASZE. Tu żyją wszystkie rozszerzenia.
    _registry.py          ← Plugin registry (nasz glue layer)
    remote_mqtt/          ← Moduł: zdalne urządzenia MQTT (ROPAM, etc.)
    expander/             ← Moduł: płyta rozszerzeń MCP23017
  webui/
    routes/      ← UPSTREAM (większość). Nasze routes są w modules/*/routes.py
    app.py       ← MINIMALNIE zmodyfikowany (tylko 2 linie dla registry)

frontend/
  src/
    components/UISettings/modules/  ← NASZE komponenty UI per moduł
    locales/                        ← NASZE tłumaczenia (pl/en)
    hooks/useWebSocket.ts           ← ZMODYFIKOWANY (dodane typy)

tasks.py         ← NASZ plik deploy (invoke)
tools/           ← NASZE narzędzia
tests/           ← NASZE testy (unit + integracyjne)
```

### Pliki upstream core z naszymi modyfikacjami (ryzykowne przy merge)

| Plik | Co zmieniliśmy | Ryzyko przy merge |
|------|---------------|-------------------|
| `boneio/core/manager/manager.py` | Zamieniono importy `remote_mqtt` na `ModuleRegistry` | Niskie — 1 pattern |
| `boneio/core/config/yaml_util.py` | `_deep_merge_schema`, `_apply_module_schema_extensions` | Średnie |
| `boneio/webui/app.py` | 2 linie zastąpione `ModuleRegistry.get().register_routes(app)` | Niskie |
| `frontend/src/hooks/useWebSocket.ts` | Dodane typy dla remote outputs | Niskie |
| `frontend/src/locales/*/common.json` | Dodane klucze tłumaczeń | Niskie |
| `frontend/src/types/config.ts` | Dodane typy remote_mqtt | Niskie |

---

## 3. Zasada rozszerzania — Plugin Registry

Każdy nowy moduł **NIE modyfikuje** `manager.py` ani `app.py` bezpośrednio.
Zamiast tego rejestruje się przez `ModuleRegistry`:

```python
# boneio/modules/moj_modul/manager_integration.py

def setup(manager): ...
def teardown_on_devices_reload(manager): ...
def setup_on_devices_reload(manager): ...
def register_routes(app): ...
def try_setup_output(manager, out_cfg, entity_id) -> bool: ...
def make_reload_handler(manager, section): ...

# Na końcu pliku:
def _register_self():
    from boneio.modules._registry import ModuleRegistry
    import boneio.modules.moj_modul.manager_integration as _self
    ModuleRegistry.get().register(_self)

_register_self()
```

`_registry.py` automatycznie importuje wszystkie podpakiety `boneio/modules/`
przy starcie — wystarczy że `_register_self()` jest w `manager_integration.py`.

### Hooki (wszystkie opcjonalne)

| Hook | Kiedy wywoływany |
|------|-----------------|
| `register_routes(app)` | Raz przy starcie FastAPI |
| `setup(manager)` | Po zakończeniu `Manager.__init__` |
| `teardown_on_devices_reload(manager)` | Przed przeładowaniem remote_devices |
| `setup_on_devices_reload(manager)` | Po przeładowaniu remote_devices |
| `try_setup_output(manager, out_cfg, entity_id) → bool` | Per-wiersz remote_outputs; zwróć `True` żeby przejąć wiersz |
| `make_reload_handler(manager, section) → coroutine\|None` | Per-sekcja config reload |

### Schemat YAML per moduł

Zamiast edytować `boneio/schema/schema.yaml`:

```yaml
# boneio/modules/moj_modul/schema_extension.yaml
# Zawartość jest deep-merged do głównego schematu przy starcie.
remote_devices:
  schema:
    schema:
      moj_klucz:
        type: dict
        ...
```

---

## 4. Zasady kodowania

- **Python 3.13** (projekt migruje z 3.7).
- **Early returns** zamiast głębokiego zagnieżdżenia.
- **Dokumentacja** na każdej nowej funkcji i klasie (docstring po `def`).
- **Logi po angielsku** (`_LOGGER.info("...")` — zawsze EN).
- **Importy na górze pliku** — nigdy w środku funkcji bez uzasadnienia
  (jedynym uzasadnieniem jest unikanie circular imports lub lazy-loading FastAPI).
- **Testy** dla każdego nowego modułu w `tests/unit/modules/` lub `tests/unit/core/`.
- **Brak `sshpass`** — SSH używa klucza; hasło tylko przez `_ssh_sudo`.

---

## 5. Proces merge z upstream

```bash
git fetch origin
git merge origin/dev-debian13
```

### Co zwykle konflikuje

1. `boneio/core/manager/manager.py` — sprawdź czy upstream nie dodał
   własnych hardkodowanych `from boneio.modules.X import ...`.
   Jeśli tak, **zastąp je wywołaniem `ModuleRegistry`**.

2. `boneio/core/config/yaml_util.py` — sprawdź czy upstream nie dodał
   własnej obsługi schema extensions. Jeśli tak, usuń naszą implementację
   i dostosuj `_registry.py`.

3. `frontend/src/locales/*/common.json` — merge kluczy ręcznie,
   **nigdy nie nadpisuj całego pliku**.

4. `boneio/webui/app.py` — zachowaj 2 linie `ModuleRegistry` zamiast
   wracać do hardkodowanych importów.

---

## 6. ⚠️ Kiedy model językowy MUSI zgłosić alert użytkownikowi

> Model powinien przeszukać diff upstream przed każdą sesją lub gdy user
> wklei changelog / commit list z upstream.

### Sytuacje wymagające alertu

**A. Upstream implementuje funkcję którą my już mamy**

Przykłady do sprawdzenia:
- upstream dodaje `boneio/modules/remote_mqtt/` — mamy to samo →
  **ALERT: "upstream zaimplementował remote_mqtt — rozważ wycofanie naszego modułu"**
- upstream dodaje własny `ModuleRegistry` lub plugin system →
  **ALERT: "upstream ma własny plugin system — sprawdź kompatybilność z naszym _registry.py"**
- upstream dodaje schema auto-merge →
  **ALERT: "upstream ma schema_extension obsługę — możemy usunąć nasz _apply_module_schema_extensions"**
- upstream dodaje ROPAM/alarm support →
  **ALERT: "upstream wspiera ROPAM — czy nasze command_template workaroundy są nadal potrzebne?"**

**B. Upstream modyfikuje plik który my też zmodyfikowaliśmy**

Pliki do monitorowania (patrz tabela w §2).  
Przy każdym merge sprawdź `git diff origin/dev-debian13 -- <plik>`.

**C. Upstream usuwa lub przemianowuje funkcję którą wywołujemy**

Np. zmiana sygnatury `Manager.__init__` lub reorganizacja `OutputManager`.

### Jak sprawdzić upstream changelog

```bash
git log origin/dev-debian13..HEAD --oneline          # nasze commity
git log HEAD..origin/dev-debian13 --oneline          # nowe w upstream
git diff origin/dev-debian13 --name-only             # zmienione pliki
git diff origin/dev-debian13 -- boneio/modules/      # czy upstream ma moduły
```

---

## 7. Workflow dla nowej funkcji

1. **Sprawdź upstream** czy nie robi tego samego (`git log`, GitHub Issues).
2. **Stwórz `boneio/modules/<nazwa>/`** z `__init__.py` i `manager_integration.py`.
3. **Schema** → `schema_extension.yaml` w katalogu modułu.
4. **Frontend** → `frontend/src/components/UISettings/modules/<nazwa>/`.
5. **Tłumaczenia** → dodaj klucze do `pl/common.json` i `en/common.json`.
6. **Testy** → `tests/unit/modules/test_<nazwa>*.py`.
7. **NIE modyfikuj** `manager.py`, `app.py` — używaj hooków registry.
8. **Deploy** → `inv deploy --fast` + `inv smoke`.

---

## 8. Środowisko deweloperskie

```bash
# Deploy na urządzenie
inv deploy            # pełny (snapshot + deploy + healthcheck)
inv deploy --fast     # tylko rsync + restart (bez snapshot)
inv smoke             # HTTP + WebSocket healthcheck

# Testy (uruchamiają się NA urządzeniu przez SSH)
inv test                                    # testy core
inv test --path tests/unit/modules/        # testy modułów
inv test --path tests/unit/core/test_timeperiod.py

# Lokalnie (tylko pliki bez pydantic/gpiod)
python3 -m pytest tests/unit/core/test_timeperiod.py
python3 -m pytest tests/unit/core/test_filter.py
python3 -m pytest tests/unit/modules/test_mqtt_template.py

# Frontend
cd frontend && npm run dev                 # dev server
npm run build                              # build produkcyjny
```

---

## 9. Mapa modułów (aktualna)

| Moduł | Opis | Status |
|-------|------|--------|
| `remote_mqtt` | Zdalne wejścia/wyjścia/sensory przez MQTT (ROPAM, inne) | Aktywny |
| `expander` | Płyta rozszerzeń z MCP23017 | Aktywny |

Nowe moduły → dodać do tej tabeli.
