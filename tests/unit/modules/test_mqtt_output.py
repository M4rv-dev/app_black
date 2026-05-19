"""Integration tests for MQTTGenericOutput.

Covers:
- turn_on / turn_off publish correct payload to correct topic
- command_template rendering (default ON/OFF and custom 1/0)
- optimistic state update after publish
- state_topic feedback overrides optimistic state
- coerce_bool integration: 1/0 payloads update state correctly
- unrecognised state_topic payload is ignored (no state change)
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from boneio.modules.remote_mqtt.output import MQTTGenericOutput


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_bus() -> MagicMock:
    """Return a mock MessageBus with a spy on send_message."""
    bus = MagicMock()
    bus.send_message = MagicMock()
    return bus


def _make_event_bus() -> MagicMock:
    """Return a mock EventBus that silently accepts fire() calls."""
    eb = MagicMock()
    eb.fire = MagicMock()
    return eb


def _make_output(
    *,
    command_template: str = "{{ state }}",
    state_topic: str | None = None,
    state_value_template: str = "{{ value }}",
    state_payload_on: str | None = None,
    state_payload_off: str | None = None,
) -> tuple[MQTTGenericOutput, MagicMock]:
    """Build a MQTTGenericOutput with mocked bus and event bus.

    Returns the output instance and the bus mock so tests can assert
    on send_message calls.
    """
    bus = _make_bus()
    output = MQTTGenericOutput(
        id="test_out",
        name="Test Output",
        device_id="dev1",
        output_id="out1",
        remote_source="mqtt",
        event_bus=_make_event_bus(),
        output_type="switch",
        topic="home/cmd/out1",
        message_bus=bus,
        command_template=command_template,
        state_topic=state_topic,
        state_value_template=state_value_template,
        state_payload_on=state_payload_on,
        state_payload_off=state_payload_off,
    )
    return output, bus


# ---------------------------------------------------------------------------
# Publish behaviour
# ---------------------------------------------------------------------------

class TestMQTTGenericOutputPublish:
    """MQTTGenericOutput publishes correct payloads."""

    @pytest.mark.asyncio
    async def test_turn_on_publishes_on(self):
        """Default command_template: turn_on sends 'ON'."""
        output, bus = _make_output()
        await output.async_turn_on()
        bus.send_message.assert_called_once_with(
            topic="home/cmd/out1", payload="ON", retain=False, qos=0
        )

    @pytest.mark.asyncio
    async def test_turn_off_publishes_off(self):
        """Default command_template: turn_off sends 'OFF'."""
        output, bus = _make_output()
        await output.async_turn_off()
        bus.send_message.assert_called_once_with(
            topic="home/cmd/out1", payload="OFF", retain=False, qos=0
        )

    @pytest.mark.asyncio
    async def test_custom_template_turn_on_sends_1(self):
        """ROPAM-style template sends '1' for ON."""
        output, bus = _make_output(
            command_template='{{ "1" if state == "ON" else "0" }}'
        )
        await output.async_turn_on()
        bus.send_message.assert_called_once_with(
            topic="home/cmd/out1", payload="1", retain=False, qos=0
        )

    @pytest.mark.asyncio
    async def test_custom_template_turn_off_sends_0(self):
        """ROPAM-style template sends '0' for OFF."""
        output, bus = _make_output(
            command_template='{{ "1" if state == "ON" else "0" }}'
        )
        await output.async_turn_off()
        bus.send_message.assert_called_once_with(
            topic="home/cmd/out1", payload="0", retain=False, qos=0
        )

    @pytest.mark.asyncio
    async def test_topic_is_correct(self):
        """Payload goes to the configured topic, not a default one."""
        bus = _make_bus()
        output = MQTTGenericOutput(
            id="door",
            name="Door",
            device_id="ropam",
            output_id="out6",
            remote_source="mqtt",
            event_bus=_make_event_bus(),
            output_type="light",
            topic="n64/99/cmd/out/6",
            message_bus=bus,
            command_template='{{ "1" if state == "ON" else "0" }}',
        )
        await output.async_turn_on()
        topic_used = bus.send_message.call_args.kwargs["topic"]
        assert topic_used == "n64/99/cmd/out/6"

    @pytest.mark.asyncio
    async def test_retain_flag_forwarded(self):
        """retain=True is passed through to send_message."""
        output, bus = _make_output()
        output._retain = True
        await output.async_turn_on()
        assert bus.send_message.call_args.kwargs["retain"] is True

    @pytest.mark.asyncio
    async def test_qos_forwarded(self):
        """qos=1 is passed through to send_message."""
        output, bus = _make_output()
        output._qos = 1
        await output.async_turn_on()
        assert bus.send_message.call_args.kwargs["qos"] == 1


# ---------------------------------------------------------------------------
# Optimistic state
# ---------------------------------------------------------------------------

class TestMQTTGenericOutputOptimisticState:
    """After publish, state is updated optimistically (no state_topic needed)."""

    @pytest.mark.asyncio
    async def test_state_is_on_after_turn_on(self):
        """State transitions to ON after async_turn_on."""
        output, _ = _make_output()
        assert output.state == "OFF"
        await output.async_turn_on()
        assert output.state == "ON"

    @pytest.mark.asyncio
    async def test_state_is_off_after_turn_off(self):
        """State transitions to OFF after async_turn_off."""
        output, _ = _make_output()
        await output.async_turn_on()
        await output.async_turn_off()
        assert output.state == "OFF"

    @pytest.mark.asyncio
    async def test_toggle_on_then_off(self):
        """async_toggle flips ON → OFF correctly."""
        output, _ = _make_output()
        await output.async_turn_on()
        assert output.state == "ON"
        await output.async_toggle()
        assert output.state == "OFF"

    @pytest.mark.asyncio
    async def test_toggle_off_then_on(self):
        """async_toggle flips OFF → ON correctly."""
        output, _ = _make_output()
        assert output.state == "OFF"
        await output.async_toggle()
        assert output.state == "ON"


# ---------------------------------------------------------------------------
# State-topic feedback
# ---------------------------------------------------------------------------

class TestMQTTGenericOutputStateFeedback:
    """State-topic messages override local optimistic state."""

    @pytest.mark.asyncio
    async def test_state_feedback_on_payload(self):
        """Receiving '1' on state_topic sets state to ON."""
        output, _ = _make_output(state_topic="home/state/out1")
        await output._on_state_message("home/state/out1", "1")
        assert output.state == "ON"

    @pytest.mark.asyncio
    async def test_state_feedback_off_payload(self):
        """Receiving '0' on state_topic sets state to OFF."""
        output, _ = _make_output(state_topic="home/state/out1")
        await output.async_turn_on()
        await output._on_state_message("home/state/out1", "0")
        assert output.state == "OFF"

    @pytest.mark.asyncio
    async def test_state_feedback_on_off_strings(self):
        """'ON'/'OFF' strings on state_topic work without custom payload maps."""
        output, _ = _make_output(state_topic="home/state/out1")
        await output._on_state_message("home/state/out1", "ON")
        assert output.state == "ON"
        await output._on_state_message("home/state/out1", "OFF")
        assert output.state == "OFF"

    @pytest.mark.asyncio
    async def test_custom_payload_on_off(self):
        """Custom payload_on/off map to True/False state."""
        output, _ = _make_output(
            state_topic="home/state/out1",
            state_payload_on="LOCKED",
            state_payload_off="UNLOCKED",
        )
        await output._on_state_message("home/state/out1", "LOCKED")
        assert output.state == "ON"
        await output._on_state_message("home/state/out1", "UNLOCKED")
        assert output.state == "OFF"

    @pytest.mark.asyncio
    async def test_unknown_payload_ignored(self):
        """Unrecognised payload on state_topic does not change state."""
        output, _ = _make_output(state_topic="home/state/out1")
        await output.async_turn_on()
        state_before = output.state
        await output._on_state_message("home/state/out1", "UNKNOWN_GARBAGE")
        assert output.state == state_before

    @pytest.mark.asyncio
    async def test_json_state_value_template(self):
        """state_value_template extracts field from JSON state payload."""
        output, _ = _make_output(
            state_topic="home/state/out1",
            state_value_template="{{ value_json.state }}",
        )
        await output._on_state_message("home/state/out1", '{"state": "ON", "brightness": 128}')
        assert output.state == "ON"

    @pytest.mark.asyncio
    async def test_device_overrides_optimistic_state(self):
        """Real device reporting OFF overrides optimistic ON set by turn_on."""
        output, _ = _make_output(state_topic="home/state/out1")
        await output.async_turn_on()
        assert output.state == "ON"
        # Device rejects the command and reports OFF
        await output._on_state_message("home/state/out1", "0")
        assert output.state == "OFF"
