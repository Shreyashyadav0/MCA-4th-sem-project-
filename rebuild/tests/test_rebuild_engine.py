"""Verification test for track 6 — ``rebuild/engine.py``.

Skips cleanly until the module exists. Then it requires the rebuilt selector to route
the same environment to the same provider, degrade to mock on the same missing
credential, and raise on the same programming error.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.config as real_config  # noqa: E402
import app.engine as real  # noqa: E402

REBUILD_FILE = ROOT / "rebuild" / "engine.py"

pytestmark = pytest.mark.skipif(
    not REBUILD_FILE.exists(), reason="rebuild/engine.py not written yet"
)

#: (settings kwargs, requested provider) — the routing matrix, minus the network.
CASES = [
    ({}, "auto"),
    ({"sarvam_api_key": "key"}, "auto"),
    ({"lmstudio_base_url": "http://localhost:1234/v1"}, "auto"),
    (
        {"sarvam_api_key": "key", "lmstudio_base_url": "http://localhost:1234/v1"},
        "auto",
    ),
    ({"sarvam_api_key": "key"}, "local"),
    ({"lmstudio_base_url": "http://localhost:1234/v1"}, "sarvam"),
    ({}, "mock"),
    ({"sarvam_api_key": "key"}, "mock"),
]


@pytest.fixture(scope="module")
def rebuilt():
    return pytest.importorskip("rebuild.engine")


@pytest.mark.parametrize("kwargs,requested", CASES)
def test_same_provider_for_the_same_environment(rebuilt, kwargs, requested):
    settings = real_config.Settings(_env_file=None, **kwargs)
    assert rebuilt.select_provider(settings, requested=requested).provider == (
        real.select_provider(settings, requested=requested).provider
    )


def test_sarvam_wins_when_both_are_configured(rebuilt):
    settings = real_config.Settings(
        _env_file=None,
        sarvam_api_key="key",
        lmstudio_base_url="http://localhost:1234/v1",
    )
    assert real.select_provider(settings).provider == "sarvam"
    assert rebuilt.select_provider(settings).provider == "sarvam"


def test_missing_credential_degrades_instead_of_raising(rebuilt):
    settings = real_config.Settings(_env_file=None)
    ours = real.select_provider(settings, requested="sarvam")
    theirs = rebuilt.select_provider(settings, requested="sarvam")
    assert theirs.provider == ours.provider == "mock"
    assert theirs.config is None and ours.config is None
    # The reason is user-facing and must name what is missing.
    assert "SARVAM_API_KEY" in theirs.reason


def test_unknown_provider_raises_in_both(rebuilt):
    settings = real_config.Settings(_env_file=None)
    with pytest.raises(ValueError):
        real.select_provider(settings, requested="gemini")
    with pytest.raises(ValueError):
        rebuilt.select_provider(settings, requested="gemini")


def test_provider_precedence_order_matches(rebuilt):
    assert tuple(rebuilt.PROVIDERS) == tuple(real.PROVIDERS)
