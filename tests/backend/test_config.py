from __future__ import annotations

import pytest

from easymcf.config import Config

pytestmark = pytest.mark.backend


@pytest.mark.parametrize("mode", ["fixture", "live"])
def test_mcf_mode_accepts_supported_values(mode):
    assert Config(mcf_mode=mode).mcf_mode == mode


def test_mcf_mode_rejects_boolean_like_value():
    with pytest.raises(ValueError, match="MCF_MODE must be 'fixture' or 'live'"):
        Config(mcf_mode="True")