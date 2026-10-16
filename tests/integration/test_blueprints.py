"""Blueprints: mit den Werkzeugen von Home Assistant laden, Eingaben einsetzen, Automation prüfen."""

from pathlib import Path

import pytest

from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA, async_validate_config_item
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.core import HomeAssistant
from homeassistant.util.yaml import load_yaml

FOLDER = Path(__file__).parents[2] / "blueprints" / "automation" / "tipsylab"
INPUTS = {
    "abfuellfenster.yaml": {"status": "sensor.test_status", "handy": "0123456789abcdef"},
    "alarm.yaml": {"sensoren": ["binary_sensor.test_flaschendruck_alarm"], "handy": "0123456789abcdef"},
    "website_feed.yaml": {},
}


def _without_phone(actions: list) -> list:
    """Die Handy-Aktion (Gerät der App) braucht hier ein echtes Gerät; für die Prüfung wird sie zur
    gleich gebauten Benachrichtigung, damit Titel- und Textvorlagen trotzdem geprüft werden."""
    out = []
    for a in actions:
        if isinstance(a, dict) and a.get("domain") == "mobile_app":
            data = {k: a[k] for k in ("title", "message", "data") if k in a}
            out.append({"action": "notify.notify", "data": data})
        else:
            out.append(a)
    return out


def test_every_blueprint_has_inputs_here():
    assert sorted(p.name for p in FOLDER.glob("*.yaml")) == sorted(INPUTS)


@pytest.mark.parametrize("name", sorted(INPUTS))
async def test_blueprint_is_a_valid_automation(hass: HomeAssistant, name: str) -> None:
    blueprint = Blueprint(load_yaml(FOLDER / name), expected_domain="automation", schema=AUTOMATION_BLUEPRINT_SCHEMA)
    inputs = BlueprintInputs(blueprint, {"use_blueprint": {"path": name, "input": INPUTS[name]}})
    inputs.validate()
    config = inputs.async_substitute()
    config["id"] = name
    config["actions"] = _without_phone(config.get("actions", []))
    validated = await async_validate_config_item(hass, name, config)
    assert validated is not None
    assert validated.validation_error is None, validated.validation_error
