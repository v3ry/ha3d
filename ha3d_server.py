#!/usr/bin/env python3
"""
Maison 3D — visualiseur 3D interactif (three.js) des capteurs Home Assistant.
Serveur Python http.server + proxy HA, calqué sur le pattern hvac_web.py.
Port : 9125 (libre à côté du 9123 HVAC).
"""
import json
import os
import queue
import threading
import time
import urllib.request
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
PORT = int(os.environ.get("MAISON3D_PORT", "9125"))
HOST = os.environ.get("MAISON3D_HOST", "127.0.0.1")

# --- HA credentials ---------------------------------------------------------
# Sources : variables d'environnement, ou fichier .env (./.env puis ~/.env)
def _load_env():
    env = {}
    for env_file in (BASE_DIR / ".env", Path.home() / ".env"):
        if not env_file.exists():
            continue
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

ENV = _load_env()
HA_URL = (ENV.get("HASS_URL") or ENV.get("HA_URL") or os.environ.get("HASS_URL")
          or "http://localhost:8123").rstrip("/")
HA_TOKEN = ENV.get("HASS_TOKEN") or ENV.get("HA_TOKEN") or os.environ.get("HASS_TOKEN")


def ha_headers():
    return {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}


def fetch_ha(path: str, timeout: int = 10):
    req = urllib.request.Request(f"{HA_URL}{path}", headers=ha_headers())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_history(entity_id: str, hours: int = 24) -> dict:
    """Historique HA (minimal_response) pour une entité → séries [ts, value]."""
    from datetime import datetime, timedelta, timezone

    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    url = f"/api/history/period/{start}?filter_entity_id={entity_id}&minimal_response&no_attributes"
    try:
        data = fetch_ha(url, timeout=15)
    except Exception as e:
        return {"error": str(e), "points": []}
    points = []
    if data:
        for e in data[0]:
            try:
                points.append({
                    "t": e.get("last_changed"),
                    "v": float(e.get("state")),
                })
            except (TypeError, ValueError):
                continue
    return {"entity_id": entity_id, "points": points}


