"""MQTTGenericSensor — numeric/string sensor sourced from an arbitrary MQTT topic.

Lightweight class (does NOT extend ``BaseSensor`` — that base class is built
for poll-based hardware sensors with AsyncUpdater + Filter, which doesn't
apply here). On each incoming payload we:

1. Render ``value_template`` (Jinja2 with ``value`` / ``value_json`` context).
2. Try to coerce the result to ``float``; otherwise keep it as string.
3. Publish ``{"state": <value>}`` to the local sensor topic so HA discovery
   (which sets ``state_topic`` to that topic + ``value_template``
   ``{{ value_json.state }}``) picks it up.
4. Emit ``SensorEvent`` on the EventBus so the WebSocket / frontend updates.

Pattern mirrors ``MQTTGenericInput`` (subscribe via MqttTopicDispatcher, log
each step for diagnosability) and ``MQTTGenericOutput`` (factory function +
``cleanup_remote_sensors`` for unregister).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from boneio.const import SENSOR, STATE
from boneio.models import SensorState
from boneio.models.events import SensorEvent
from boneio.modules.remote_mqtt.dispatcher import get_dispatcher
from boneio.modules.remote_mqtt.template import evaluate

if TYPE_CHECKING:
    from boneio.core.manager import Manager

_LOGGER = logging.getLogger(__name__)


def _coerce_number(rendered: str) -> float | str:
    """Try to convert rendered template output to float; fall back to string."""
    if rendered is None:
        return ""
    s = str(rendered).strip()
    if not s:
        return ""
    try:
        return float(s)
    except (TypeError, ValueError):
        return s


class MQTTGenericSensor:
    """Subscribe to one MQTT topic and expose its value as a boneIO sensor."""

    is_remote: bool = True

    def __init__(
        self,
        *,
        id: str,
        name: str,
        device_id: str,
        sensor_id: str,
        topic: str,
        message_bus: Any,
        event_bus: Any,
        topic_prefix: str,
        value_template: str = "{{ value }}",
        unit_of_measurement: str | None = None,
        device_class: str | None = None,
        state_class: str | None = None,
        area: str | None = None,
        show_in_ha: bool = False,
    ) -> None:
        self._id = id
        self._name = name
        self._device_id = device_id
        self._sensor_id = sensor_id
        self._topic = topic
        self._message_bus = message_bus
        self._event_bus = event_bus
        self._topic_prefix = topic_prefix
        self._value_template = value_template
        self._unit_of_measurement = unit_of_measurement or ""
        self._device_class = device_class
        self._state_class = state_class
        self.area: str | None = area
        self.show_in_ha = show_in_ha

        self._state: float | str | None = None
        self._timestamp: float | None = None
        self._subscribed = False

        # Local boneIO sensor topic — HA discovery points its state_topic here.
        self._send_topic = f"{topic_prefix}/{SENSOR}/{id}"

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._subscribe(), name=f"mqtt-sensor-{self._id}-subscribe")
        except RuntimeError:
            _LOGGER.warning(
                "MQTTGenericSensor '%s' instantiated outside event loop — subscription deferred",
                self._id,
            )

    # ------------------------------------------------------------------
    # Subscribe / unsubscribe
    # ------------------------------------------------------------------

    async def _subscribe(self) -> None:
        try:
            dispatcher = get_dispatcher(self._message_bus)
            await dispatcher.subscribe(
                self._topic, self._on_message, f"sensor:{self._id}"
            )
            self._subscribed = True
            _LOGGER.info(
                "MQTTGenericSensor '%s' subscribed to topic '%s' (template=%r)",
                self._id, self._topic, self._value_template,
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error(
                "MQTTGenericSensor '%s' failed to subscribe to '%s': %s",
                self._id, self._topic, exc,
            )

    async def unsubscribe(self) -> None:
        if not self._subscribed:
            return
        try:
            dispatcher = get_dispatcher(self._message_bus)
            await dispatcher.unsubscribe(self._topic, f"sensor:{self._id}")
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "MQTTGenericSensor '%s' failed to unsubscribe from '%s': %s",
                self._id, self._topic, exc,
            )
        self._subscribed = False

    # ------------------------------------------------------------------
    # Message handler
    # ------------------------------------------------------------------

    async def _on_message(self, topic: str, payload: str) -> None:
        try:
            rendered = evaluate(self._value_template, payload)
        except ValueError as exc:
            _LOGGER.warning(
                "MQTTGenericSensor '%s' template %r raised on payload %r: %s",
                self._id, self._value_template, payload, exc,
            )
            return

        value = _coerce_number(rendered)
        self._state = value
        self._timestamp = time.time()

        # Publish to local sensor topic so HA discovery picks it up.
        try:
            self._message_bus.send_message(
                topic=self._send_topic,
                payload={STATE: value},
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "MQTTGenericSensor '%s' failed to republish to '%s': %s",
                self._id, self._send_topic, exc,
            )

        # Emit SensorEvent on the EventBus → WebSocket → frontend.
        self._event_bus.trigger_event(SensorEvent(
            entity_id=self._id,
            state=SensorState(
                id=self._id,
                name=self._name,
                state=value,
                unit=self._unit_of_measurement,
                timestamp=self._timestamp,
            ),
        ))

        _LOGGER.info(
            "MQTTGenericSensor '%s' RX topic=%s rendered=%r value=%r",
            self._id, topic, rendered, value,
        )

    # ------------------------------------------------------------------
    # Properties (read by SensorManager / HA discovery / WebSocket)
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> float | str | None:
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        return self._unit_of_measurement

    @property
    def device_class(self) -> str | None:
        return self._device_class

    @property
    def state_class(self) -> str | None:
        return self._state_class

    @property
    def last_timestamp(self) -> float | None:
        return self._timestamp

    @property
    def send_topic(self) -> str:
        return self._send_topic

    def __repr__(self) -> str:
        return (
            f"<MQTTGenericSensor id={self._id!r} device={self._device_id!r} "
            f"sensor={self._sensor_id!r} topic={self._topic!r} state={self._state!r}>"
        )


# ----------------------------------------------------------------------
# Factory + cleanup (called from manager.register_remote_sensors)
# ----------------------------------------------------------------------


def _find_device_sensor(manager: "Manager", device_id: str, sensor_id: str) -> dict | None:
    """Resolve a sensor declaration on the remote device's mqtt.sensors catalog."""
    full_cfg = manager._config_helper.get_config()
    devices_cfg = full_cfg.get("remote_devices", [])
    device_cfg = next((d for d in devices_cfg if d.get("id") == device_id), None)
    if not device_cfg:
        return None
    sensors = device_cfg.get("mqtt", {}).get("sensors", [])
    return next((s for s in sensors if s.get("id") == sensor_id), None)


