"""Unit tests for coast_guard.errors.

These check the custom exception/warning hierarchy and the message helpers.
Errors are constructed with ``logit=False`` where possible to avoid noisy
log output during the test run.
"""
import pytest

from coast_guard import errors


ERROR_SUBCLASSES = [
    errors.SystemCallError,
    errors.StandardProfileError,
    errors.ToaError,
    errors.DataReductionFailed,
    errors.BadFile,
    errors.CleanError,
    errors.ConfigurationError,
    errors.BadPulsarNameError,
    errors.HeaderCorrectionError,
    errors.DiagnosticError,
    errors.InputError,
    errors.FitError,
    errors.FormatError,
    errors.DatabaseError,
    errors.BadStatusError,
    errors.UnrecognizedValueError,
    errors.TemplateGenerationError,
    errors.CalibrationError,
]


class TestCoastGuardError:
    def test_is_exception(self):
        assert issubclass(errors.CoastGuardError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(errors.CoastGuardError):
            raise errors.CoastGuardError("boom", logit=False)

    def test_get_message_returns_plain_text(self):
        err = errors.CoastGuardError("plain message", logit=False)
        assert err.get_message() == "plain message"

    def test_str_contains_original_message(self):
        # __str__ may wrap the message in colour codes, but the raw text
        # must still be present.
        err = errors.CoastGuardError("wrapped message", logit=False)
        assert "wrapped message" in str(err)

    @pytest.mark.parametrize("cls", ERROR_SUBCLASSES)
    def test_subclasses_inherit(self, cls):
        assert issubclass(cls, errors.CoastGuardError)
        err = cls("msg", logit=False)
        assert err.get_message() == "msg"


class TestFatalErrors:
    def test_fatal_is_exception_not_coastguarderror(self):
        assert issubclass(errors.FatalCoastGuardError, Exception)
        # Fatal errors are intentionally a separate hierarchy.
        assert not issubclass(errors.FatalCoastGuardError, errors.CoastGuardError)

    def test_bad_column_name_is_fatal(self):
        assert issubclass(errors.BadColumnNameError, errors.FatalCoastGuardError)

    def test_get_message(self):
        err = errors.FatalCoastGuardError("fatal msg")
        assert err.get_message() == "fatal msg"
        assert "fatal msg" in str(err)


class TestWarnings:
    def test_coastguard_warning_is_warning(self):
        assert issubclass(errors.CoastGuardWarning, Warning)

    def test_str_contains_message(self):
        w = errors.CoastGuardWarning("careful")
        assert "careful" in str(w)

    def test_logged_warning_subclass(self):
        assert issubclass(errors.LoggedCoastGuardWarning, errors.CoastGuardWarning)
