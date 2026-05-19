"""Unit tests for boneio.core.utils.filter.

Covers every filter operation in FILTERS dict and the Filter._apply_filters
pipeline: chaining, None propagation, unknown filter warning.
"""
from __future__ import annotations

import pytest

from boneio.core.utils.filter import FILTERS, Filter


# ---------------------------------------------------------------------------
# Individual filter functions (pure lambdas)
# ---------------------------------------------------------------------------

class TestFilterFunctions:
    """Each lambda in FILTERS behaves correctly in isolation."""

    def test_offset_positive(self):
        assert FILTERS["offset"](10.0, 2.0) == 12.0

    def test_offset_negative(self):
        assert FILTERS["offset"](10.0, -3.0) == 7.0

    def test_round_two_decimals(self):
        assert FILTERS["round"](3.14159, 2) == 3.14

    def test_round_zero_decimals(self):
        assert FILTERS["round"](3.7, 0) == 4.0

    def test_multiply_normal(self):
        assert FILTERS["multiply"](5.0, 2.0) == 10.0

    def test_multiply_zero_value_returns_zero(self):
        """multiply returns the falsy value (0) unchanged — not 0 * factor."""
        assert FILTERS["multiply"](0, 3.0) == 0

    def test_multiply_none_value_returns_none(self):
        """multiply(None, y) returns None because `x if x` is falsy for None."""
        assert FILTERS["multiply"](None, 3.0) is None

    def test_filter_out_match(self):
        """filter_out returns None when value equals threshold."""
        assert FILTERS["filter_out"](99.9, 99.9) is None

    def test_filter_out_no_match(self):
        assert FILTERS["filter_out"](10.0, 99.9) == 10.0

    def test_filter_out_greater_above(self):
        """filter_out_greater returns None when value > threshold."""
        assert FILTERS["filter_out_greater"](100.0, 50.0) is None

    def test_filter_out_greater_at_threshold(self):
        """filter_out_greater passes value exactly at threshold."""
        assert FILTERS["filter_out_greater"](50.0, 50.0) == 50.0

    def test_filter_out_lower_below(self):
        """filter_out_lower returns None when value < threshold."""
        assert FILTERS["filter_out_lower"](5.0, 10.0) is None

    def test_filter_out_lower_at_threshold(self):
        assert FILTERS["filter_out_lower"](10.0, 10.0) == 10.0

    def test_encode_temperature(self):
        """encode_temperature: (int(x * y) << 1) | 1."""
        result = FILTERS["encode_temperature"](25.0, 2.0)
        assert result == (int(25.0 * 2.0) << 1) | 1

    def test_firmware_version(self):
        """firmware_version: high byte = major, low byte = minor."""
        # version 1.5 → int = 0x0105
        raw = (1 << 8) | 5
        assert FILTERS["firmware_version"](raw, None) == "v1.5"


# ---------------------------------------------------------------------------
# Filter._apply_filters pipeline
# ---------------------------------------------------------------------------

class TestFilterApplyFilters:
    """Filter._apply_filters chains operations in order."""

    def _make_filter(self, filters: list) -> Filter:
        """Return a Filter instance with given _filters list."""
        f = Filter()
        f._filters = filters
        return f

    def test_single_offset(self):
        f = self._make_filter([{"offset": 5.0}])
        assert f._apply_filters(10.0) == 15.0

    def test_single_round(self):
        f = self._make_filter([{"round": 1}])
        assert f._apply_filters(3.567) == 3.6

    def test_chain_offset_then_round(self):
        """offset then round: 10.0 + 0.123 = 10.123 → round to 2dp = 10.12."""
        f = self._make_filter([{"offset": 0.123}, {"round": 2}])
        result = f._apply_filters(10.0)
        assert result == pytest.approx(10.12)

    def test_chain_multiply_then_offset(self):
        f = self._make_filter([{"multiply": 2.0}, {"offset": 1.0}])
        assert f._apply_filters(5.0) == 11.0

    def test_none_input_propagates(self):
        """None input short-circuits — result is None regardless of filters."""
        f = self._make_filter([{"offset": 5.0}, {"round": 1}])
        assert f._apply_filters(None) is None

    def test_filter_out_produces_none(self):
        """filter_out returning None stops further processing."""
        f = self._make_filter([{"filter_out": 99.9}, {"offset": 1.0}])
        # value == threshold → None → offset never applied
        assert f._apply_filters(99.9) is None

    def test_empty_filters_passthrough(self):
        f = self._make_filter([])
        assert f._apply_filters(42.0) == 42.0

    def test_explicit_filters_override_instance(self):
        """Passing filters= overrides self._filters."""
        f = self._make_filter([{"offset": 999.0}])
        result = f._apply_filters(10.0, filters=[{"offset": 1.0}])
        assert result == 11.0

    def test_unknown_filter_skipped_with_warning(self, caplog):
        """Unknown filter key logs a warning and skips that step."""
        import logging
        f = self._make_filter([{"nonexistent_filter": 1.0}, {"offset": 2.0}])
        with caplog.at_level(logging.WARNING):
            result = f._apply_filters(5.0)
        assert result == 7.0
        assert "nonexistent_filter" in caplog.text

    def test_filter_out_greater_in_pipeline(self):
        """filter_out_greater: returns None for values above threshold."""
        f = self._make_filter([{"filter_out_greater": 100.0}])
        assert f._apply_filters(150.0) is None
        assert f._apply_filters(50.0) == 50.0

    def test_filter_out_lower_in_pipeline(self):
        f = self._make_filter([{"filter_out_lower": 10.0}])
        assert f._apply_filters(5.0) is None
        assert f._apply_filters(15.0) == 15.0