# --- Layout + capteurs ------------------------------------------------------
# Si layout.json est absent (installation fraîche), génère une maison de démo
def _demo_layout():
    return {
        "house_name": "Ha3D — Demo house",
        "levels": [{
            "name": "rdc", "y_floor": 0, "height": 2.6, "rooms": [
                {"id": "salon", "name": "Living room", "x": 0, "z": 0, "w": 6, "d": 5, "color": "#f0e68c"},
                {"id": "cuisine", "name": "Kitchen", "x": 6, "z": 0, "w": 4, "d": 5, "color": "#98fb98"},
                {"id": "chambre", "name": "Bedroom", "x": 0, "z": 5, "w": 5, "d": 4, "color": "#87ceeb"},
                {"id": "sdb", "name": "Bathroom", "x": 5, "z": 5, "w": 3, "d": 4, "color": "#d8bfd8"},
                {"id": "bureau", "name": "Office", "x": 8, "z": 5, "w": 4, "d": 4, "color": "#ffcc99"},
            ],
            "furniture": [
                {"id": "demo_canap", "type": "model", "name": "Sofa", "model": "Canape", "room": "salon", "x": 0.25, "z": 0.55, "scale": 1.1},
                {"id": "demo_tv", "type": "model", "name": "TV", "model": "TV", "room": "salon", "x": 0.82, "z": 0.5, "scale": 1.0, "rotY": 3.14},
                {"id": "demo_tablebasse", "type": "model", "name": "Coffee table", "model": "TableBasse", "room": "salon", "x": 0.5, "z": 0.62, "scale": 1.0},
                {"id": "demo_table", "type": "model", "name": "Table", "model": "TableManger", "room": "cuisine", "x": 0.5, "z": 0.5, "scale": 1.0},
                {"id": "demo_chaise1", "type": "model", "name": "Chair", "model": "Chaise", "room": "cuisine", "x": 0.5, "z": 0.25, "scale": 0.9},
                {"id": "demo_chaise2", "type": "model", "name": "Chair", "model": "Chaise", "room": "cuisine", "x": 0.5, "z": 0.75, "scale": 0.9, "rotY": 3.14},
                {"id": "demo_frigo", "type": "model", "name": "Fridge", "model": "Frigo", "room": "cuisine", "x": 0.88, "z": 0.5, "scale": 1.0},
                {"id": "demo_lit", "type": "model", "name": "Bed", "model": "Lit", "room": "chambre", "x": 0.25, "z": 0.5, "scale": 1.0},
                {"id": "demo_armoire", "type": "model", "name": "Wardrobe", "model": "Armoire", "room": "chambre", "x": 0.85, "z": 0.5, "scale": 1.0},
                {"id": "demo_baignoire", "type": "model", "name": "Bathtub", "model": "Baignoire", "room": "sdb", "x": 0.3, "z": 0.5, "scale": 1.0},
                {"id": "demo_wc", "type": "model", "name": "Toilet", "model": "WC", "room": "sdb", "x": 0.75, "z": 0.5, "scale": 1.0},
                {"id": "demo_bureau", "type": "model", "name": "Desk", "model": "Bureau", "room": "bureau", "x": 0.5, "z": 0.35, "scale": 1.0},
                {"id": "demo_chaisebureau", "type": "model", "name": "Office chair", "model": "ChaiseBureau", "room": "bureau", "x": 0.5, "z": 0.68, "scale": 1.0, "rotY": 3.14},
                {"id": "demo_plante", "type": "model", "name": "Plant", "model": "Plante", "room": "salon", "x": 0.9, "z": 0.15, "scale": 1.0},
                {"id": "demo_lampadaire", "type": "model", "name": "Floor lamp", "model": "Lampadaire", "room": "salon", "x": 0.1, "z": 0.15, "scale": 1.0},
            ],
        }],
        "sensors": [
            {"entity": "sensor.demo_temperature_salon", "name": "Living room temp", "room": "salon", "pos": [3, 1.7, 2.2]},
            {"entity": "sensor.demo_temperature_chambre", "name": "Bedroom temp", "room": "chambre", "pos": [2.5, 1.7, 2.5]},
            {"entity": "sensor.demo_humidity_salon", "name": "Living room humidity", "room": "salon", "pos": [4.2, 1.7, 1.5]},
            {"entity": "light.demo_lamp", "name": "Lamp", "room": "salon", "pos": [5.2, 1.2, 3.8]},
            {"entity": "switch.demo_plug", "name": "Plug", "room": "bureau", "pos": [9.5, 1.2, 6.5]},
            {"entity": "binary_sensor.demo_door", "name": "Front door", "room": "salon", "pos": [0.2, 1.5, 0.2]},
        ],
        "doors": [
            {"id": "porte_salon_cuisine", "name": "Salon ↔ Kitchen", "room": "salon", "rotY": 0, "fixed": 0, "t": 6, "width": 0.9, "height": 2.1, "hinge": "a0", "openSign": 1},
            {"id": "porte_salon_chambre", "name": "Salon ↔ Bedroom", "room": "salon", "rotY": 1.5708, "fixed": 0, "t": 5, "width": 0.9, "height": 2.1, "hinge": "a0", "openSign": 1},
            {"id": "porte_chambre_sdb", "name": "Bedroom ↔ Bathroom", "room": "chambre", "rotY": 1.5708, "fixed": 5, "t": 5, "width": 0.9, "height": 2.1, "hinge": "a0", "openSign": 1},
        ],
        "default_camera": {"pos": [-18, 14, 14], "target": [5.5, 1, 3.5]},
    }


def _load_layout():
    f = BASE_DIR / "layout.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    print("layout.json absent — utilisation de la maison de démonstration")
    return _demo_layout()


LAYOUT = _load_layout()
# Vrai si le serveur tourne avec la maison de démo (pas de layout.json)
IS_DEMO = not (BASE_DIR / "layout.json").exists()

# Cache temps réel : entité -> {state, unit, attrs} alimenté par le WebSocket HA
STATE_CACHE = {}
STATE_CACHE_LOCK = threading.Lock()
SSE_CLIENTS = set()
SSE_LOCK = threading.Lock()


