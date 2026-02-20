"""Camera platform Bolzano Radar - 2FPS + OSM Grayscale + Alpha Composite."""
import io
import logging
import math
from datetime import datetime
from typing import Any

import aiohttp
from PIL import Image, ImageChops, ImageEnhance

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, JSON_URL

_LOGGER = logging.getLogger(__name__)

# ── BBOX RADAR (fisso dal JSON - NON modificare) ──────────────────────────────
RADAR_LON_MIN = 9.533
RADAR_LAT_MIN = 45.41
RADAR_LON_MAX = 12.55
RADAR_LAT_MAX = 47.60

# ── BBOX VISUALIZZAZIONE (centrato su Bolzano ~100km raggio) ──────────────────
VIEW_LON_MIN = 10.049   # ~190km larghezza
VIEW_LAT_MIN = 45.5997  # ~200km altezza
VIEW_LON_MAX = 12.55    # Clampato al limite radar
VIEW_LAT_MAX = 47.3963


OSM_ZOOM    = 10
OUTPUT_W    = 765  # Proporzionato aspect ratio geografico
OUTPUT_H    = 800
RADAR_ALPHA = 120
GLOBAL_OPACITY = 0.70

# ── OSM Tile helpers ──────────────────────────────────────────────────────────

def _deg2tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """WGS84 → tile OSM (x, y)."""
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def _tile2deg(x: int, y: int, zoom: int) -> tuple[float, float]:
    """Tile OSM → WGS84 (lat, lon) angolo top-left."""
    n = 2 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return lat, lon


# ── Setup ─────────────────────────────────────────────────────────────────────

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup camera platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BolzanoRadarCamera(coordinator)])


# ── Coordinator ───────────────────────────────────────────────────────────────

class BolzanoRadarCoordinator(DataUpdateCoordinator):
    """Coordinator fetch JSON e gestione frames."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.entry_id = entry_id
        self.frames: list[str] = []
        self.current_frame_index: int = 0
        self.last_data: Any = None
        self.is_paused: bool = False
        self.force_refresh_camera: bool = False
        self.camera_entities: list = [] 

    async def _async_update_data(self) -> Any:
        """Fetch JSON e estrai frames rainfall_intensity."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                JSON_URL, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"HTTP {resp.status}")
                data = await resp.json()

            new_frames = []
            for layer in data:
                if layer.get("weather_type") == "rainfall_intensity":
                    for ts in layer.get("timeseries", []):
                        if ts.get("type") == "pastFrames":
                            base = "https://static-meteo.provincia.bz.it/raster-data/website/"
                            new_frames = [base + u for u in ts.get("intervals", [])]
                            break
                    if new_frames:
                        break

            if not new_frames:
                raise UpdateFailed("Nessun frame rainfall_intensity trovato")

            self.frames = new_frames
            self.current_frame_index = 0
            self.last_data = data
            _LOGGER.info("Caricati %d frames radar", len(self.frames))
            return data

        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(str(err)) from err


# ── Camera Entity ─────────────────────────────────────────────────────────────

