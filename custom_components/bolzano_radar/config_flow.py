"""Config flow Bolzano Radar."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow Bolzano Radar."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):  # ← NO self.config_entry qui
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step user - Nessuna config necessaria."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(
            title="Bolzano Radar Piogge", data={}
        )

class OptionsFlowHandler(config_entries.OptionsFlow):  # ← NO __init__!
    """Options flow handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Gestisci opzioni."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Schema opzioni (es. FPS, opacità)
        data_schema = vol.Schema({
            vol.Optional("fps", default=2.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.5, max=5.0, step=0.5)
            ),
            vol.Optional("radar_opacity", default=0.7): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.3, max=1.0, step=0.05)
            ),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema
        )