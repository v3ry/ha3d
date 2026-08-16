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
        "house_name": "Ma maison (démo)",
        "levels": [{
            "name": "rdc", "y_floor": 0, "height": 2.6, "rooms": [
                {"id": "salon", "name": "Salon", "x": 0, "z": 0, "w": 5, "d": 4, "color": "#f0e68c"},
                {"id": "cuisine", "name": "Cuisine", "x": 5, "z": 0, "w": 3, "d": 4, "color": "#98fb98"},
                {"id": "chambre", "name": "Chambre", "x": 0, "z": 4, "w": 4, "d": 3, "color": "#87ceeb"},
            ],
            "furniture": [
                {"id": "demo_canap", "type": "box", "name": "Canapé", "room": "salon", "x": 0.3, "z": 0.5, "w": 2.0, "d": 0.8, "h": 0.8, "c": "#c9a227"},
                {"id": "demo_table", "type": "box", "name": "Table", "room": "cuisine", "x": 0.5, "z": 0.5, "w": 1.2, "d": 0.8, "h": 0.75, "c": "#8b5a2b"},
                {"id": "demo_lit", "type": "box", "name": "Lit", "room": "chambre", "x": 0.3, "z": 0.4, "w": 1.6, "d": 2.0, "h": 0.5, "c": "#6a9ec4"},
            ],
        }],
        "sensors": [],
        "doors": [],
        "default_camera": {"pos": [-15, 12, 10], "target": [4.5, 1, 10]},
    }


def _load_layout():
    f = BASE_DIR / "layout.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    print("layout.json absent — utilisation de la maison de démonstration")
    return _demo_layout()


LAYOUT = _load_layout()

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
    with STATE_CACHE_LOCK:
        cache_hot = len(STATE_CACHE) >= len(_tracked_ids()) * 0.5
    if cache_hot:
        by_id = dict(STATE_CACHE)
        out = [_status_entry(s, by_id) for s in LAYOUT["sensors"]]
        return {"house_name": LAYOUT["house_name"], "sensors": out, "doors": _doors_status(by_id), "geo": {"lat": lat, "lon": lon}}

    # Fallback REST
    entity_ids = _tracked_ids()
    try:
        states = fetch_ha("/api/states")
    except Exception as e:
        return {"error": str(e), "sensors": [], "geo": {"lat": lat, "lon": lon}}
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
    return {"house_name": LAYOUT["house_name"], "sensors": out, "doors": _doors_status(by_id), "geo": {"lat": lat, "lon": lon}}


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
            return self._send(404, json.dumps({"error": "modèle introuvable"}))
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
                return self._send(400, json.dumps({"error": "entity manquant"}))
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
                return self._send(400, json.dumps({"ok": False, "error": "entity_id manquant"}))
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
        return False, "layout n'est pas un objet JSON"
    if "sensors" not in new_layout or not isinstance(new_layout["sensors"], list):
        return False, "sensors manquant ou invalide"
    levels = new_layout.get("levels")
    if not isinstance(levels, list) or not levels:
        return False, "levels manquant ou vide"
    level = levels[0]
    rooms = level.get("rooms", []) if isinstance(level, dict) else None
    if not isinstance(rooms, list) or not rooms:
        return False, "rooms manquant ou vide"

    # Pièces
    seen_ids = set()
    for r in rooms:
        rid = r.get("id") if isinstance(r, dict) else None
        if not rid:
            return False, "pièce sans id"
        if rid in seen_ids:
            return False, f"id de pièce dupliqué : {rid}"
        seen_ids.add(rid)
        pts = r.get("pts")
        if pts:
            if not isinstance(pts, list) or len(pts) < 3:
                return False, f"pièce « {rid} » : polygone invalide (pts < 3 sommets)"
            for p in pts:
                if not isinstance(p, (list, tuple)) or len(p) != 2 or not all(
                        isinstance(v, (int, float)) and v == v for v in p):  # rejette NaN
                    return False, f"pièce « {rid} » : sommet invalide {p}"
        else:
            for k in ("x", "z", "w", "d"):
                v = r.get(k)
                if not isinstance(v, (int, float)) or v != v:
                    return False, f"pièce « {rid} » : {k} invalide ({v})"
            if r.get("w", 0) < 0.5 or r.get("d", 0) < 0.5:
                return False, f"pièce « {rid} » : dimensions trop petites (< 0.5 m)"

    # Portes
    seen_door_ids = set()
    for d in new_layout.get("doors", []):
        did = d.get("id") if isinstance(d, dict) else None
        if did and did in seen_door_ids:
            return False, f"id de porte dupliqué : {did}"
        if did:
            seen_door_ids.add(did)
        for k in ("t", "width"):
            v = d.get(k)
            if not isinstance(v, (int, float)) or v != v or v <= 0:
                return False, f"porte « {did or '?'} » : {k} invalide ({v})"

    # Capteurs
    seen_sensors = set()
    for s in new_layout["sensors"]:
        e = s.get("entity") if isinstance(s, dict) else None
        if not e:
            return False, "capteur sans entity"
        if e in seen_sensors:
            return False, f"entité dupliquée : {e}"
        seen_sensors.add(e)

    # Objets
    furn = level.get("furniture", []) if isinstance(level, dict) else []
    seen_furn = set()
    for f in furn:
        fid = f.get("id") if isinstance(f, dict) else None
        if not fid:
            return False, "objet sans id"
        if fid in seen_furn:
            return False, f"id d'objet dupliqué : {fid}"
        seen_furn.add(fid)

    # Vues caméra enregistrées
    views = new_layout.get("camera_views", [])
    if not isinstance(views, list):
        return False, "camera_views doit être une liste"
    seen_view_names = set()
    for v in views:
        if not isinstance(v, dict):
            return False, "vue caméra invalide (pas un objet)"
        for k in ("pos", "target"):
            arr = v.get(k)
            if not isinstance(arr, (list, tuple)) or len(arr) != 3 or not all(
                    isinstance(x, (int, float)) and x == x for x in arr):
                return False, f"vue « {v.get('name', '?')} » : {k} invalide"
        vname = v.get("name")
        if vname and vname in seen_view_names:
            return False, f"nom de vue dupliqué : {vname}"
        if vname:
            seen_view_names.add(vname)

    return True, ""


def save_layout(new_layout: dict) -> dict:
    """Sauvegarde le layout (positions entités + caméra) dans layout.json, avec backup."""
    ok, err = validate_layout(new_layout)
    if not ok:
        return {"ok": False, "error": f"layout invalide : {err}"}
    try:
        # Backup du fichier actuel
        backup_dir = BASE_DIR.parent / "ha3d_layout_backups"
        backup_dir.mkdir(exist_ok=True)
        ts = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"layout_{ts}.json"
        if (BASE_DIR / "layout.json").exists():
            backup_path.write_bytes((BASE_DIR / "layout.json").read_bytes())
        # Écriture du nouveau layout
        out = json.dumps(new_layout, ensure_ascii=False, indent=1)
        (BASE_DIR / "layout.json").write_text(out, encoding="utf-8")
        # Rechargement en mémoire
        global LAYOUT
        LAYOUT = new_layout
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
