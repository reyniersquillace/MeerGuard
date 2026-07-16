"""
This file contains custom errors and warnings 
for the CoastGuard timing pipeline.

Patrick Lazarus, Nov. 10, 2011
"""
import sys
from coast_guard import colour
from coast_guard import log


class CoastGuardError(Exception):
    """Base class for (non-fatal) CoastGuard errors.

        When raised the error message is (by default) logged and is
        colourized as an 'error' when converted to a string.
    """
    def __init__(self, msg, logit=True):
        """Create a CoastGuardError.

            Inputs:
                msg: The error message.
                logit: If True, log the message at 'error' level.
                    (Default: True)
        """
        if logit:
            log.log(msg, 'error')
        super(CoastGuardError, self).__init__(msg)

    def __str__(self):
        return colour.cstring(super(CoastGuardError, self).__str__(), 'error')

    def get_message(self):
        """Return the (uncolourized) error message."""
        return super(CoastGuardError, self).__str__()


class SystemCallError(CoastGuardError):
    """Error raised when an external system call fails."""
    pass


class StandardProfileError(CoastGuardError):
    """Error related to a standard/template profile."""
    pass


class ToaError(CoastGuardError):
    """Error related to time-of-arrival (TOA) generation."""
    pass


class DataReductionFailed(CoastGuardError):
    """Error raised when data reduction fails."""
    pass


class BadFile(CoastGuardError):
    """Error raised for a missing or otherwise invalid file."""
    pass


class CleanError(CoastGuardError):
    """Error raised during RFI cleaning."""
    pass


class ConfigurationError(CoastGuardError):
    """Error related to configuration values."""
    pass


class BadPulsarNameError(CoastGuardError):
    """Error raised for an unrecognized or invalid pulsar name."""
    pass


class HeaderCorrectionError(CoastGuardError):
    """Error raised when correcting an archive header fails."""
    pass


class DiagnosticError(CoastGuardError):
    """Error related to producing diagnostics."""
    pass


class InputError(CoastGuardError):
    """Error raised for invalid input."""
    pass


class FitError(CoastGuardError):
    """Error raised when a fit fails or returns a bad status."""
    pass


class FormatError(CoastGuardError):
    """Error raised for badly formatted data."""
    pass


class DatabaseError(CoastGuardError):
    """Error related to database access."""
    pass


class BadStatusError(CoastGuardError):
    """Error raised for an unexpected processing status."""
    pass


class UnrecognizedValueError(CoastGuardError):
    """Error raised when a value is not recognized."""
    pass


class TemplateGenerationError(CoastGuardError):
    """Error raised when template generation fails."""
    pass


class CalibrationError(CoastGuardError):
    """Error related to calibration."""
    pass


# Fatal class of errors. These should not be caught.
class FatalCoastGuardError(Exception):
    """Base class for fatal CoastGuard errors.

        These represent unrecoverable conditions and should not be caught.
        The message is logged at 'critical' level when raised.
    """
    def __init__(self, msg):
        """Create a FatalCoastGuardError and log 'msg' at 'critical' level."""
        log.log(msg, 'critical')
        super(FatalCoastGuardError, self).__init__(msg)

    def __str__(self):
        return colour.cstring(super(FatalCoastGuardError, self).__str__(), 'error')

    def get_message(self):
        """Return the (uncolourized) error message."""
        return super(FatalCoastGuardError, self).__str__()


class BadColumnNameError(FatalCoastGuardError):
    """Fatal error raised for an unrecognized database column name."""
    pass

# Custom Warnings
class CoastGuardWarning(Warning):
    """Base class for CoastGuard warnings.

        The warning message is colourized as a 'warning' when converted
        to a string.
    """
    def __str__(self):
        return colour.cstring(super(CoastGuardWarning, self).__str__(), 'warning')


class LoggedCoastGuardWarning(CoastGuardWarning):
    """A CoastGuard warning that is also logged (at 'warning' level)."""
    def __init__(self, msg):
        """Create the warning and log 'msg' at 'warning' level."""
        log.log(msg, 'warning')
        super(CoastGuardWarning, self).__init__(msg)

