"""Bolzano Radar - Fix pausa/riprendi."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .camera import BolzanoRadarCoordinator

PLATFORMS = [Platform.CAMERA, Platform.NUMBER]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = BolzanoRadarCoordinator(hass, entry.entry_id)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await coordinator.async_refresh()

    scan_interval_min = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    async def rotate_frames():
        while True:
            await asyncio.sleep(0.5)
            if coordinator.frames and not coordinator.is_paused:
                coordinator.current_frame_index = (
                    coordinator.current_frame_index + 1
                ) % len(coordinator.frames)
                coordinator.force_refresh_camera = True  # ✅ Fix sincronizzazione
                coordinator.async_set_updated_data(coordinator.last_data)


    hass.async_create_background_task(rotate_frames(), "bolzano_rotate")

    async def handle_resume(call) -> None:
        """Service bolzano_radar.resume → riprende auto-play."""
        coordinator.is_paused = False
        _LOGGER.info("Radar: auto-play ripreso")

    hass.services.async_register(DOMAIN, "resume", handle_resume)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)
    hass.services.async_remove(DOMAIN, "resume")
    return unload_ok