def setup_remote_sensor(
    *,
    entity_id: str,
    cfg: dict[str, Any],
    manager: "Manager",
    sensors_dict: dict[str, Any],
    ha_discovery_fn: Any = None,
) -> bool:
    """Build, register, and (if enabled) HA-discover a single MQTT remote sensor.

    Lookups the topic + value_template + unit + device_class on the device's
    ``mqtt.sensors[]`` catalog. ``remote_sensors`` row only carries routing
    (device_id, sensor_id) + optional overrides (name, area, unit, device_class).

    Returns True on success, False on validation failure.
    """
    device_id = cfg.get("device_id")
    sensor_id = cfg.get("sensor_id")
    if not device_id or not sensor_id:
        _LOGGER.warning(
            "Skipping mqtt remote sensor '%s': missing device_id or sensor_id",
            entity_id,
        )
        return False

    sensor_def = _find_device_sensor(manager, device_id, sensor_id)
    if not sensor_def:
        _LOGGER.warning(
            "MQTT remote sensor '%s': sensor '%s' not found on device '%s' "
            "(remote_devices[%s].mqtt.sensors). Add it on the device first.",
            entity_id, sensor_id, device_id, device_id,
        )
        return False

    topic = sensor_def.get("topic")
    if not topic:
        _LOGGER.warning(
            "MQTT remote sensor '%s': device sensor '%s/%s' has no `topic` "
            "configured — edit the device's sensor definition.",
            entity_id, device_id, sensor_id,
        )
        return False

    # Display name precedence: remote_sensors override > device sensor name > entity_id
    name = str(cfg.get("name") or sensor_def.get("name") or entity_id)
    # Unit / device_class / state_class precedence: remote_sensors override > device default
    unit = cfg.get("unit_of_measurement") or sensor_def.get("unit_of_measurement")
    device_class = cfg.get("device_class") or sensor_def.get("device_class")
    state_class = cfg.get("state_class") or sensor_def.get("state_class")

    mqtt_sensor = MQTTGenericSensor(
        id=entity_id,
        name=name,
        device_id=device_id,
        sensor_id=sensor_id,
        topic=topic,
        message_bus=manager.message_bus,
        event_bus=manager._event_bus,
        topic_prefix=manager._config_helper.topic_prefix,
        value_template=sensor_def.get("value_template", "{{ value }}"),
        unit_of_measurement=unit,
        device_class=device_class,
        state_class=state_class,
        area=cfg.get("area"),
        show_in_ha=bool(cfg.get("show_in_ha", False)),
    )

    sensors_dict[entity_id] = mqtt_sensor

    if cfg.get("show_in_ha") and ha_discovery_fn is not None:
        ha_discovery_fn(mqtt_sensor)

    _LOGGER.info(
        "Registered MQTT remote sensor '%s' (device=%s/%s, topic=%s, unit=%s, device_class=%s)",
        entity_id, device_id, sensor_id, topic, unit or "—", device_class or "—",
    )
    return True


async def cleanup_remote_sensors(sensors_dict: dict[str, Any]) -> None:
    """Unsubscribe MQTT topic listeners for every MQTTGenericSensor.

    Called from ``Manager.unregister_remote_sensors`` so subscriptions don't
    leak across reloads.
    """
    tasks = [
        v.unsubscribe()
        for v in sensors_dict.values()
        if isinstance(v, MQTTGenericSensor)
    ]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
        _LOGGER.info("Unsubscribed %d MQTT remote sensor(s)", len(tasks))