class BolzanoRadarCamera(Camera):
    """Camera entity: basemap OSM grigio + radar vivido 2FPS."""

    _attr_name = "Bolzano Radar Piogge"
    _attr_icon = "mdi:radar"
    _attr_has_entity_name = True
    _attr_is_streaming = False
    _attr_is_on = True
    _attr_supported_features = CameraEntityFeature(0)

    def __init__(self, coordinator: BolzanoRadarCoordinator) -> None:
        super().__init__()
        self.coordinator = coordinator
        self._attr_unique_id = f"{DOMAIN}.radar_camera"
        self._basemap: Image.Image | None = None
        self._last_radar_url: str | None = None
        self._last_composite: bytes | None = None
        self._attr_extra_state_attributes: dict[str, Any] = {
            "total_frames": 0,
            "current_frame": 0,
            "fps": "2.0",
            "frame_time": "N/A",
            "current_url": None,
        }

    @property
    def available(self) -> bool:
        return bool(self.coordinator.frames)

    def _update_attributes(self) -> None:
        """Aggiorna attributi con info frame corrente."""
        if not self.coordinator.frames:
            return

        current_url = self.coordinator.frames[self.coordinator.current_frame_index]
        timestamp_str = current_url.split('/')[-1].split('.')[0][-14:]

        frame_time = "N/A"
        if len(timestamp_str) == 14:
            try:
                dt = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
                frame_time = dt.strftime('%d %b %H:%M')
            except ValueError:
                pass

        self._attr_extra_state_attributes = {
            "total_frames": len(self.coordinator.frames),
            "current_frame": self.coordinator.current_frame_index + 1,
            "fps": "2.0",
            "frame_time": frame_time,
            "current_url": current_url,
        }

    # ── Basemap OSM in Scala di Grigi ─────────────────────────────────────────

    async def _fetch_basemap(self) -> Image.Image | None:
        """Scarica tiles OSM VIEW bbox, converti grigi, assembla (cached)."""
        if self._basemap is not None:
            return self._basemap

        session = async_get_clientsession(self.hass)
        headers = {"User-Agent": "HomeAssistant-BolzanoRadar/1.0"}

        x_min, y_max = _deg2tile(VIEW_LAT_MIN, VIEW_LON_MIN, OSM_ZOOM)
        x_max, y_min = _deg2tile(VIEW_LAT_MAX, VIEW_LON_MAX, OSM_ZOOM)

        tiles_w = x_max - x_min + 1
        tiles_h = y_max - y_min + 1
        full_img = Image.new("RGBA", (tiles_w * 256, tiles_h * 256))

        for tx in range(x_min, x_max + 1):
            for ty in range(y_min, y_max + 1):
                url = f"https://tile.openstreetmap.org/{OSM_ZOOM}/{tx}/{ty}.png"
                try:
                    async with session.get(
                        url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            tile_data = await resp.read()
                            tile_img = Image.open(io.BytesIO(tile_data)).convert("RGBA")
                            px = (tx - x_min) * 256
                            py = (ty - y_min) * 256
                            full_img.paste(tile_img, (px, py))
                        else:
                            _LOGGER.warning(
                                "Tile HTTP %s: %s/%s/%s", resp.status, OSM_ZOOM, tx, ty
                            )
                except Exception as err:
                    _LOGGER.warning("Tile fallita %s/%s/%s: %s", OSM_ZOOM, tx, ty, err)

        # Crop esatto VIEW bbox
        lat_top, lon_left = _tile2deg(x_min, y_min, OSM_ZOOM)
        lat_bot, lon_right = _tile2deg(x_max + 1, y_max + 1, OSM_ZOOM)

        full_w, full_h = full_img.size
        span_lon = lon_right - lon_left
        span_lat = lat_top - lat_bot

        left   = int((VIEW_LON_MIN - lon_left) / span_lon * full_w)
        right  = int((VIEW_LON_MAX - lon_left) / span_lon * full_w)
        top    = int((lat_top - VIEW_LAT_MAX) / span_lat * full_h)
        bottom = int((lat_top - VIEW_LAT_MIN) / span_lat * full_h)

        cropped = full_img.crop((left, top, right, bottom))

        # ✅ Scala di grigi + più scura per far risaltare radar
        grayscale = cropped.convert("L")
        grayscale = ImageEnhance.Brightness(grayscale).enhance(0.85)  # Più scura
        grayscale = ImageEnhance.Contrast(grayscale).enhance(1.3)     # Più contrasto

        self._basemap = grayscale.convert("RGBA").resize(
            (OUTPUT_W, OUTPUT_H), Image.LANCZOS
        )
        _LOGGER.info(
            "Basemap OSM grigia assemblata (%dx%d tiles zoom %s)",
            tiles_w, tiles_h, OSM_ZOOM
        )
        return self._basemap

    # ── Compositing ───────────────────────────────────────────────────────────

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Compone basemap grigia + radar vivido con alpha_composite."""
        if not self.coordinator.frames:
            return None

        url = self.coordinator.frames[self.coordinator.current_frame_index]


        if url != self._last_radar_url or self.coordinator.force_refresh_camera:
            self._last_radar_url = None
            self._last_composite = None
            self.coordinator.force_refresh_camera = False  # Reset flag

        if self._last_composite is not None:
            return self._last_composite


        session = async_get_clientsession(self.hass)

        # 1. Basemap OSM grigia (cached)
        basemap = await self._fetch_basemap()
        if basemap is None:
            return None

        # 2. Scarica frame radar
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return self._last_composite
                radar_data = await resp.read()
        except Exception as err:
            _LOGGER.error("Errore download radar: %s", err)
            return self._last_composite

        # 3. Crop radar proporzionale su VIEW bbox
        try:
            radar_full = Image.open(io.BytesIO(radar_data)).convert("RGBA")

            radar_span_lon = RADAR_LON_MAX - RADAR_LON_MIN
            radar_span_lat = RADAR_LAT_MAX - RADAR_LAT_MIN

            rel_left   = (VIEW_LON_MIN - RADAR_LON_MIN) / radar_span_lon
            rel_right  = (VIEW_LON_MAX - RADAR_LON_MIN) / radar_span_lon
            rel_top    = (RADAR_LAT_MAX - VIEW_LAT_MAX) / radar_span_lat
            rel_bottom = (RADAR_LAT_MAX - VIEW_LAT_MIN) / radar_span_lat

            rw, rh = radar_full.size
            crop_left   = int(rel_left   * rw)
            crop_right  = int(rel_right  * rw)
            crop_top    = int(rel_top    * rh)
            crop_bottom = int(rel_bottom * rh)

            radar_cropped = radar_full.crop(
                (crop_left, crop_top, crop_right, crop_bottom)
            )
            radar_resized = radar_cropped.resize(
                (OUTPUT_W, OUTPUT_H), Image.LANCZOS
            )

            # 4. ✅ Boost saturazione e contrasto colori radar
            r, g, b, a = radar_resized.split()
            radar_rgb = Image.merge("RGB", (r, g, b))

            radar_rgb = ImageEnhance.Color(radar_rgb).enhance(2.2)     # +150% saturazione
            radar_rgb = ImageEnhance.Contrast(radar_rgb).enhance(1.5)  # +80% contrasto

            r2, g2, b2 = radar_rgb.split()

            # ✅ Alpha: soglia netta (elimina pixel quasi-trasparenti)
            a_clean = a.point(lambda x: 255 if x > 60 else 0)
            radar_final = Image.merge("RGBA", (r2, g2, b2, a_clean))

            # 5. ✅ alpha_composite: preserva colori originali radar
            GLOBAL_OPACITY = 0.65  # 65% opaco → regola qui (0.4=molto trasparente, 0.8=opaco)
            a_transparent = a.point(lambda x: int(x * GLOBAL_OPACITY) if x > 10 else 0)
            radar_final = Image.merge("RGBA", (r2, g2, b2, a_transparent))
            base_rgba = basemap.convert("RGBA")
            result_rgba = Image.alpha_composite(base_rgba, radar_final)

            # 6. Salva JPEG
            out = io.BytesIO()
            result_rgba.convert("RGB").save(out, format="JPEG", quality=90)
            self._last_composite = out.getvalue()
            self._last_radar_url = url                     
            self._update_attributes()
            return self._last_composite

        except Exception as err:
            _LOGGER.error("Errore compositing: %s", err)
            return self._last_composite

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def async_added_to_hass(self) -> None:
        # ✅ Registra questa entity nel coordinator
        self.coordinator.camera_entities.append(self)

        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
        await self.coordinator.async_refresh()
        self.hass.async_create_background_task(
            self._fetch_basemap(), "bolzano_basemap_prefetch"
        )

    async def async_will_remove_from_hass(self) -> None:
        if self in self.coordinator.camera_entities:
            self.coordinator.camera_entities.remove(self)




    def invalidate_cache(self) -> None:
        """✅ Invalida cache composito - forza nuovo render."""
        self._last_radar_url = None
        self._last_composite = None