def _tracked_ids() -> set:
    """Entités suivies en temps réel (capteurs du layout + sum_with + portes animées)."""
    ids = set()
    for s in LAYOUT["sensors"]:
        ids.add(s["entity"])
        if s.get("sum_with"):
            ids.add(s["sum_with"])
    for d in LAYOUT.get("doors", []):
        if d.get("entity"):
            ids.add(d["entity"])
    return ids


def _door_ids() -> set:
    """Entités des portes animées (état on = ouverte)."""
    return {d["entity"] for d in LAYOUT.get("doors", []) if d.get("entity")}


def _demo_sensor_state(s: dict) -> tuple:
    """Valeur simulée réaliste pour le mode démo, selon le type d'entité."""
    eid = s["entity"]
    name = (s.get("label") or eid).lower()
    # Déterministe : stable entre les rechargements
    seed = sum(ord(c) for c in eid)
    base = (seed % 100) / 100.0
    if eid.startswith(("sensor.temperature",)) or "temp" in name and "hum" not in name:
        return f"{19 + round(base * 8, 1)}", "°C"
    if eid.startswith(("sensor.humidity",)) or "hum" in name:
        return f"{40 + round(base * 30)}", "%"
    if eid.startswith(("binary_sensor.",)) or "door" in name or "porte" in name:
        return "off", ""
    if eid.startswith(("light.", "switch.", "fan.")):
        return "on" if base > 0.5 else "off", ""
    if eid.startswith(("sensor.power", "sensor.energy", "sensor.conso")) or "power" in name:
        return f"{round(base * 400 + 5)}", "W"
    if eid.startswith(("sensor.battery",)) or "battery" in name:
        return f"{round(base * 40 + 55)}", "%"
    if "solar" in name:
        return f"{round(base * 2500 + 500)}", "W"
    return "21.5", "°C"


def _status_entry(s: dict, by_id: dict) -> dict:
    """Construit l'entrée de statut d'un capteur configuré depuis un dict états."""
    sid = s["entity"]
    sum_with = s.get("sum_with")

    def num(eid):
        e = by_id.get(eid)
        if e is None:
            return None
        try:
            return float(e.get("state"))
        except (TypeError, ValueError):
            return None

    if sum_with:
        v1 = num(sid)
        v2 = num(sum_with)
        if v1 is None and v2 is None:
            return {"entity": sid, "state": "unavailable", "unit": "", "attrs": {}}
        total = (abs(v1) if v1 is not None else 0) + (abs(v2) if v2 is not None else 0)
        unit = by_id.get(sid, {}).get("unit", "") or "W"
        return {
            "entity": sid,
            "state": str(total),
            "unit": unit,
            "attrs": {"friendly_name": s.get("label", sid), "is_sum": True},
        }

    e = by_id.get(sid)
    if e is None:
        # Mode démo : simule une valeur réaliste selon le type d'entité
        if IS_DEMO:
            sim = _demo_sensor_state(s)
            return {"entity": sid, "state": sim[0], "unit": sim[1], "attrs": {"friendly_name": s.get("label", sid), "demo": True}}
        return {"entity": sid, "state": "unavailable", "unit": "", "attrs": {}}
    attrs = e.get("attrs", {})
    return {
        "entity": sid,
        "state": e.get("state"),
        "unit": e.get("unit", ""),
        "attrs": attrs,
    }


def _doors_status(by_id: dict) -> list:
    """États des portes animées pour le snapshot SSE."""
    out = []
    for d in LAYOUT.get("doors", []):
        eid = d.get("entity")
        if not eid:
            continue
        e = by_id.get(eid) or {}
        out.append({"id": d.get("id"), "entity": eid, "state": e.get("state", "unavailable")})
    return out


def _status_geo():
    """Coordonnées de la maison : env HA3D_LAT/HA3D_LON, sinon depuis la config HA."""
    lat = os.environ.get("HA3D_LAT")
    lon = os.environ.get("HA3D_LON")
    if lat and lon:
        try:
            return float(lat), float(lon)
        except ValueError:
            pass
    try:
        cfg = fetch_ha("/api/config")
        if isinstance(cfg, dict) and cfg.get("latitude") is not None:
            return float(cfg["latitude"]), float(cfg["longitude"])
    except Exception:
        pass
    return None, None


