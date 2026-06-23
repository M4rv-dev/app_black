"""Public API for the remote_mqtt module.

Provides scanning + Jinja2-based value extraction for arbitrary MQTT
devices that don't follow boneIO's topic convention (e.g. ROPAM alarm
panels publishing ``n64/88/temp1 = {"val": 6.5, ...}``).

Core boneIO files MUST import only from this module's public API.
Internal restructuring of the module never breaks consumers.

Note on lazy loading: ``register_routes`` (and any FastAPI / jinja2
dependants) are imported lazily via ``__getattr__`` so pure helpers
load without pulling FastAPI.
"""

from __future__ import annotations

from typing import Any

from boneio.modules.remote_mqtt.scanner import (
    PayloadType,
    ScanResult,
    infer_payload_type,
    scan_topics,
)
from boneio.modules.remote_mqtt.template import (
    coerce_bool,
    evaluate,
    try_parse_json,
)

# Import manager_integration eagerly so _register_self() runs and this module
# is registered in ModuleRegistry at import time (required for plugin discovery).
from boneio.modules.remote_mqtt import manager_integration as _integration  # noqa: F401

__all__ = [
    "PayloadType",
    "ScanResult",
    "infer_payload_type",
    "scan_topics",
    "coerce_bool",
    "evaluate",
    "try_parse_json",
    # Lazy-loaded (touch RemoteInputBase / FastAPI / jinja2 only on access):
    "register_routes",
    "MQTTGenericInput",
    "MQTTGenericOutput",
    "setup_remote_input",
    "cleanup_remote_inputs",
    "setup_remote_output",
    "cleanup_remote_outputs",
    "MQTTGenericSensor",
    "setup_remote_sensor",
    "cleanup_remote_sensors",
]


def __getattr__(name: str) -> Any:
    """Lazy load FastAPI / RemoteInputBase / RemoteOutputBase dependants on first access."""
    if name == "register_routes":
        from boneio.modules.remote_mqtt.routes import register_routes
        return register_routes
    if name == "MQTTGenericInput":
        from boneio.modules.remote_mqtt.input import MQTTGenericInput
        return MQTTGenericInput
    if name == "setup_remote_input":
        from boneio.modules.remote_mqtt.input import setup_remote_input
        return setup_remote_input
    if name == "cleanup_remote_inputs":
        from boneio.modules.remote_mqtt.input import cleanup_remote_inputs
        return cleanup_remote_inputs
    if name == "MQTTGenericOutput":
        from boneio.modules.remote_mqtt.output import MQTTGenericOutput
        return MQTTGenericOutput
    if name == "setup_remote_output":
        from boneio.modules.remote_mqtt.output import setup_remote_output
        return setup_remote_output
    if name == "cleanup_remote_outputs":
        from boneio.modules.remote_mqtt.output import cleanup_remote_outputs
        return cleanup_remote_outputs
    if name == "MQTTGenericSensor":
        from boneio.modules.remote_mqtt.sensor import MQTTGenericSensor
        return MQTTGenericSensor
    if name == "setup_remote_sensor":
        from boneio.modules.remote_mqtt.sensor import setup_remote_sensor
        return setup_remote_sensor
    if name == "cleanup_remote_sensors":
        from boneio.modules.remote_mqtt.sensor import cleanup_remote_sensors
        return cleanup_remote_sensors
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _remote_output_effective_id(entry: dict) -> str | None:
    """Return the effective ID the backend uses to register a remote output.

    Mirrors the convention seen in journal logs ("Registered MQTT remote
    output 'alarm_ropam_out6'") — explicit ``id`` wins, otherwise compose
    ``f'{device_id}_{output_id}'``. Returns ``None`` if neither is usable.
    """
    explicit_id = entry.get("id")
    if isinstance(explicit_id, str) and explicit_id:
        return explicit_id
    device_id = entry.get("device_id")
    output_id = entry.get("output_id")
    if isinstance(device_id, str) and device_id and isinstance(output_id, str) and output_id:
        return f"{device_id}_{output_id}"
    return None


def enrich_config_response(config_data: dict) -> None:
    """Add ``boneio_output`` alias to remote outputs in GET /api/config.

    Although `remote_outputs:` is an upstream-owned section (ESPHome / MQTT /
    WLED / CAN), upstream's own OutputGroupForm filters by
    ``output.boneio_output`` and silently drops every remote output from
    the group-member picker. Until that's fixed upstream, we attach an
    ephemeral ``boneio_output`` alias to each remote output entry so the
    existing filter naturally includes them. The alias is removed in
    ``strip_for_save`` so the YAML written back to disk stays clean.

    We enrich the entire section (regardless of ``remote_source``), not
    only mqtt ones — the user expects *all* remote outputs to appear in
    group pickers, and the alias semantics (effective registration ID)
    are identical for every source.
    """
    remotes = config_data.get("remote_outputs")
    if not isinstance(remotes, list):
        return
    for entry in remotes:
        if not isinstance(entry, dict):
            continue
        if entry.get("boneio_output"):
            continue
        alias = _remote_output_effective_id(entry)
        if alias is not None:
            entry["boneio_output"] = alias


def strip_for_save(section: str, data: Any) -> None:
    """Reverse the ``boneio_output`` alias before remote_outputs is written
    back to YAML — same idempotent contract as the expander module."""
    if section != "remote_outputs" or not isinstance(data, list):
        return
    for entry in data:
        if not isinstance(entry, dict):
            continue
        expected = _remote_output_effective_id(entry)
        if expected is not None and entry.get("boneio_output") == expected:
            entry.pop("boneio_output", None)
