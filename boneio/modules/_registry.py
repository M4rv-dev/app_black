"""BoneIO module plugin registry.

Each extension module registers itself here at import time via
``ModuleRegistry.register()``.  Core boneIO code (``manager.py``,
``app.py``) calls the registry hooks instead of importing individual
modules directly — this keeps upstream core files free of hard-coded
module references.

Lifecycle hooks a module can implement (all optional):

``register_routes(app)``
    Called once at app startup to mount FastAPI routers.

``setup(manager)``
    Called after the Manager has finished its initial boot sequence.

``teardown_on_devices_reload(manager)``
    Called before remote devices are reloaded so the module can clean up
    subscriptions, state, etc.

``setup_on_devices_reload(manager)``
    Called after remote devices (and inputs/outputs) have been
    re-registered so the module can re-attach its logic.

``try_setup_output(manager, out_cfg, entity_id) -> bool``
    Called for each remote output row during ``register_remote_outputs``.
    Return ``True`` to claim the row (skip the default device-manager
    flow), ``False`` to pass.

``make_reload_handler(manager, section) -> Callable | None``
    Called to obtain a section-specific async reload coroutine.
    Return ``None`` if the module does not handle that section.
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI
    from boneio.core.manager.manager import Manager

_LOGGER = logging.getLogger(__name__)

_HOOKS = (
    "register_routes",
    "setup",
    "teardown_on_devices_reload",
    "setup_on_devices_reload",
    "try_setup_output",
    "try_setup_input",
    "cleanup_inputs",
    "make_reload_handler",
    "enrich_config_response",
    "strip_for_save",
)


class ModuleRegistry:
    """Singleton registry for BoneIO extension modules."""

    _instance: "ModuleRegistry | None" = None

    def __init__(self) -> None:
        self._modules: list[Any] = []

    @classmethod
    def get(cls) -> "ModuleRegistry":
        """Return the process-wide singleton, creating it on first call."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, module: Any) -> None:
        """Register an extension module object (typically a module's ``__init__``).

        ``module`` must expose at least one of the documented hook attributes.
        Unknown attributes are silently ignored so older modules remain compatible
        when new hooks are added.
        """
        self._modules.append(module)
        _LOGGER.debug("ModuleRegistry: registered module %s", getattr(module, "__name__", module))

    # ------------------------------------------------------------------
    # Hook dispatchers
    # ------------------------------------------------------------------

    def register_routes(self, app: "FastAPI") -> None:
        """Call ``register_routes(app)`` on every registered module that has it."""
        for mod in self._modules:
            fn = getattr(mod, "register_routes", None)
            if fn is not None:
                try:
                    fn(app)
                    _LOGGER.debug("ModuleRegistry: register_routes OK — %s", mod.__name__)
                except Exception:
                    _LOGGER.exception("ModuleRegistry: register_routes FAILED — %s", mod.__name__)

    def setup(self, manager: "Manager") -> None:
        """Call ``setup(manager)`` on every registered module that has it."""
        for mod in self._modules:
            fn = getattr(mod, "setup", None)
            if fn is not None:
                try:
                    fn(manager)
                    _LOGGER.debug("ModuleRegistry: setup OK — %s", mod.__name__)
                except Exception:
                    _LOGGER.exception("ModuleRegistry: setup FAILED — %s", mod.__name__)

    def teardown_on_devices_reload(self, manager: "Manager") -> None:
        """Call ``teardown_on_devices_reload(manager)`` on all modules."""
        for mod in self._modules:
            fn = getattr(mod, "teardown_on_devices_reload", None)
            if fn is not None:
                try:
                    fn(manager)
                except Exception:
                    _LOGGER.exception("ModuleRegistry: teardown_on_devices_reload FAILED — %s", mod.__name__)

    def setup_on_devices_reload(self, manager: "Manager") -> None:
        """Call ``setup_on_devices_reload(manager)`` on all modules."""
        for mod in self._modules:
            fn = getattr(mod, "setup_on_devices_reload", None)
            if fn is not None:
                try:
                    fn(manager)
                except Exception:
                    _LOGGER.exception("ModuleRegistry: setup_on_devices_reload FAILED — %s", mod.__name__)

    def try_setup_input(
        self,
        manager: "Manager",
        custom_id: str,
        ri_cfg: dict,
        inputs_dict: dict,
        parsed_actions: dict,
        ha_discovery_fn: Any,
    ) -> "bool | None":
        """Ask each module to claim a remote input row.

        Returns the registration result if a module claims it (``remote_source``
        matches), so the caller can skip the default ESPHome flow.
        Returns ``None`` if no module handles the row.
        """
        for mod in self._modules:
            fn = getattr(mod, "try_setup_input", None)
            if fn is not None:
                try:
                    result = fn(manager, custom_id, ri_cfg, inputs_dict, parsed_actions, ha_discovery_fn)
                    if result is not None:
                        return result
                except Exception:
                    _LOGGER.exception("ModuleRegistry: try_setup_input FAILED — %s", mod.__name__)
        return None

    def cleanup_inputs(self, inputs_dict: dict) -> None:
        """Ask each module to clean up its owned inputs before unregistration.

        Called from ``RemoteInputRegistrar.unregister_all`` so modules can
        flush subscriptions, timers, etc. before the dict entries are deleted.
        """
        for mod in self._modules:
            fn = getattr(mod, "cleanup_inputs", None)
            if fn is not None:
                try:
                    fn(inputs_dict)
                except Exception:
                    _LOGGER.exception("ModuleRegistry: cleanup_inputs FAILED — %s", mod.__name__)

    def try_setup_output(self, manager: "Manager", out_cfg: dict, entity_id: str) -> bool:
        """Ask each module to claim a remote output row.

        Returns ``True`` as soon as one module claims it; ``False`` if none do.
        """
        for mod in self._modules:
            fn = getattr(mod, "try_setup_output", None)
            if fn is not None:
                try:
                    if fn(manager, out_cfg, entity_id):
                        return True
                except Exception:
                    _LOGGER.exception("ModuleRegistry: try_setup_output FAILED — %s", mod.__name__)
        return False

    def enrich_config_response(self, config_data: dict) -> None:
        """Give each module a chance to add derived/virtual fields to the
        parsed config before it's returned by ``GET /api/config``.

        Modules mutate ``config_data`` in place — typically by adding alias
        fields like ``boneio_output`` to sections they own (e.g. expansion
        outputs, remote outputs) so the upstream UI components can filter
        them without any module-specific knowledge.

        Counterpart: ``strip_for_save`` removes the same fields before the
        config is persisted back to YAML, keeping user-edited files clean.
        """
        for mod in self._modules:
            fn = getattr(mod, "enrich_config_response", None)
            if fn is not None:
                try:
                    fn(config_data)
                except Exception:
                    _LOGGER.exception("ModuleRegistry: enrich_config_response FAILED — %s", mod.__name__)

    def strip_for_save(self, section: str, data: Any) -> None:
        """Give each module a chance to strip derived fields from a section
        payload before it's written to YAML via ``PUT /api/config/{section}``.

        Mirrors ``enrich_config_response`` — modules mutate ``data`` in place
        to remove fields they had injected on the GET path, so round-trip
        save→load doesn't accumulate auto-generated cruft in the user's
        YAML files.
        """
        for mod in self._modules:
            fn = getattr(mod, "strip_for_save", None)
            if fn is not None:
                try:
                    fn(section, data)
                except Exception:
                    _LOGGER.exception("ModuleRegistry: strip_for_save FAILED — %s", mod.__name__)

    def make_reload_handler(self, manager: "Manager", section: str):
        """Return the first non-None reload handler for ``section``, or ``None``."""
        for mod in self._modules:
            fn = getattr(mod, "make_reload_handler", None)
            if fn is not None:
                try:
                    handler = fn(manager, section)
                    if handler is not None:
                        return handler
                except Exception:
                    _LOGGER.exception("ModuleRegistry: make_reload_handler FAILED — %s", mod.__name__)
        return None


def _autodiscover() -> None:
    """Import every subpackage of ``boneio.modules`` so modules self-register.

    Called once at the bottom of this file.  Modules that want to participate
    must call ``ModuleRegistry.get().register(their_integration_module)`` from
    their own ``__init__.py`` or ``manager_integration.py``.
    """
    import boneio.modules as _pkg
    for info in pkgutil.iter_modules(_pkg.__path__):
        if info.name.startswith("_"):
            continue
        try:
            importlib.import_module(f"boneio.modules.{info.name}")
        except Exception:
            _LOGGER.exception("ModuleRegistry: failed to import boneio.modules.%s", info.name)


_autodiscover()
