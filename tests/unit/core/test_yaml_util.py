"""Unit tests for boneio.core.config.yaml_util.

Covers pure-function utilities that do not require a running Manager,
MQTT bus, or schema validation:
- _deep_merge_schema
- filter_yaml_files
- normalize_board_name
- normalize_version
- load_yaml_file (via tmp_path)
- load_config_from_string (basic smoke)
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from boneio.core.config.yaml_util import (
    _deep_merge_schema,
    filter_yaml_files,
    normalize_board_name,
    normalize_version,
    load_yaml_file,
)


# ---------------------------------------------------------------------------
# _deep_merge_schema
# ---------------------------------------------------------------------------

class TestDeepMergeSchema:
    """_deep_merge_schema recursively merges dicts without mutating source."""

    def test_adds_new_key(self):
        target = {"a": 1}
        _deep_merge_schema(target, {"b": 2})
        assert target == {"a": 1, "b": 2}

    def test_overwrites_scalar(self):
        target = {"a": 1}
        _deep_merge_schema(target, {"a": 99})
        assert target["a"] == 99

    def test_deep_merge_nested_dict(self):
        """Nested dicts are merged, not replaced."""
        target = {"outer": {"a": 1, "b": 2}}
        _deep_merge_schema(target, {"outer": {"b": 99, "c": 3}})
        assert target["outer"] == {"a": 1, "b": 99, "c": 3}

    def test_list_is_replaced_not_concatenated(self):
        """Lists are overwritten wholesale (Cerberus schema semantics)."""
        target = {"items": [1, 2, 3]}
        _deep_merge_schema(target, {"items": [4, 5]})
        assert target["items"] == [4, 5]

    def test_deeply_nested_merge(self):
        target = {"a": {"b": {"c": 1}}}
        _deep_merge_schema(target, {"a": {"b": {"d": 2}}})
        assert target["a"]["b"] == {"c": 1, "d": 2}

    def test_empty_source_no_change(self):
        target = {"a": 1}
        _deep_merge_schema(target, {})
        assert target == {"a": 1}

    def test_empty_target_gets_source(self):
        target = {}
        _deep_merge_schema(target, {"x": 42})
        assert target == {"x": 42}

    def test_returns_target(self):
        """Function returns the mutated target dict."""
        target = {"a": 1}
        result = _deep_merge_schema(target, {"b": 2})
        assert result is target


# ---------------------------------------------------------------------------
# filter_yaml_files
# ---------------------------------------------------------------------------

class TestFilterYamlFiles:
    """filter_yaml_files keeps only non-secret, non-hidden YAML files."""

    def test_keeps_yaml_extension(self):
        assert filter_yaml_files(["config.yaml"]) == ["config.yaml"]

    def test_keeps_yml_extension(self):
        assert filter_yaml_files(["config.yml"]) == ["config.yml"]

    def test_removes_non_yaml(self):
        assert filter_yaml_files(["config.yaml", "readme.txt"]) == ["config.yaml"]

    def test_removes_secrets_yaml(self):
        assert filter_yaml_files(["config.yaml", "secrets.yaml"]) == ["config.yaml"]

    def test_removes_secrets_yml(self):
        assert filter_yaml_files(["config.yaml", "secrets.yml"]) == ["config.yaml"]

    def test_removes_hidden_files(self):
        assert filter_yaml_files([".hidden.yaml", "config.yaml"]) == ["config.yaml"]

    def test_empty_input(self):
        assert filter_yaml_files([]) == []

    def test_all_filtered_out(self):
        assert filter_yaml_files(["secrets.yaml", "readme.txt"]) == []


# ---------------------------------------------------------------------------
# normalize_board_name
# ---------------------------------------------------------------------------

class TestNormalizeBoardName:
    """normalize_board_name maps hardware name variants to canonical form."""

    @pytest.mark.parametrize("name, expected", [
        ("32x10a",    "32_10"),
        ("32x10A",    "32_10"),
        ("32x10",     "32_10"),
        ("32",        "32_10"),
        ("32x5a",     "32_5"),
        ("32x5A",     "32_5"),
        ("32x5",      "32_5"),
        ("24x16A",    "24_16"),
        ("24x16",     "24_16"),
        ("24",        "24_16"),
        ("cover",     "cover"),
        ("cm",        "cover_mix"),
        ("cover mix", "cover_mix"),
        ("covermix",  "cover_mix"),
        ("cover_mix", "cover_mix"),
        ("48x4A",     "48_4"),
        ("48",        "48_4"),
    ])
    def test_known_variants(self, name, expected):
        """All documented name variants normalise to the expected canonical form."""
        assert normalize_board_name(name) == expected

    def test_empty_string_returns_empty(self):
        assert normalize_board_name("") == ""

    def test_case_insensitive(self):
        assert normalize_board_name("32X10A") == "32_10"

    def test_strips_whitespace(self):
        assert normalize_board_name("  32x10  ") == "32_10"


# ---------------------------------------------------------------------------
# normalize_version
# ---------------------------------------------------------------------------

class TestNormalizeVersion:
    """normalize_version trims to major.minor."""

    @pytest.mark.parametrize("raw, expected", [
        ("0.7.1",   "0.7"),
        ("0.8.2",   "0.8"),
        ("0.9",     "0.9"),
        ("1.0.0",   "1.0"),
        ("1.2.3.4", "1.2"),
    ])
    def test_known_versions(self, raw, expected):
        assert normalize_version(raw) == expected

    def test_empty_string_returned_as_is(self):
        assert normalize_version("") == ""

    def test_single_part_returned_as_is(self):
        """Single component (no dot) returned unchanged."""
        assert normalize_version("1") == "1"


# ---------------------------------------------------------------------------
# load_yaml_file
# ---------------------------------------------------------------------------

class TestLoadYamlFile:
    """load_yaml_file reads and parses YAML with BoneIOLoader."""

    def test_simple_dict(self, tmp_path):
        f = tmp_path / "cfg.yaml"
        f.write_text("key: value\nnum: 42\n")
        result = load_yaml_file(str(f))
        assert result["key"] == "value"
        assert result["num"] == 42

    def test_empty_file_returns_ordered_dict(self, tmp_path):
        """Empty YAML file returns empty OrderedDict (not None)."""
        from collections import OrderedDict
        f = tmp_path / "empty.yaml"
        f.write_text("")
        result = load_yaml_file(str(f))
        assert isinstance(result, OrderedDict)
        assert len(result) == 0

    def test_list_of_dicts(self, tmp_path):
        f = tmp_path / "list.yaml"
        f.write_text(textwrap.dedent("""\
            - id: a
              value: 1
            - id: b
              value: 2
        """))
        result = load_yaml_file(str(f))
        assert len(result) == 2
        assert result[0]["id"] == "a"

    def test_nested_dict(self, tmp_path):
        f = tmp_path / "nested.yaml"
        f.write_text("outer:\n  inner: hello\n")
        result = load_yaml_file(str(f))
        assert result["outer"]["inner"] == "hello"

    def test_missing_file_raises(self, tmp_path):
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_yaml_file(str(tmp_path / "nonexistent.yaml"))
