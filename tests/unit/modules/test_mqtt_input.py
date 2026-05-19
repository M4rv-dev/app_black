"""Integration tests for MQTTGenericInput._on_message pipeline.

Tests the full payload → template → coerce_bool → state-change pipeline
without touching the MQTT bus or real event loop subscriptions.

We call _on_message directly (bypassing subscribe()) so no dispatcher
mock is needed — we're testing business logic, not wiring.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from boneio.modules.remote_mqtt.input import MQTTGenericInput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_input(
    *,
    value_template: str = "{{ value }}",
    payload_on: str | None = None,
    payload_off: str | None = None,
    mode: str = "binary_sensor",
) -> MQTTGenericInput:
    """Build a MQTTGenericInput with all external deps mocked.

    subscribe() is patched to a no-op so the test doesn't need a real
    dispatcher or MQTT bus.
    """
    bus = MagicMock()
    event_bus = MagicMock()
    event_bus.fire = MagicMock()

    with patch.object(MQTTGenericInput, "_subscribe", new_callable=AsyncMock):
        inp = MQTTGenericInput(
            id="test_in",
            name="Test Input",
            pin="mqtt:home/state/in1",
            topic="home/state/in1",
            message_bus=bus,
            value_template=value_template,
            payload_on=payload_on,
            payload_off=payload_off,
            event_bus=event_bus,
            actions={},
            mode=mode,
        )
    return inp


# ---------------------------------------------------------------------------
# _on_message pipeline
# ---------------------------------------------------------------------------

class TestMQTTGenericInputOnMessage:
    """Tests for the payload-processing pipeline in _on_message."""

    @pytest.mark.asyncio
    async def test_plain_on_payload_sets_state_true(self):
        """'ON' payload coerces to True and updates _state."""
        inp = _make_input()
        await inp._on_message("home/state/in1", "ON")
        assert inp._state is True

    @pytest.mark.asyncio
    async def test_plain_off_payload_sets_state_false(self):
        """'OFF' payload coerces to False and updates _state."""
        inp = _make_input()
        inp._state = True
        await inp._on_message("home/state/in1", "OFF")
        assert inp._state is False

    @pytest.mark.asyncio
    async def test_numeric_1_sets_state_true(self):
        """ROPAM-style '1' payload sets state to True."""
        inp = _make_input()
        await inp._on_message("home/state/in1", "1")
        assert inp._state is True

    @pytest.mark.asyncio
    async def test_numeric_0_sets_state_false(self):
        """ROPAM-style '0' payload sets state to False."""
        inp = _make_input()
        inp._state = True
        await inp._on_message("home/state/in1", "0")
        assert inp._state is False

    @pytest.mark.asyncio
    async def test_json_template_extraction(self):
        """value_template extracts field from JSON payload."""
        inp = _make_input(value_template="{{ value_json.state }}")
        await inp._on_message("home/state/in1", '{"state": "ON", "brightness": 255}')
        assert inp._state is True

    @pytest.mark.asyncio
    async def test_custom_payload_on(self):
        """custom payload_on string maps to True."""
        inp = _make_input(payload_on="LOCKED")
        await inp._on_message("home/state/in1", "LOCKED")
        assert inp._state is True

    @pytest.mark.asyncio
    async def test_custom_payload_off(self):
        """custom payload_off string maps to False."""
        inp = _make_input(payload_off="UNLOCKED")
        inp._state = True
        await inp._on_message("home/state/in1", "UNLOCKED")
        assert inp._state is False

    @pytest.mark.asyncio
    async def test_unknown_payload_does_not_change_state(self):
        """Unrecognised payload is dropped — state unchanged."""
        inp = _make_input()
        inp._state = True
        await inp._on_message("home/state/in1", "GARBAGE_XYZ")
        assert inp._state is True

    @pytest.mark.asyncio
    async def test_bad_template_does_not_raise(self):
        """Template error is caught by _on_message — state stays False, no exception."""
        inp = _make_input(value_template="{{ value_json.missing_key }}")
        # evaluate() now wraps all Jinja2 exceptions in ValueError,
        # so _on_message catches it, logs a warning, and returns cleanly.
        await inp._on_message("home/state/in1", '{"other": 1}')
        assert inp._state is False

    @pytest.mark.asyncio
    async def test_inverted_true_inverts_coerced_value(self):
        """inverted=True flips the coerced bool before updating state."""
        bus = MagicMock()
        event_bus = MagicMock()
        event_bus.fire = MagicMock()
        with patch.object(MQTTGenericInput, "_subscribe", new_callable=AsyncMock):
            inp = MQTTGenericInput(
                id="inv_in",
                name="Inverted",
                pin="mqtt:home/state/inv",
                topic="home/state/inv",
                message_bus=bus,
                event_bus=event_bus,
                actions={},
                mode="binary_sensor",
                inverted=True,
            )
        await inp._on_message("home/state/inv", "ON")
        # inverted: ON → coerced True → after inversion → False
        assert inp._state is False


# ---------------------------------------------------------------------------
# Repeated message deduplication
# ---------------------------------------------------------------------------

class TestMQTTGenericInputDeduplication:
    """Same-value messages should not emit redundant events."""

    @pytest.mark.asyncio
    async def test_same_state_twice_no_duplicate_event(self):
        """Second identical payload does not fire another event."""
        inp = _make_input()
        inp._event_bus.fire = MagicMock()

        await inp._on_message("home/state/in1", "1")
        count_after_first = inp._event_bus.fire.call_count

        await inp._on_message("home/state/in1", "1")
        count_after_second = inp._event_bus.fire.call_count

        # Event count must not increase on duplicate state
        assert count_after_second == count_after_first
