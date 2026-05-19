"""Unit tests for boneio.core.utils.timeperiod.

Covers TimePeriod construction, unit conversions, arithmetic comparisons,
__str__ / __repr__, as_dict, as_timedelta, and the parse_time_to_seconds /
parse_time_to_ms helpers.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from boneio.core.utils.timeperiod import (
    TimePeriod,
    TimePeriodMicroseconds,
    TimePeriodMilliseconds,
    TimePeriodMinutes,
    TimePeriodSeconds,
    parse_time_to_ms,
    parse_time_to_seconds,
)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestTimePeriodConstruction:
    """TimePeriod stores and normalises unit fields correctly."""

    def test_seconds_only(self):
        """Plain seconds value stored on .seconds."""
        tp = TimePeriod(seconds=30)
        assert tp.seconds == 30
        assert tp.minutes is None
        assert tp.hours is None

    def test_minutes_only(self):
        """Plain minutes stored on .minutes."""
        tp = TimePeriod(minutes=5)
        assert tp.minutes == 5

    def test_hours_only(self):
        tp = TimePeriod(hours=2)
        assert tp.hours == 2

    def test_days_only(self):
        tp = TimePeriod(days=1)
        assert tp.days == 1

    def test_milliseconds_only(self):
        tp = TimePeriod(milliseconds=500)
        assert tp.milliseconds == 500

    def test_microseconds_only(self):
        tp = TimePeriod(microseconds=250)
        assert tp.microseconds == 250

    def test_fractional_seconds_normalised_to_ms(self):
        """1.5 seconds → seconds=1, milliseconds=500."""
        tp = TimePeriod(seconds=1.5)
        assert tp.seconds == 1
        assert tp.milliseconds == 500

    def test_fractional_minutes_normalised_to_seconds(self):
        """1.5 minutes → minutes=1, seconds=30."""
        tp = TimePeriod(minutes=1.5)
        assert tp.minutes == 1
        assert tp.seconds == 30

    def test_fractional_hours_normalised_to_minutes(self):
        """1.5 hours → hours=1, minutes=30."""
        tp = TimePeriod(hours=1.5)
        assert tp.hours == 1
        assert tp.minutes == 30

    def test_fractional_days_normalised_to_hours(self):
        """0.5 days → days=0, hours=12."""
        tp = TimePeriod(days=0.5)
        assert tp.days == 0
        assert tp.hours == 12

    def test_microseconds_non_integer_raises(self):
        """Sub-microsecond precision raises ValueError."""
        with pytest.raises(ValueError, match="Maximum precision is microseconds"):
            TimePeriod(microseconds=1.7)


# ---------------------------------------------------------------------------
# Total conversions
# ---------------------------------------------------------------------------

class TestTimePeriodTotals:
    """total_* properties accumulate nested units correctly."""

    def test_total_seconds_from_minutes(self):
        assert TimePeriod(minutes=2).total_seconds == 120

    def test_total_seconds_from_hours(self):
        assert TimePeriod(hours=1).total_seconds == 3600

    def test_total_seconds_from_days(self):
        assert TimePeriod(days=1).total_seconds == 86400

    def test_total_milliseconds_from_seconds(self):
        assert TimePeriod(seconds=5).total_milliseconds == 5000

    def test_total_milliseconds_from_ms(self):
        assert TimePeriod(milliseconds=750).total_milliseconds == 750

    def test_total_microseconds_from_ms(self):
        assert TimePeriod(milliseconds=1).total_microseconds == 1000

    def test_total_in_seconds_float(self):
        assert TimePeriod(milliseconds=500).total_in_seconds == pytest.approx(0.5)

    def test_combined_units(self):
        """1h 30m = 5400 seconds."""
        tp = TimePeriod(hours=1, minutes=30)
        assert tp.total_seconds == 5400

    def test_zero_period(self):
        """Empty TimePeriod = 0 in every unit."""
        tp = TimePeriod()
        assert tp.total_seconds == 0
        assert tp.total_milliseconds == 0
        assert tp.total_in_seconds == 0.0


# ---------------------------------------------------------------------------
# as_timedelta
# ---------------------------------------------------------------------------

class TestTimePeriodAsTimedelta:
    """as_timedelta returns correct datetime.timedelta."""

    def test_seconds_timedelta(self):
        assert TimePeriod(seconds=10).as_timedelta == timedelta(seconds=10)

    def test_minutes_timedelta(self):
        assert TimePeriod(minutes=3).as_timedelta == timedelta(minutes=3)

    def test_combined_timedelta(self):
        tp = TimePeriod(hours=1, minutes=30)
        assert tp.as_timedelta == timedelta(hours=1, minutes=30)


# ---------------------------------------------------------------------------
# __str__ / __repr__ / as_dict
# ---------------------------------------------------------------------------

class TestTimePeriodStringRepresentation:
    """String representations and dict serialisation."""

    def test_str_seconds(self):
        assert str(TimePeriod(seconds=5)) == "5s"

    def test_str_minutes(self):
        assert str(TimePeriod(minutes=10)) == "10min"

    def test_str_hours(self):
        assert str(TimePeriod(hours=2)) == "2h"

    def test_str_days(self):
        assert str(TimePeriod(days=3)) == "3d"

    def test_str_milliseconds(self):
        assert str(TimePeriod(milliseconds=500)) == "500ms"

    def test_str_microseconds(self):
        assert str(TimePeriod(microseconds=100)) == "100us"

    def test_str_empty(self):
        assert str(TimePeriod()) == "0s"

    def test_repr_contains_str(self):
        tp = TimePeriod(seconds=7)
        assert "7s" in repr(tp)

    def test_as_dict_seconds(self):
        assert TimePeriod(seconds=5).as_dict() == {"seconds": 5}

    def test_as_dict_multiple_units(self):
        d = TimePeriod(hours=1, minutes=30).as_dict()
        assert d["hours"] == 1
        assert d["minutes"] == 30


# ---------------------------------------------------------------------------
# Comparison operators
# ---------------------------------------------------------------------------

class TestTimePeriodComparisons:
    """Comparison operators work on total_microseconds."""

    def test_equal(self):
        assert TimePeriod(seconds=60) == TimePeriod(minutes=1)

    def test_not_equal(self):
        assert TimePeriod(seconds=30) != TimePeriod(seconds=31)

    def test_less_than(self):
        assert TimePeriod(seconds=30) < TimePeriod(minutes=1)

    def test_greater_than(self):
        assert TimePeriod(minutes=1) > TimePeriod(seconds=30)

    def test_less_than_or_equal(self):
        assert TimePeriod(seconds=60) <= TimePeriod(minutes=1)

    def test_greater_than_or_equal(self):
        assert TimePeriod(minutes=1) >= TimePeriod(seconds=60)

    def test_not_equal_to_non_timeperiod(self):
        assert TimePeriod(seconds=5).__eq__(42) is NotImplemented


# ---------------------------------------------------------------------------
# Subclasses (smoke)
# ---------------------------------------------------------------------------

class TestTimePeriodSubclasses:
    """Subclasses are valid TimePeriod instances."""

    def test_microseconds_subclass(self):
        tp = TimePeriodMicroseconds(microseconds=1000)
        assert tp.total_in_seconds == pytest.approx(0.001)

    def test_milliseconds_subclass(self):
        tp = TimePeriodMilliseconds(milliseconds=500)
        assert tp.total_in_seconds == pytest.approx(0.5)

    def test_seconds_subclass(self):
        tp = TimePeriodSeconds(seconds=10)
        assert tp.total_in_seconds == 10.0

    def test_minutes_subclass(self):
        tp = TimePeriodMinutes(minutes=2)
        assert tp.total_seconds == 120


# ---------------------------------------------------------------------------
# parse_time_to_seconds
# ---------------------------------------------------------------------------

class TestParseTimeToSeconds:
    """parse_time_to_seconds handles TimePeriod, numeric, None, and bad input."""

    def test_timeperiod_input(self):
        assert parse_time_to_seconds(TimePeriod(seconds=30), 0.0) == 30.0

    def test_int_input(self):
        assert parse_time_to_seconds(60, 0.0) == 60.0

    def test_float_input(self):
        assert parse_time_to_seconds(1.5, 0.0) == pytest.approx(1.5)

    def test_none_returns_default(self):
        assert parse_time_to_seconds(None, 99.0) == 99.0

    def test_invalid_string_returns_default(self):
        assert parse_time_to_seconds("bad", 5.0) == 5.0

    def test_minutes_timeperiod(self):
        assert parse_time_to_seconds(TimePeriod(minutes=1), 0.0) == 60.0


# ---------------------------------------------------------------------------
# parse_time_to_ms
# ---------------------------------------------------------------------------

class TestParseTimeToMs:
    """parse_time_to_ms handles TimePeriod, numeric, None, and bad input."""

    def test_timeperiod_milliseconds(self):
        assert parse_time_to_ms(TimePeriod(milliseconds=250), None) == 250

    def test_timeperiod_seconds(self):
        assert parse_time_to_ms(TimePeriod(seconds=2), None) == 2000

    def test_int_input(self):
        assert parse_time_to_ms(500, None) == 500

    def test_float_input(self):
        assert parse_time_to_ms(1.5, None) == 1

    def test_none_returns_default(self):
        assert parse_time_to_ms(None, 100) == 100

    def test_none_with_none_default(self):
        assert parse_time_to_ms(None, None) is None

    def test_invalid_string_returns_default(self):
        assert parse_time_to_ms("bad", 200) == 200
