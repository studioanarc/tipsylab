"""Home-Assistant-Tests: eigene Integrationen aus custom_components/ erlauben."""

from datetime import timedelta

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.util import dt as dt_util

# Vor dem Start von Home Assistant importieren, sonst gewinnt das custom_components des Test-Plugins
import custom_components.tipsylab  # noqa: E402, F401

DOMAIN = "tipsylab"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def petnat_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data={
            "name": "Test",
            "mode": "petnat",
            "brix0": 20.5,
            "volume_l": 750,
            "start": (dt_util.utcnow() - timedelta(days=7)).isoformat(),
            "gravity_entity": "sensor.spindel_gravity",
            "gravity_unit": "sg",
            "temperature_entity": "sensor.wein_temperatur",
        },
        options={"target_bar_20c": 2.5, "bottle": "750", "malo_in_bottle": False, "malic_g_l": 0.0,
                 "q10": 2.2, "dry_sugar_g_l": 2.0, "filling_loss": 0.08},
    )
