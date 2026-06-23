"""Manager-side integration of the remote_mqtt module.

This file owns *all* manager-level lifecycle for generic MQTT remote inputs,
outputs and sensors — registration on startup, unregistration on reload,
HA discovery emission, and reload-dispatcher entries.

Upstream ``boneio/core/manager/manager.py`` calls this module via three small
hooks (``setup``, ``teardown``, ``reload_section``) so that all MQTT-aware
code stays inside ``boneio/modules/remote_mqtt/``. Pattern: copy of how the
expander module isolates its own concerns.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from boneio.core.manager import Manager

_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Sensors — full lifecycle
# ----------------------------------------------------------------------

def register_remote_sensors(manager: "Manager") -> None:
    """Register remote sensors from the ``remote_sensors`` config section.

    Currently only MQTT generic sensors are supported. Each entry maps a
    device + sensor_id to a topic/value_template defined on the device's
    ``mqtt.sensors[]`` catalog and exposes it as a local boneIO sensor
    (with optional HA discovery).
    """
    config = manager._config_helper.get_config()
    remote_sensors_config: list[dict] = config.get("remote_sensors", [])
    if not remote_sensors_config:
        return

    from boneio.const import SENSOR
    from boneio.integration.homeassistant import ha_availabilty_message
    from boneio.modules.remote_mqtt import setup_remote_sensor

    def _publish_ha(sensor: Any) -> None:
        extra: dict[str, Any] = {"value_template": "{{ value_json.state }}"}
        if sensor.unit_of_measurement:
            extra["unit_of_measurement"] = sensor.unit_of_measurement
        if sensor.device_class:
            extra["device_class"] = sensor.device_class
        if sensor.state_class:
            extra["state_class"] = sensor.state_class
        payload = ha_availabilty_message(
            id=sensor.id,
            name=sensor.name,
            entity_type="sensor",
            device_type=SENSOR,
            config_helper=manager._config_helper,
            area=sensor.area,
            **extra,
        )
        manager.publish_ha_discovery(id=sensor.id, ha_type="sensor", payload=payload)

    count = 0
    for cfg in remote_sensors_config:
        remote_source = cfg.get("remote_source", "mqtt")
        if remote_source != "mqtt":
            _LOGGER.warning(
                "remote_sensors: only remote_source='mqtt' is supported (got %r)",
                remote_source,
            )
            continue
        device_id = cfg.get("device_id", "")
        sensor_id = cfg.get("sensor_id", "")
        entity_id = cfg.get("id", "").strip()
        if not entity_id:
            entity_id = f"{device_id}_{sensor_id}".replace("-", "_")
        if entity_id in manager.sensors._remote_sensors:
            _LOGGER.warning(
                "Remote sensor '%s' already registered, skipping duplicate",
                entity_id,
            )
            continue
        if setup_remote_sensor(
            entity_id=entity_id,
            cfg=cfg,
            manager=manager,
            sensors_dict=manager.sensors._remote_sensors,
            ha_discovery_fn=_publish_ha,
        ):
            count += 1

    _LOGGER.info("Remote sensors registered: %d total", count)


def unregister_remote_sensors(manager: "Manager") -> None:
    """Unsubscribe and remove all remote sensors.

    Runs the async cleanup on a best-effort basis — if no loop is running
    we just clear the dict (subscriptions will be GC'd with the bus).
    """
    if not manager.sensors._remote_sensors:
        return
    from boneio.modules.remote_mqtt import cleanup_remote_sensors

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(cleanup_remote_sensors(manager.sensors._remote_sensors))
    except RuntimeError:
        _LOGGER.debug(
            "unregister_remote_sensors called without running loop — skipping unsubscribe"
        )
    manager.sensors._remote_sensors.clear()


async def reload_remote_sensors(manager: "Manager") -> None:
    """Reload only the remote_sensors section (called by reload dispatcher)."""
    _LOGGER.info("Reloading remote sensors configuration")
    unregister_remote_sensors(manager)
    register_remote_sensors(manager)


# ----------------------------------------------------------------------
# Outputs — single dispatch point used by Manager.register_remote_outputs
# ----------------------------------------------------------------------

def try_setup_mqtt_input(
    manager: "Manager",
    custom_id: str,
    ri_cfg: dict,
    inputs_dict: dict,
    parsed_actions: dict,
    ha_discovery_fn: Any,
) -> bool | None:
    """Try to set up an MQTT generic input for this remote_inputs row.

    Returns the registration result if the row was handled (i.e.
    ``remote_source == "mqtt"``), so the caller skips the ESPHome flow.
    Returns ``None`` if the row is not ours — caller continues normal flow.
    """
    if ri_cfg.get("remote_source") != "mqtt":
        return None
    from boneio.modules.remote_mqtt import setup_remote_input

    return setup_remote_input(
        custom_id=custom_id,
        cfg=ri_cfg,
        manager=manager,
        inputs_dict=inputs_dict,
        parsed_actions=parsed_actions,
        ha_discovery_fn=ha_discovery_fn,
    )


def cleanup_mqtt_for_registrar(inputs_dict: dict) -> None:
    """Schedule unsubscribe of MQTTGenericInput entries before they're dropped.

    Called from ``RemoteInputRegistrar.unregister_all`` so module-owned MQTT
    subscriptions are torn down cleanly on reload. Best-effort — if there's
    no running event loop we skip (subscriptions get GC'd with the bus).
    """
    try:
        import asyncio
        from boneio.modules.remote_mqtt import cleanup_remote_inputs

        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(cleanup_remote_inputs(inputs_dict))
    except Exception:  # noqa: BLE001
        pass


def try_setup_mqtt_output(manager: "Manager", out_cfg: dict, entity_id: str) -> bool:
    """Try to set up an MQTT generic output for this remote_outputs row.

    Returns True if the row was handled (i.e. ``remote_source == "mqtt"``),
    so the caller skips the standard device-manager flow.
    """
    if out_cfg.get("remote_source") != "mqtt":
        return False
    from boneio.modules.remote_mqtt import setup_remote_output

    setup_remote_output(
        entity_id=entity_id,
        cfg=out_cfg,
        manager=manager,
        outputs_dict=manager.outputs._outputs,  # type: ignore[attr-defined]
    )
    return True


# ----------------------------------------------------------------------
# Top-level setup / teardown hooks (called from manager.py)
# ----------------------------------------------------------------------

def setup(manager: "Manager") -> None:
    """One-shot module setup — called once during Manager.__init__.

    Anything that needs to register on boot lives here.
    """
    register_remote_sensors(manager)


def teardown_on_devices_reload(manager: "Manager") -> None:
    """Clean up MQTT-owned state before remote_devices is reloaded."""
    unregister_remote_sensors(manager)


def setup_on_devices_reload(manager: "Manager") -> None:
    """Re-register MQTT-owned state after remote_devices is reloaded."""
    register_remote_sensors(manager)


def register_routes(app: object) -> None:
    """Mount FastAPI routers for the remote_mqtt module."""
    from boneio.modules.remote_mqtt.routes import register_routes as _register
    _register(app)


def try_setup_input(
    manager: "Manager",
    custom_id: str,
    ri_cfg: dict,
    inputs_dict: dict,
    parsed_actions: dict,
    ha_discovery_fn: Any,
) -> "bool | None":
    """Claim a remote input row if it belongs to this module (ModuleRegistry hook)."""
    return try_setup_mqtt_input(manager, custom_id, ri_cfg, inputs_dict, parsed_actions, ha_discovery_fn)


def cleanup_inputs(inputs_dict: dict) -> None:
    """Clean up module-owned inputs before unregistration (ModuleRegistry hook)."""
    cleanup_mqtt_for_registrar(inputs_dict)


def try_setup_output(manager: "Manager", out_cfg: dict, entity_id: str) -> bool:
    """Claim a remote output row if it belongs to this module."""
    return try_setup_mqtt_output(manager, out_cfg, entity_id)


def make_reload_handler(manager: "Manager", section: str):
    """Return an async reload coroutine for ``section``, or None."""
    if section == "remote_sensors":
        async def _handler():
            await reload_remote_sensors(manager)
        return _handler
    return None


# ---------------------------------------------------------------------------
# Self-registration — runs once when this module is first imported.
# ---------------------------------------------------------------------------

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

    Although ``remote_outputs:`` is an upstream-owned section (ESPHome / MQTT
    / WLED / CAN), upstream's OutputGroupForm filters group members by
    ``output.boneio_output`` — which remote outputs never carry — and so it
    silently drops every remote output from the picker. Until that's fixed
    upstream we attach a transient ``boneio_output`` alias here and strip it
    again on save (see ``strip_for_save``) so the YAML on disk stays clean.

    Enriches the entire section regardless of ``remote_source`` — the user
    expects *all* remote outputs in group pickers, and the alias semantics
    (effective registration ID) are identical for every source.
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


def strip_for_save(section: str, data) -> None:
    """Reverse the ``boneio_output`` alias before remote_outputs is written
    back to YAML — idempotent contract: only strip when value still equals
    the computed effective ID."""
    if section != "remote_outputs" or not isinstance(data, list):
        return
    for entry in data:
        if not isinstance(entry, dict):
            continue
        expected = _remote_output_effective_id(entry)
        if expected is not None and entry.get("boneio_output") == expected:
            entry.pop("boneio_output", None)


def _register_self() -> None:
    """Register this integration with the process-wide ModuleRegistry."""
    try:
        from boneio.modules._registry import ModuleRegistry
        import boneio.modules.remote_mqtt.manager_integration as _self
        ModuleRegistry.get().register(_self)
    except Exception:  # noqa: BLE001
        pass  # Registry not available in minimal test environments


_register_self()
