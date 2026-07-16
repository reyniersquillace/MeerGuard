"""Shared pytest fixtures / import shims for the MeerGuard test-suite.

The real ``psrchive`` C-extension is not available in the test environment
(and is not needed to exercise the pure-Python helpers). A couple of modules
(``coast_guard.cleaners.surgical``, ``coast_guard.clean_archive``) import
``psrchive`` at module import time, which would raise ``ModuleNotFoundError``
before any of their pure-Python siblings can be imported.

To let those imports succeed we inject a lightweight ``MagicMock`` under the
``psrchive`` key in ``sys.modules`` *before* any test module is collected. This
is deliberately minimal: it only stops the top-level ``import psrchive`` from
failing. No test relies on the mock returning meaningful values -- anything
that actually needs a live Archive is left to integration testing.
"""
import sys
from unittest.mock import MagicMock

# Inject the stub as early as possible (at collection time).
if 'psrchive' not in sys.modules:
    sys.modules['psrchive'] = MagicMock(name='psrchive_stub')
