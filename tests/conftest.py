"""Pytest configuration (FUP-11).

Provides:
 - sys.path adjustment for local package imports
 - registration of custom markers
 - conditional skip of integration tests when ARGoS binary missing
"""

from __future__ import annotations

import sys
import os
import shutil
import pytest

SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

INTEGRATION_KEYWORDS = (
    "timeout_recovery",
    "graceful_shutdown",
    "seed_restart",
    "reward_variance",
)


def pytest_configure(config):  # noqa: D401
    config.addinivalue_line("markers", "timeout: test has a timeout (seconds)")


def pytest_collection_modifyitems(config, items):  # noqa: D401
    if shutil.which("argos3"):
        return
    skip = pytest.mark.skip(reason="argos3 not installed; skipping integration tests")
    for item in items:
        if any(key in item.nodeid for key in INTEGRATION_KEYWORDS):
            item.add_marker(skip)
