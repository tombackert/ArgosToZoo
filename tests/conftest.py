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
    # Legacy fallback: keep for a short transition window; will be removed once
    # all tests consistently use @pytest.mark.integration
    "parallel_api",
    "timeout_recovery",
    "graceful_shutdown",
    "seed_restart",
    "reward_variance",
    "test_env"
)


def pytest_configure(config):  # noqa: D401
    config.addinivalue_line("markers", "timeout: test has a timeout (seconds)")
    config.addinivalue_line(
        "markers",
        "integration: test requires argos3 binary (will be skipped in fast CI job if missing)",
    )


def pytest_collection_modifyitems(config, items):  # noqa: D401
    if shutil.which("argos3"):
        return
    skip = pytest.mark.skip(
        reason="argos3 not installed; skipping integration tests (@integration)"
    )
    for item in items:
        # Primary: use explicit marker
        if "integration" in item.keywords:
            item.add_marker(skip)
            continue
        # Fallback: legacy name-based heuristic until all tests annotated
        if any(key in item.nodeid for key in INTEGRATION_KEYWORDS):
            item.add_marker(skip)