def get_status() -> dict:
    """Renvoie l'état en direct de chaque capteur configuré.

    Utilise le cache temps réel (WebSocket) s'il est chaud, sinon bascule
    sur un fetch REST (fallback au démarrage / si le WS est down).
    Inclut les coordonnées géographiques (jour/nuit saisonnier côté client).
    """
    lat, lon = _status_geo()
    # Mode démo : pas besoin d'interroger HA, valeurs simulées déterministes
    if IS_DEMO:
        out = [_status_entry(s, {}) for s in LAYOUT["sensors"]]
        return {"house_name": LAYOUT["house_name"], "sensors": out, "doors": [], "geo": {"lat": lat, "lon": lon}, "demo": True}
    with STATE_CACHE_LOCK:
        cache_hot = len(STATE_CACHE) >= len(_tracked_ids()) * 0.5
    if cache_hot:
        by_id = dict(STATE_CACHE)
        out = [_status_entry(s, by_id) for s in LAYOUT["sensors"]]
        return {"house_name": LAYOUT["house_name"], "sensors": out, "doors": _doors_status(by_id), "geo": {"lat": lat, "lon": lon}, "demo": IS_DEMO}

    # Fallback REST
    entity_ids = _tracked_ids()
    try:
        states = fetch_ha("/api/states")
    except Exception as e:
        return {"error": str(e), "sensors": [], "geo": {"lat": lat, "lon": lon}, "demo": IS_DEMO}
    by_id = {}
    for st in states:
        eid = st.get("entity_id", "")
        attrs = st.get("attributes", {})
        by_id[eid] = {
            "state": st.get("state"),
            "unit": attrs.get("unit_of_measurement", ""),
            "attrs": {
                "friendly_name": attrs.get("friendly_name", eid),
                "temperature": attrs.get("temperature"),
                "current_temperature": attrs.get("current_temperature"),
                "humidity": attrs.get("humidity"),
                "battery_level": attrs.get("battery_level"),
                "hvac_action": attrs.get("hvac_action"),
                "hvac_mode": attrs.get("hvac_mode"),
            },
        }
    # Ne garde que les entités suivies dans le cache (le WS renvoie tous les états HA)
    with STATE_CACHE_LOCK:
        STATE_CACHE.update({k: v for k, v in by_id.items() if k in entity_ids})
    out = [_status_entry(s, by_id) for s in LAYOUT["sensors"]]
    return {"house_name": LAYOUT["house_name"], "sensors": out, "doors": _doors_status(by_id), "geo": {"lat": lat, "lon": lon}, "demo": IS_DEMO}


def parse_ha_url(ha_url: str) -> tuple:
    """Extrait (host, port) d'une URL Home Assistant (robuste : https, chemins, IPv6)."""
    _u = urlparse(ha_url)
    return _u.hostname or "127.0.0.1", _u.port or 8123


def _sse_broadcast(obj: dict):
    payload = "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"
    with SSE_LOCK:
        for q in list(SSE_CLIENTS):
            try:
                q.put_nowait(payload)
            except queue.Full:
                # Client trop lent : sa file est saturée → on le déconnecte
                SSE_CLIENTS.discard(q)
            except Exception:
                SSE_CLIENTS.discard(q)


