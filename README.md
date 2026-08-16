# 🏠 Ha3D — 3D home visualizer for Home Assistant

Interactive 3D visualizer (three.js) of your home with real-time Home Assistant sensors: temperatures, climate, clickable lights, animated doors, solar, batteries. Built-in editor: draw your rooms, place doors and furniture, add your entities — everything saved to a local JSON file.

> **🌍 Languages** — [🇫🇷 Français](README.fr.md) · [🇬🇧 English](README.md)

## ✨ Features

- **3D rendering** of the home (default isometric view, OrbitControls: orbit / zoom / pan)
- **Real-time sensors** from Home Assistant (HA WebSocket → SSE, 60s fallback)
- **3D icons by type**: thermometer (temp), droplet (humidity), snowflake (AC), bulb (light), lightning (power), battery, solar panel, door, alert
- **Clickable 3D lights**: toggle via the HA API (halo + drop shadows)
- **Real animated doors**: walls cut at openings, frames + pivoting leaves driven by HA state (on = open, smooth transition)
- **Merged walls**: shared walls between rooms are deduplicated (no clipping)
- **Seasonal day/night 🌗**: real sun position from date/time and geolocation (natural sunrise/sunset, adapted lighting and colors), manual modes ☀️/🌙
- **Anti-overlap labels**
- **Debug mode 🔧**:
  - Drag & drop entities (floor X/Z or height Y)
  - Room 🏠, door 🚪 and object 🛋️ editing (drag, wheel or **R** key rotation, ➕ add, 🗑️ delete)
  - **Undo/Redo: Ctrl+Z / Ctrl+Shift+Z** (50 steps)
  - Add / remove HA entities (live search)
  - Saved camera views 🎥, default camera capture
  - Direct server save (automatic backup)
- **24h history** per sensor (chart)
- **Alerts**: open door, low battery, high temperature
- **Type filters**, **PNG capture**

## 🚀 Installation

```bash
git clone https://github.com/v3ry/ha3d.git
cd ha3d

# 1. Configuration: Home Assistant URL + token
cp .env.example .env
#    edit .env: HASS_URL=http://<ha-ip>:8123 and HA_TOKEN=<long-lived token>
#    (Home Assistant Profile > Security > Long-lived access tokens)

# 2. Starting layout (demo house)
cp layout.example.json layout.json

# 3. Run
python3 ha3d_server.py
# → http://127.0.0.1:9125
```

> **Note**: without `layout.json`, the server starts with a demo house — use debug mode 🔧 to draw your rooms and add your entities.

### Access from other devices

```bash
# In .env: expose on the local network
MAISON3D_HOST=0.0.0.0
```

### Systemd (auto-start)

```bash
cp maison3d.service.example ~/.config/systemd/user/maison3d.service
# adapt WorkingDirectory/ExecStart to your install path
systemctl --user daemon-reload
systemctl --user enable --now maison3d
```

### Docker

```bash
cp .env.example .env    # fill HASS_URL + HA_TOKEN
cp layout.example.json layout.json   # or let the auto-generated demo house run

# Build + run
docker compose up -d --build
# → http://127.0.0.1:9125
```

The container runs as a **non-root user**, mounts `layout.json` and `ha3d_layout_backups/` as volumes (persistence + backups). The server writes backups to `HA3D_BACKUP_DIR` (default: `~/ha3d_layout_backups`, overridable).

### Check your configuration

```bash
python3 tools/check_config.py   # .env, HA connection, layout validity
```

## ⚙️ Configuration

- **`.env`**: `HASS_URL`, `HA_TOKEN` (required); `MAISON3D_HOST` (default `127.0.0.1`), `MAISON3D_PORT` (default `9125`); `HA3D_LAT`/`HA3D_LON` (optional — auto-detected from HA config by default); `HA3D_BACKUP_DIR` (backup directory, default `~/ha3d_layout_backups`)
- **`layout.json`**: rooms, entities, positions, camera — generated with the 3D editor (debug mode), saved with automatic backup to `~/ha3d_layout_backups/`

## 🌍 Languages

The interface is available in **10 languages**: 🇫🇷 Français · 🇬🇧 English · 🇩🇪 Deutsch · 🇪🇸 Español · 🇮🇹 Italiano · 🇵🇹 Português · 🇳🇱 Nederlands · 🇵🇱 Polski · 🇹🇷 Türkçe · 🇷🇺 Русский.

The language is auto-detected from your browser (`navigator.language`) and can be switched anytime with the **selector in the top-left HUD**. Your choice is remembered (`localStorage`).

## 🛡️ Security

- **The server listens on `127.0.0.1` by default** — only expose it (`MAISON3D_HOST=0.0.0.0`) on a trusted network
- Write endpoints (`/api/save-layout`, `/api/toggle`) are **not authenticated**: never expose this server to the Internet
- Your data stays local: `layout.json` (rooms, entities, GPS position) is git-ignored
- The HA token is only read from `.env` (never committed)

## 🧰 Development

```bash
python3 -m unittest test_ha3d_server   # server tests + layout validation
```

## 🗂️ Architecture

| File | Role |
|---|---|
| `ha3d_server.py` | HTTP server + HA API proxy (layout, status, history, toggle, save-layout, entities, SSE) |
| `index.html` | three.js client (rendering, interactions, debug mode) — no npm dependencies |
| `layout.json` | Local configuration (rooms, entities, positions, camera) — **not versioned** |
| `layout.example.json` | Demo layout |
| `models/` | 3D glTF models (CC0 — poly.pizza + Khronos), served by `/models/*.glb` |
| `ha_ws.py` | HA WebSocket client (Lovelace dashboard driving) |
| `tools/` | Utilities: `check_config.py` (pre-launch check), `fetch_furniture.py` (CC0 catalog) |
| `Dockerfile`, `docker-compose.yml` | Container (non-root user, layout + backups volumes) |

## 📦 3D model catalog

The object panel lets you choose the type: **🟫 Simple box** or **🧊 3D model** (list loaded from `/api/models`). Drop a `.glb` into `models/` — it automatically appears in the list.

28 included models, all **CC0**: sofas, tables, beds, chairs, wardrobes, storage, appliances, bathroom, lamps, plant (source [poly.pizza](https://poly.pizza) + Khronos Sample Models) — see `models/README.md` for detailed attribution.

## 📄 License

[MIT](LICENSE) © 2026 v3ry — free to use, including commercially.
