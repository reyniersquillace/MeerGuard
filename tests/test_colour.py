"""Unit tests for coast_guard.colour.

Tests the terminal-colour string helpers. ``config.colour`` is toggled via
monkeypatch to exercise both the coloured and plain code paths.
"""
import pytest

from coast_guard import colour
from coast_guard import config


class TestCstring:
    def test_plain_when_colour_disabled(self, monkeypatch):
        monkeypatch.setattr(config, 'colour', False)
        assert colour.cstring("hello") == "hello"

    def test_wraps_when_colour_enabled(self, monkeypatch):
        monkeypatch.setattr(config, 'colour', True)
        out = colour.cstring("hello", preset='error')
        # Original text is preserved between the colour codes.
        assert "hello" in out
        # Ends with the reset/default code.
        assert out.endswith(colour.DEFAULT_CODE)
        # Contains the escape introducer.
        assert '\033[' in out

    def test_preset_error_code_used(self, monkeypatch):
        monkeypatch.setattr(config, 'colour', True)
        out = colour.cstring("x", preset='error')
        assert out.startswith(colour.preset_codes['error'])

    def test_current_code_restored_after_override(self, monkeypatch):
        monkeypatch.setattr(config, 'colour', True)
        before = colour.current_code
        colour.cstring("x", preset='success')
        assert colour.current_code == before


class TestCset:
    def test_preset_sets_current_code(self):
        colour.cset('error')
        assert colour.current_code == colour.preset_codes['error']
        colour.creset()

    def test_creset_restores_default(self):
        colour.cset('error')
        colour.creset()
        assert colour.current_code == colour.DEFAULT_CODE

    def test_unrecognised_preset_leaves_code_unchanged(self, capsys):
        colour.creset()
        before = colour.current_code
        colour.cset('does-not-exist')
        captured = capsys.readouterr()
        assert 'Unrecognized preset' in captured.out
        assert colour.current_code == before

    def test_named_fg_bg_build_code(self):
        colour.cset(fg='red', bg='blue')
        # Foreground 31, background 44 per the module dicts.
        assert '31' in colour.current_code
        assert '44' in colour.current_code
        colour.creset()

    def test_bold_attribute(self):
        colour.cset(fg='green', bold=True)
        # attribute 'bold' == 1
        assert colour.current_code.startswith('\033[1;')
        colour.creset()

    def test_numeric_fg_colour_code(self):
        # Previously a Python-2 bug (types.IntType). An integer colour code
        # should be accepted and embedded verbatim.
        colour.cset(fg=31)
        assert '31' in colour.current_code
        colour.creset()

    def test_numeric_string_bg_colour_code(self):
        # A digit-string colour code is also accepted (fg.isdigit() branch).
        colour.cset(bg='44')
        assert '44' in colour.current_code
        colour.creset()


class TestPresetTables:
    def test_all_presets_are_escape_codes(self):
        for code in colour.preset_codes.values():
            assert code.startswith('\033[')

    def test_default_and_reset_alias(self):
        assert colour.preset_codes['default'] == colour.preset_codes['reset']
