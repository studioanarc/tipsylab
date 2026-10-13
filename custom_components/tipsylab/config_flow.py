"""Neuen Ansatz anlegen: Ansatz → Quellen → Ziel. Später änderbar über die Optionen."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    DateTimeSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import dt as dt_util

from .const import (
    BOTTLES,
    CONF_BOTTLE_PRESSURE_ENTITY,
    CONF_BOTTLE_TEMP_ENTITY,
    CONF_BRIX0,
    CONF_BUBBLE_DEVICE,
    CONF_CO2_TARGET_ENTITY,
    CONF_GRAVITY_ENTITY,
    CONF_GRAVITY_UNIT,
    CONF_HEATER_HOST,
    CONF_MODE,
    CONF_NAME,
    CONF_PRESSURE_ENTITY,
    CONF_SG0,
    CONF_START,
    CONF_TEMP_ENTITY,
    CONF_VOLUME,
    CONF_WEIGHT_ENTITY,
    DEFAULT_OPTIONS,
    DOMAIN,
    GRAVITY_UNITS,
    MODES,
    OPT_BOTTLE,
    OPT_DRY_SUGAR,
    OPT_FILLING_LOSS,
    OPT_MALIC,
    OPT_MALO,
    OPT_PRV_BAR,
    OPT_Q10,
    OPT_TARGET_BAR,
    OPT_TEMP_LATE,
    OPT_TEMP_START,
    OPT_TEMP_SWITCH_SUGAR,
    SOURCE_KEYS,
)


def _num(min_v: float, max_v: float, step: float, unit: str | None = None) -> NumberSelector:
    config = NumberSelectorConfig(min=min_v, max=max_v, step=step, mode=NumberSelectorMode.BOX)
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


def _select(options: list[str], key: str) -> SelectSelector:
    return SelectSelector(SelectSelectorConfig(options=options, translation_key=key, mode=SelectSelectorMode.LIST))


def _sensor() -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain="sensor"))


def _parse_start(value: str | None) -> str:
    if value:
        parsed = dt_util.parse_datetime(value)
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
            return dt_util.as_utc(parsed).isoformat()
    return dt_util.utcnow().isoformat()


def sources_schema(mode: str) -> vol.Schema:
    """Sensoren und Geräte eines Ansatzes, je nach Betriebsart."""
    if mode == "charmat":
        return vol.Schema(
            {
                vol.Required(CONF_PRESSURE_ENTITY): _sensor(),
                vol.Required(CONF_TEMP_ENTITY): _sensor(),
                vol.Optional(CONF_CO2_TARGET_ENTITY): EntitySelector(EntitySelectorConfig(domain="number")),
                vol.Optional(CONF_HEATER_HOST): TextSelector(),
            }
        )
    fields: dict[Any, Any] = {
        vol.Optional(CONF_BUBBLE_DEVICE): TextSelector(),
        vol.Optional(CONF_GRAVITY_ENTITY): _sensor(),
        vol.Required(CONF_GRAVITY_UNIT, default="sg"): _select(GRAVITY_UNITS, "gravity_unit"),
        vol.Optional(CONF_TEMP_ENTITY): _sensor(),
        vol.Optional(CONF_WEIGHT_ENTITY): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="weight")),
        vol.Optional(CONF_HEATER_HOST): TextSelector(),
    }
    if mode == "petnat":  # Messflasche nach dem Abfüllen, z. B. die Flaschenbox
        fields[vol.Optional(CONF_BOTTLE_PRESSURE_ENTITY)] = EntitySelector(
            EntitySelectorConfig(domain="sensor", device_class="pressure")
        )
        fields[vol.Optional(CONF_BOTTLE_TEMP_ENTITY)] = _sensor()
    return vol.Schema(fields)


def target_schema(mode: str, current: dict[str, Any]) -> vol.Schema:
    """Ziel und Temperaturplan, je nach Betriebsart."""

    def opt(key: str) -> Any:
        return current.get(key, DEFAULT_OPTIONS.get(key))

    fields: dict[Any, Any] = {}
    if mode in ("petnat", "charmat"):
        fields[vol.Required(OPT_TARGET_BAR, default=opt(OPT_TARGET_BAR))] = _num(0.5, 6.0, 0.1, "bar")
    if mode == "petnat":
        fields[vol.Required(OPT_BOTTLE, default=opt(OPT_BOTTLE))] = _select(BOTTLES, "bottle")
        fields[vol.Required(OPT_MALO, default=opt(OPT_MALO))] = BooleanSelector()
        fields[vol.Optional(OPT_MALIC, default=opt(OPT_MALIC))] = _num(0, 10, 0.1, "g/L")
    if mode == "still":
        fields[vol.Required(OPT_DRY_SUGAR, default=opt(OPT_DRY_SUGAR))] = _num(0, 10, 0.5, "g/L")
    if mode == "charmat":
        fields[vol.Optional(OPT_PRV_BAR, description={"suggested_value": opt(OPT_PRV_BAR)})] = _num(0.5, 12, 0.1, "bar")
        fields[vol.Required(OPT_FILLING_LOSS, default=opt(OPT_FILLING_LOSS))] = _num(0, 0.5, 0.01)
    if mode in ("petnat", "still"):
        for key in (OPT_TEMP_START, OPT_TEMP_SWITCH_SUGAR, OPT_TEMP_LATE):
            unit = "g/L" if key == OPT_TEMP_SWITCH_SUGAR else "°C"
            max_v = 250 if key == OPT_TEMP_SWITCH_SUGAR else 30
            fields[vol.Optional(key, description={"suggested_value": current.get(key)})] = _num(0, max_v, 0.5, unit)
        fields[vol.Required(OPT_Q10, default=opt(OPT_Q10))] = _num(1.2, 4.0, 0.1)
    return vol.Schema(fields)


class TipsylabConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ein Config-Entry je Ansatz."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            mode = user_input[CONF_MODE]
            if mode != "charmat" and not user_input.get(CONF_BRIX0) and not user_input.get(CONF_SG0):
                errors["base"] = "must_required"
            else:
                self._data = {**user_input, CONF_START: _parse_start(user_input.get(CONF_START))}
                return await self.async_step_sources()
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): TextSelector(),
                vol.Required(CONF_MODE, default="petnat"): _select(MODES, "mode"),
                vol.Optional(CONF_BRIX0): _num(0, 40, 0.1, "°Bx"),
                vol.Optional(CONF_SG0): _num(0.98, 1.2, 0.001),
                vol.Required(CONF_VOLUME, default=750): _num(1, 100000, 1, "L"),
                vol.Optional(CONF_START): DateTimeSelector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_sources(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        mode = self._data[CONF_MODE]
        if user_input is not None:
            self._data.update({k: v for k, v in user_input.items() if v not in (None, "")})
            return await self.async_step_target()
        return self.async_show_form(step_id="sources", data_schema=sources_schema(mode))

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Quellen nachträglich ändern, etwa eine Waage nachrüsten. Messungen bleiben erhalten."""
        entry = self._get_reconfigure_entry()
        mode = entry.data[CONF_MODE]
        if user_input is not None:
            data = {k: v for k, v in entry.data.items() if k not in SOURCE_KEYS}
            data.update({k: v for k, v in user_input.items() if v not in (None, "")})
            return self.async_update_reload_and_abort(entry, data=data)
        schema = self.add_suggested_values_to_schema(sources_schema(mode), entry.data)
        return self.async_show_form(step_id="reconfigure", data_schema=schema)

    async def async_step_target(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        mode = self._data[CONF_MODE]
        if user_input is not None:
            options = {**DEFAULT_OPTIONS, **{k: v for k, v in user_input.items() if v is not None}}
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data, options=options)
        return self.async_show_form(step_id="target", data_schema=target_schema(mode, {}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> TipsylabOptionsFlow:
        return TipsylabOptionsFlow()


class TipsylabOptionsFlow(OptionsFlowWithReload):
    """Ziel, Flasche, Malo und Temperaturplan ändern."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        mode = self.config_entry.data.get(CONF_MODE, "petnat")
        if user_input is not None:
            options = dict(self.config_entry.options)
            for key in (OPT_TEMP_START, OPT_TEMP_SWITCH_SUGAR, OPT_TEMP_LATE, OPT_PRV_BAR):
                if key not in user_input:  # geleerte Felder wirklich entfernen
                    options.pop(key, None)
            options.update(user_input)
            return self.async_create_entry(data=options)
        return self.async_show_form(step_id="init", data_schema=target_schema(mode, dict(self.config_entry.options)))
