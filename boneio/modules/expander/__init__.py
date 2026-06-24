"""Public API for the expander module.

Core boneIO files MUST import only from this module — never reach into
``yaml_util`` or ``routes`` internals directly. This is the stable contract;
internal restructuring of the module never breaks consumers.

Note on lazy loading: ``register_routes`` is imported lazily via
``__getattr__`` because it pulls in FastAPI. Pure helpers (``is_expander_output``,
``split_outputs_for_includes``, ``dedup_outputs_prefer_named``,
``filter_out_expander``, ``EXPANDER_PREFIX``) load eagerly with no heavy deps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from boneio.modules.expander.yaml_util import (
    EXPANDER_PREFIX,
    dedup_outputs_prefer_named,
    filter_out_expander,
    is_expander_output,
    split_outputs_for_includes,
)

if TYPE_CHECKING:
    from boneio.modules.expander.routes import register_routes  # noqa: F401

__all__ = [
    "EXPANDER_PREFIX",
    "dedup_outputs_prefer_named",
    "filter_out_expander",
    "is_expander_output",
    "register_routes",
    "split_outputs_for_includes",
]


def __getattr__(name: str) -> Any:
    """Lazy load ``register_routes`` to keep FastAPI off the import path for pure helpers."""
    if name == "register_routes":
        from boneio.modules.expander.routes import register_routes
        return register_routes
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def enrich_config_response(config_data: dict) -> None:
    """Add ``boneio_output`` alias to expansion-board outputs in the GET /api/config response.

    Expansion outputs are defined as ``- id: EX_OUT_NN, kind: mcp, mcp_id:
    expander_left|expander_right, …`` (see expansion_board_output_*.yaml).
    They intentionally don't carry a ``boneio_output`` field because they're
    not wired to a board terminal — that field is upstream's marker for
    "this output references a physical board output".

    Upstream's OutputGroupForm filters by ``output.boneio_output``, so without
    this alias expansion outputs disappear from the group-member picker. We
    add ``boneio_output = id`` so the upstream filter naturally picks them
    up; the value is stripped back out in ``strip_for_save`` so it never
    persists to the user's YAML.

    Only mutates entries that don't already have ``boneio_output``, so
    board outputs (which carry both ``id`` and ``boneio_output``) are
    untouched.
    """
    outputs = config_data.get("output")
    if not isinstance(outputs, list):
        return
    for entry in outputs:
        if not isinstance(entry, dict):
            continue
        if entry.get("boneio_output"):
            continue
        if entry.get("kind") != "mcp":
            continue
        entry_id = entry.get("id")
        if entry_id and is_expander_output(entry):
            entry["boneio_output"] = entry_id


def strip_for_save(section: str, data: Any) -> None:
    """Remove the ``boneio_output`` alias we injected in ``enrich_config_response``.

    Only strips when the value still matches the entry's ``id`` *and* the
    entry passes ``is_expander_output`` — that way we never clobber a
    genuine board output that the user explicitly typed ``boneio_output:
    OUT_01`` for.
    """
    if section != "output" or not isinstance(data, list):
        return
    for entry in data:
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id")
        if (
            entry.get("kind") == "mcp"
            and entry_id
            and is_expander_output(entry)
            and entry.get("boneio_output") == entry_id
        ):
            entry.pop("boneio_output", None)


def _register_self() -> None:
    """Register this module with the process-wide ModuleRegistry."""
    try:
        import boneio.modules.expander as _self
        from boneio.modules._registry import ModuleRegistry
        ModuleRegistry.get().register(_self)
    except Exception:  # noqa: BLE001
        pass  # Registry not available in minimal test environments


_register_self()
