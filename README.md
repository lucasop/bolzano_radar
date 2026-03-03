# Bolzano Radar


**Integrazione Home Assistant personalizzata** per visualizzare il **radar piogge Bolzano** (Provincia Autonoma di Bolzano) con:

- **Animazione 2 FPS** (frame passati)
- **Basemap OSM grayscale** (mappa scura per far risaltare radar)
- **Slider frame manuale** con pausa/riprendi
- **Attributi live**: ora frame, current/total frames, FPS
- **Leggenda colori** integrabile in Lovelace


## Caratteristiche

| Funzione | Descrizione |
| :-- | :-- |
| **Camera animata** | `camera.bolzano_radar_piogge` - Live view 765x800 |
| **Slider frame** | `number.bolzano_radar_frame` - Naviga manualmente |
| **Servizi** | `bolzano_radar.resume` - Riprendi auto-play |
| **Attributi** | `frame_time`, `current_frame`, `total_frames` |
| **Cache smart** | Basemap OSM cached, radar refresh on-demand |

## Installazione

### Opzione 1: HACS (Raccomandato)

1. **Aggiungi repository** in HACS:

```
https://github.com/lucasop/bolzano_radar
```

2. **Cerca "Bolzano Radar"** → **Download**.
3. **Riavvia** Home Assistant.
4. **Configura** → **Integrazioni** → **+ Aggiungi** → **Bolzano Radar**.

### Opzione 2: Manuale

1. **Scarica** repository in `/config/custom_components/bolzano_radar/`.
2. **Riavvia** Home Assistant.
3. **Configura** → **Integrazioni** → **+ Aggiungi** → **Bolzano Radar**.

## Lovelace Dashboard (Esempio)

```yaml
type: horizontal-stack
cards:
  - type: vertical-stack
    cards:
      - show_state: false
        show_name: false
        camera_view: live
        fit_mode: cover
        type: picture-entity
        entity: camera.bolzano_radar_piogge
        aspect_ratio: "765:800"
      - type: markdown
        content: >
          🕐 **{{ state_attr('camera.bolzano_radar_piogge','frame_time') }}**
          &nbsp;&nbsp; Frame **{{
          state_attr('camera.bolzano_radar_piogge','current_frame') }}** /  {{
          state_attr('camera.bolzano_radar_piogge','total_frames') }} {% if
          state_attr('number.bolzano_radar_frame','is_paused') %} ⏸️ **PAUSA** 
          {% else %} ▶️ **PLAY** {% endif %}
      - type: entities
        entities:
          - entity: number.bolzano_radar_frame
            name: Radar Frame
            icon: mdi:rotate-right
            tap_action:
              action: call-service
              service: bolzano_radar.resume
      - type: picture
        image: /local/legenda_pioggia_90.png
        tap_action: none
        aspect_ratio: "1:5"

```


## Servizi Disponibili

| Servizio | Parametri | Descrizione |
| :-- | :-- | :-- |
| `bolzano_radar.resume` | - | Riprende auto-play 2 FPS |

## Recorder/Log  eclusione entity

```yaml
recorder:
  exclude:
    entities:
      - number.bolzano_radar_frame

logbook:
  exclude:
    entities:
      - number.bolzano_radar_frame
```

## Screenshot

## Risoluzione Problemi

| Problema | Soluzione |
| :-- | :-- |
| **No frames** | Controlla log → JSON radar.bz.it raggiungibile? |
| **Slider desync** | Riavvia HA → Cache invalidata |
| **Mappa lenta** | Basemap cached dopo 1° avvio |

```
Log: Caricati 37 frames radar → OK!
```


## Requisiti

- Home Assistant **2024.2+**
- Pillow **>=10.0** (auto-installato)
- Accesso internet (radar.bz.it, OSM tiles)


## Contributi

Fork → PR su GitHub. Issue per bug/nuove feature.

## Licenza

MIT © [lucasop](https://github.com/lucasop) - [https://github.com/lucasop/bolzano_radar](https://github.com/lucasop/bolzano_radar)

***

⭐ **Star il repo se ti è utile!** 🌧️🗺️
<span style="display:none">[^1][^10][^2][^3][^4][^5][^6][^7][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://community.home-assistant.io/t/custom-component-readme/131133

[^2]: https://github.com/custom-components/readme

[^3]: https://community.home-assistant.io/t/custom-component-yet-another-template-to-help-you-start-quickly-with-cookiecutter/245056

[^4]: https://github.com/PiotrMachowski/Home-Assistant-custom-components-Custom-Templates

[^5]: https://github.com/custom-components/readme/blob/main/README.md

[^6]: https://github.com/custom-components

[^7]: https://www.home-assistant.io/docs/configuration/templating/

[^8]: https://github.com/home-assistant/example-custom-config

[^9]: https://community.home-assistant.io/t/best-practices-to-develop-and-maintain-a-custom-component/339295

[^10]: https://github.com/custom-components/readme/blob/main/custom_components/readme/__init__.py

