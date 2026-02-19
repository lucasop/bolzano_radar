"""Config flow per Bolzano Radar."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig

from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

class BolzanoRadarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow handler."""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ):
        """Opzioni flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Step user per add integration."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_only")
        
        return self.async_create_entry(title="Bolzano Radar", data={})

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Init options."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Init options."""
        if user_input is not None:
            return self.async_create_entry(title="Configurazione", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): int(NumberSelector(NumberSelectorConfig(min=1, max=60))),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )

