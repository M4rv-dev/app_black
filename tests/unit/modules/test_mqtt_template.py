"""Unit tests for boneio.modules.remote_mqtt.template.

Covers:
- evaluate(): Jinja2 rendering with raw and JSON payloads
- coerce_bool(): boolean coercion from rendered strings
- try_parse_json(): best-effort JSON parsing
"""
from __future__ import annotations

import pytest

from boneio.modules.remote_mqtt.template import coerce_bool, evaluate, try_parse_json


# ---------------------------------------------------------------------------
# try_parse_json
# ---------------------------------------------------------------------------

class TestTryParseJson:
    """Tests for try_parse_json helper."""

    def test_valid_dict(self):
        """Valid JSON object is parsed to dict."""
        result = try_parse_json('{"val": 3.5, "fail": 0}')
        assert result == {"val": 3.5, "fail": 0}

    def test_valid_list(self):
        """Valid JSON array is parsed to list."""
        assert try_parse_json("[1, 2, 3]") == [1, 2, 3]

    def test_plain_string_returns_none(self):
        """Plain string (non-JSON) returns None."""
        assert try_parse_json("ON") is None

    def test_numeric_string_returns_none(self):
        """Numeric-only payload returns None — not a JSON object/array."""
        assert try_parse_json("3.5") is None

    def test_empty_string_returns_none(self):
        """Empty payload returns None."""
        assert try_parse_json("") is None

    def test_malformed_json_returns_none(self):
        """Malformed JSON returns None instead of raising."""
        assert try_parse_json("{bad json}") is None


# ---------------------------------------------------------------------------
# evaluate()
# ---------------------------------------------------------------------------

class TestEvaluate:
    """Tests for Jinja2 template evaluation."""

    def test_passthrough_raw_value(self):
        """{{ value }} returns payload unchanged."""
        assert evaluate("{{ value }}", "ON") == "ON"

    def test_json_field_extraction(self):
        """value_json.field extracts from JSON payload."""
        result = evaluate("{{ value_json.val }}", '{"val": 3.5, "fail": 0}')
        assert result == "3.5"

    def test_json_nested_field(self):
        """Nested JSON path works."""
        result = evaluate("{{ value_json.a.b }}", '{"a": {"b": "hello"}}')
        assert result == "hello"

    def test_conditional_template(self):
        """Conditional Jinja2 expression renders correctly."""
        tpl = '{{ "1" if value == "ON" else "0" }}'
        assert evaluate(tpl, "ON") == "1"
        assert evaluate(tpl, "OFF") == "0"

    def test_state_template_for_command(self):
        """command_template style: state variable resolves via value alias."""
        tpl = '{{ "1" if value == "ON" else "0" }}'
        assert evaluate(tpl, "ON") == "1"

    def test_invalid_template_raises_value_error_on_parse(self):
        """Malformed template raises ValueError."""
        with pytest.raises(ValueError, match="Template error"):
            evaluate("{{ unclosed", "payload")

    def test_strict_undefined_raises_value_error(self):
        """Accessing nonexistent JSON key raises ValueError (StrictUndefined)."""
        with pytest.raises(ValueError, match="Template error"):
            evaluate("{{ value_json.nonexistent }}", '{"val": 1}')

    def test_value_json_none_for_plain_payload(self):
        """value_json is None for non-JSON payloads — accessing .val raises ValueError."""
        with pytest.raises(ValueError, match="Template error"):
            evaluate("{{ value_json.val }}", "plain_string")

    def test_integer_result_as_string(self):
        """Numeric result is returned as string."""
        result = evaluate("{{ value_json.count }}", '{"count": 42}')
        assert result == "42"


# ---------------------------------------------------------------------------
# coerce_bool()
# ---------------------------------------------------------------------------

class TestCoerceBool:
    """Tests for boolean coercion from rendered template strings."""

    # -- Standard ON/OFF strings --

    def test_on_string(self):
        """'ON' coerces to True."""
        assert coerce_bool("ON") is True

    def test_off_string(self):
        """'OFF' coerces to False."""
        assert coerce_bool("OFF") is False

    def test_case_insensitive_on(self):
        """'on', 'On', 'ON' all coerce to True."""
        for s in ("on", "On", "ON"):
            assert coerce_bool(s) is True

    def test_case_insensitive_off(self):
        """'off', 'Off', 'OFF' all coerce to False."""
        for s in ("off", "Off", "OFF"):
            assert coerce_bool(s) is False

    # -- ROPAM-style 1/0 --

    def test_numeric_one(self):
        """'1' coerces to True (ROPAM/generic device convention)."""
        assert coerce_bool("1") is True

    def test_numeric_zero(self):
        """'0' coerces to False (ROPAM/generic device convention)."""
        assert coerce_bool("0") is False

    # -- true/false boolean strings --

    def test_true_string(self):
        """'true' coerces to True."""
        assert coerce_bool("true") is True

    def test_false_string(self):
        """'false' coerces to False."""
        assert coerce_bool("false") is False

    # -- open/closed (valve/cover) --

    def test_open_string(self):
        """'open' coerces to True."""
        assert coerce_bool("open") is True

    def test_closed_string(self):
        """'closed' coerces to False."""
        assert coerce_bool("closed") is False

    # -- custom payload_on / payload_off --

    def test_custom_payload_on(self):
        """Exact match on payload_on takes priority over fallback."""
        assert coerce_bool("LOCK", payload_on="LOCK") is True

    def test_custom_payload_off(self):
        """Exact match on payload_off takes priority over fallback."""
        assert coerce_bool("UNLOCK", payload_off="UNLOCK") is False

    def test_custom_payload_on_no_match(self):
        """Non-matching value with only payload_on set returns None."""
        assert coerce_bool("UNKNOWN", payload_on="LOCK") is None

    def test_ambiguous_returns_none(self):
        """Unrecognised string returns None."""
        assert coerce_bool("MAYBE") is None

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace is stripped before matching."""
        assert coerce_bool("  on  ") is True
        assert coerce_bool("  0  ") is False
