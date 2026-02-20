"""Number platform - Slider frame Bolzano Radar."""
import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BolzanoRadarFrameSlider(coordinator)])


class BolzanoRadarFrameSlider(NumberEntity):
    """Slider frame radar."""

    _attr_name = "Bolzano Radar Frame"
    _attr_icon = "mdi:film"
    _attr_has_entity_name = True
    _attr_native_min_value = 1
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator) -> None:
        super().__init__()
        self.coordinator = coordinator
        self._attr_unique_id = f"{DOMAIN}.frame_slider"
        # ✅ Registra listener coordinator per sync automatico
        self._attr_native_value = 1
        self._attr_native_max_value = max(1, len(coordinator.frames))

    async def async_added_to_hass(self) -> None:
        """Registra listener per aggiornamento automatico slider."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
        self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        """✅ Aggiorna slider in sync con frame corrente."""
        self._attr_native_value = float(
            self.coordinator.current_frame_index + 1
        )
        self._attr_native_max_value = float(
            max(1, len(self.coordinator.frames))
        )
        self.async_write_ha_state()  # ✅ Forza update UI

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "is_paused": self.coordinator.is_paused,
            "total_frames": len(self.coordinator.frames),
        }

    async def async_set_native_value(self, value: float) -> None:
        """Utente muove slider → pausa e vai al frame."""
        self.coordinator.current_frame_index = int(value) - 1
        self.coordinator.is_paused = True
        self._attr_native_value = value
        self.coordinator.force_refresh_camera = True   # ✅ Sostituisce invalidate_cache loop
        self.coordinator.async_set_updated_data(self.coordinator.last_data)
        self.async_write_ha_state()