def _ws_ha_loop():
    """Thread : s'abonne aux state_changed de HA via WebSocket et met à jour le cache."""
    from ha_ws import Ws  # client websocket minimal, même dossier

    host, port = parse_ha_url(HA_URL)
    backoff = 5
    while True:
        try:
            ws = Ws(host, port, "/api/websocket")
            # Auth
            while True:
                m = ws.recv()
                if not m:
                    continue
                t = m.get("type")
                if t == "auth_required":
                    ws.send({"type": "auth", "access_token": HA_TOKEN})
                elif t == "auth_ok":
                    break
                elif t == "auth_invalid":
                    raise ConnectionError("auth_invalid — token HA invalide ou expiré")
            ws.send({"id": 1, "type": "subscribe_events", "event_type": "state_changed"})
            print("🟢 WebSocket HA connecté (temps réel)")
            backoff = 5  # connexion OK : on repart de la base
            tracked = _tracked_ids()
            door_ids = _door_ids()
            while True:
                m = ws.recv()
                if not m or m.get("type") != "event":
                    continue
                ev = m.get("event", {})
                if ev.get("event_type") != "state_changed":
                    continue
                data = ev.get("data", {})
                eid = data.get("entity_id", "")
                if eid not in tracked:
                    continue
                ns = data.get("new_state") or {}
                attrs = ns.get("attributes", {})
                entry = {
                    "state": ns.get("state"),
                    "unit": attrs.get("unit_of_measurement", ""),
                    "attrs": {
                        "friendly_name": attrs.get("friendly_name", eid),
                        "temperature": attrs.get("temperature"),
                        "current_temperature": attrs.get("current_temperature"),
                        "humidity": attrs.get("humidity"),
                        "battery_level": attrs.get("battery_level"),
                        "hvac_action": attrs.get("hvac_action"),
                        "hvac_mode": attrs.get("hvac_mode"),
                    },
                }
                with STATE_CACHE_LOCK:
                    STATE_CACHE[eid] = entry
                # Recalcule les capteurs du layout concernés (y compris sum_with)
                updates = []
                with STATE_CACHE_LOCK:
                    by_id = dict(STATE_CACHE)
                for s in LAYOUT["sensors"]:
                    if s["entity"] == eid or s.get("sum_with") == eid:
                        updates.append(_status_entry(s, by_id))
                for u in updates:
                    _sse_broadcast({"type": "update", **u})
                # Porte animée : broadcast de l'état même si ce n'est pas un capteur du layout
                if eid in door_ids:
                    with STATE_CACHE_LOCK:
                        _entry = dict(STATE_CACHE.get(eid) or {})
                    _sse_broadcast({"type": "update", "entity": eid, **_entry})
        except Exception as e:
            msg = str(e)
            delay = backoff
            if "auth_invalid" in msg:
                delay = 60
                print(f"🔴 WebSocket HA : {msg} — nouvel essai dans {delay} s")
            else:
                print(f"⚠️ WebSocket HA: {msg} — reconnexion dans {delay} s")
            time.sleep(delay)
            backoff = min(backoff * 2, 60)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # silence

    def _send(self, code: int, body: str, ctype: str = "application/json"):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b)

    def _send_cors_ok(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _handle_sse(self):
        """Server-Sent Events : snapshot initial puis mises à jour temps réel."""
        q = queue.Queue(maxsize=100)  # bornée : un client lent est déconnecté plutôt que de saturer la RAM
        with SSE_LOCK:
            SSE_CLIENTS.add(q)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            # Snapshot initial
            snap = json.dumps({"type": "snapshot", **get_status()}, ensure_ascii=False)
            self.wfile.write(f"data: {snap}\n\n".encode("utf-8"))
            self.wfile.flush()
            while True:
                try:
                    payload = q.get(timeout=15)
                    self.wfile.write(payload.encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    # keepalive
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with SSE_LOCK:
                SSE_CLIENTS.discard(q)

    def do_OPTIONS(self):
        self._send_cors_ok()

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/models/"):
            # Servir les modèles 3D .glb (chemin sûr)
            name = path[len("/models/"):]
            if "/" in name or ".." in name:
                return self._send(404, json.dumps({"error": "bad path"}))
            f = BASE_DIR / "models" / name
            if f.exists() and f.suffix.lower() == ".glb":
                data = f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "model/gltf-binary")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(data)
                return
            return self._send(404, json.dumps({"error": "model not found"}))
        if path in ("/", "/index.html"):
            html = (BASE_DIR / "index.html").read_text(encoding="utf-8")
            return self._send(200, html, "text/html; charset=utf-8")
        if path == "/api/layout":
            return self._send(200, json.dumps(LAYOUT, ensure_ascii=False))
        if path == "/api/models":
            # Liste des modèles 3D disponibles (fichiers .glb du dossier models/)
            models = sorted(p.stem for p in (BASE_DIR / "models").glob("*.glb"))
            return self._send(200, json.dumps({"models": models}, ensure_ascii=False))
        if path == "/api/entities":
            from urllib.parse import parse_qs
            q = parse_qs(urlparse(self.path).query).get("q", [""])[0]
            return self._send(200, json.dumps(get_entities(q), ensure_ascii=False))
        if path == "/api/status":
            return self._send(200, json.dumps(get_status(), ensure_ascii=False))
        if path == "/api/events":
            return self._handle_sse()
        if path == "/api/history":
            from urllib.parse import parse_qs
            q = parse_qs(urlparse(self.path).query)
            entity_id = q.get("entity", [""])[0]
            hours = int(q.get("hours", ["24"])[0])
            if not entity_id:
                return self._send(400, json.dumps({"error": "entity missing"}))
            return self._send(200, json.dumps(get_history(entity_id, hours), ensure_ascii=False))
        return self._send(404, json.dumps({"error": "Not found"}))

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/toggle":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            try:
                payload = json.loads(raw)
            except Exception:
                return self._send(400, json.dumps({"ok": False, "error": "bad json"}))
            entity_id = payload.get("entity_id", "")
            if not entity_id:
                return self._send(400, json.dumps({"ok": False, "error": "entity_id missing"}))
            return self._send(200, json.dumps(toggle_entity(entity_id), ensure_ascii=False))
        if path == "/api/save-layout":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            try:
                new_layout = json.loads(raw)
            except Exception:
                return self._send(400, json.dumps({"ok": False, "error": "bad json"}))
            return self._send(200, json.dumps(save_layout(new_layout), ensure_ascii=False))
        return self._send(404, json.dumps({"error": "Not found"}))


def toggle_entity(entity_id: str) -> dict:
    """Bascule une entité (light/switch) via le service homeassistant.toggle."""
    domain = entity_id.split(".")[0] if "." in entity_id else ""
    if domain not in ("light", "switch", "input_boolean", "fan", "group"):
        return {"ok": False, "error": f"domaine non basculable: {domain}"}
    data = json.dumps({"entity_id": entity_id}).encode("utf-8")
    req = urllib.request.Request(
        f"{HA_URL}/api/services/{domain}/toggle",
        data=data,
        headers=ha_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
        return {"ok": True, "entity_id": entity_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_entities(query: str = "") -> list:
    """Liste les entités HA (entity_id, friendly_name, domaine), filtrées par texte."""
    try:
        states = fetch_ha("/api/states")
    except Exception as e:
        return {"error": str(e)}
    q = query.strip().lower()
    out = []
    for st in states:
        eid = st.get("entity_id", "")
        attrs = st.get("attributes") or {}
        name = attrs.get("friendly_name") or eid
        domain = eid.split(".")[0] if "." in eid else ""
        if q and q not in eid.lower() and q not in name.lower():
            continue
        out.append({
            "entity_id": eid,
            "friendly_name": name,
            "domain": domain,
            "state": st.get("state"),
        })
        if len(out) >= 60:
            break
    return {"count": len(out), "entities": out}


def validate_layout(new_layout: dict) -> tuple:
    """Valide la structure d'un layout avant sauvegarde. Retourne (ok, erreur)."""
    if not isinstance(new_layout, dict):
        return False, "layout is not a JSON object"
    if "sensors" not in new_layout or not isinstance(new_layout["sensors"], list):
        return False, "sensors missing or invalid"
    levels = new_layout.get("levels")
    if not isinstance(levels, list) or not levels:
        return False, "levels missing or empty"
    level = levels[0]
    rooms = level.get("rooms", []) if isinstance(level, dict) else None
    if not isinstance(rooms, list) or not rooms:
        return False, "rooms missing or empty"

    # Pièces
    seen_ids = set()
    for r in rooms:
        rid = r.get("id") if isinstance(r, dict) else None
        if not rid:
            return False, "room without id"
        if rid in seen_ids:
            return False, f"duplicate room id: {rid}"
        seen_ids.add(rid)
        pts = r.get("pts")
        if pts:
            if not isinstance(pts, list) or len(pts) < 3:
                return False, f"room '{rid}': invalid polygon (pts < 3 vertices)"
            for p in pts:
                if not isinstance(p, (list, tuple)) or len(p) != 2 or not all(
                        isinstance(v, (int, float)) and v == v for v in p):  # rejette NaN
                    return False, f"room '{rid}': invalid vertex {p}"
        else:
            for k in ("x", "z", "w", "d"):
                v = r.get(k)
                if not isinstance(v, (int, float)) or v != v:
                    return False, f"room '{rid}': invalid {k} ({v})"
            if r.get("w", 0) < 0.5 or r.get("d", 0) < 0.5:
                return False, f"room '{rid}': dimensions too small (< 0.5 m)"

    # Portes
    seen_door_ids = set()
    for d in new_layout.get("doors", []):
        did = d.get("id") if isinstance(d, dict) else None
        if did and did in seen_door_ids:
            return False, f"duplicate door id: {did}"
        if did:
            seen_door_ids.add(did)
        for k in ("t", "width"):
            v = d.get(k)
            if not isinstance(v, (int, float)) or v != v or v <= 0:
                return False, f"door '{did or '?'}': invalid {k} ({v})"

    # Capteurs
    seen_sensors = set()
    for s in new_layout["sensors"]:
        e = s.get("entity") if isinstance(s, dict) else None
        if not e:
            return False, "sensor without entity"
        if e in seen_sensors:
            return False, f"duplicate entity: {e}"
        seen_sensors.add(e)

    # Objets
    furn = level.get("furniture", []) if isinstance(level, dict) else []
    seen_furn = set()
    for f in furn:
        fid = f.get("id") if isinstance(f, dict) else None
        if not fid:
            return False, "object without id"
        if fid in seen_furn:
            return False, f"duplicate object id: {fid}"
        seen_furn.add(fid)

    # Vues caméra enregistrées
    views = new_layout.get("camera_views", [])
    if not isinstance(views, list):
        return False, "camera_views must be a list"
    seen_view_names = set()
    for v in views:
        if not isinstance(v, dict):
            return False, "invalid camera view (not an object)"
        for k in ("pos", "target"):
            arr = v.get(k)
            if not isinstance(arr, (list, tuple)) or len(arr) != 3 or not all(
                    isinstance(x, (int, float)) and x == x for x in arr):
                return False, f"view '{v.get('name', '?')}': invalid {k}"
        vname = v.get("name")
        if vname and vname in seen_view_names:
            return False, f"duplicate view name: {vname}"
        if vname:
            seen_view_names.add(vname)

    return True, ""


def save_layout(new_layout: dict) -> dict:
    """Sauvegarde le layout (positions entités + caméra) dans layout.json, avec backup."""
    ok, err = validate_layout(new_layout)
    if not ok:
        return {"ok": False, "error": f"invalid layout: {err}"}
    try:
        # Backup du fichier actuel (répertoire configurable : HA3D_BACKUP_DIR)
        backup_dir = Path(os.environ.get("HA3D_BACKUP_DIR", BASE_DIR.parent / "ha3d_layout_backups"))
        backup_dir.mkdir(exist_ok=True)
        ts = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"layout_{ts}.json"
        if (BASE_DIR / "layout.json").exists():
            backup_path.write_bytes((BASE_DIR / "layout.json").read_bytes())
        # Écriture du nouveau layout
        out = json.dumps(new_layout, ensure_ascii=False, indent=1)
        (BASE_DIR / "layout.json").write_text(out, encoding="utf-8")
        # Rechargement en mémoire
        global LAYOUT, IS_DEMO
        LAYOUT = new_layout
        IS_DEMO = not (BASE_DIR / "layout.json").exists()
        return {"ok": True, "backup": str(backup_path), "sensors": len(new_layout["sensors"])}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    print(f"🏠 Maison 3D → http://{HOST}:{PORT}")
    # Thread WebSocket HA (temps réel)
    threading.Thread(target=_ws_ha_loop, daemon=True).start()
    # Serveur threadé : indispensable pour les connexions SSE longues
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.daemon_threads = True
    httpd.serve_forever()


if __name__ == "__main__":
    main()
