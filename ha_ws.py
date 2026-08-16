#!/usr/bin/env python3
"""Client websocket minimal pour l'API Lovelace de Home Assistant (pur Python, sans dépendance)."""
import base64, hashlib, json, os, socket, struct, sys
from pathlib import Path

def load_env():
    env = {}
    for p in (Path(__file__).resolve().parent / ".env", Path.home() / ".env"):
        if not p.exists():
            continue
        for line in open(p):
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

class Ws:
    def __init__(self, host, port, path):
        self.sock = socket.create_connection((host, port), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
               f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            resp += self.sock.recv(4096)
        if b"101" not in resp.split(b"\r\n", 1)[0]:
            raise RuntimeError("handshake échoué: " + resp[:200].decode(errors="replace"))
        self.buf = resp.split(b"\r\n\r\n", 1)[1]

    def send(self, obj):
        payload = json.dumps(obj).encode()
        mask = os.urandom(4)
        hdr = bytearray([0x81])
        n = len(payload)
        if n < 126: hdr.append(0x80 | n)
        elif n < 65536: hdr.append(0x80 | 126); hdr += struct.pack(">H", n)
        else: hdr.append(0x80 | 127); hdr += struct.pack(">Q", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(hdr) + mask + masked)

    def recv(self):
        def read(n):
            while len(self.buf) < n:
                chunk = self.sock.recv(65536)
                if not chunk: raise EOFError("socket fermé")
                self.buf += chunk
            data, self.buf = self.buf[:n], self.buf[n:]
            return data
        hdr = read(2)
        fin = hdr[0] & 0x80; op = hdr[0] & 0x0F
        ln = hdr[1] & 0x7F
        if ln == 126: ln = struct.unpack(">H", read(2))[0]
        elif ln == 127: ln = struct.unpack(">Q", read(8))[0]
        payload = read(ln)
        if hdr[1] & 0x80:  # masqué (côté serveur HA: non masqué normalement)
            mask = payload[:4]; payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload[4:]))
        if op == 1: return json.loads(payload.decode())
        if op == 8: raise EOFError("close frame")
        if op == 9:  # ping -> pong
            self.sock.sendall(bytes([0x8A]) + struct.pack(">B", ln) + payload)
            return self.recv()
        return self.recv()

    def close(self):
        try: self.sock.close()
        except Exception: pass

def main():
    env = load_env()
    url = env.get("HASS_URL") or env.get("HA_URL") or os.environ.get("HASS_URL") or "http://localhost:8123"
    token = env.get("HA_TOKEN") or env.get("HASS_TOKEN")
    if not token: sys.exit("token introuvable")
    host = url.replace("http://", "").replace("https://", "").split(":")[0]
    port = int(url.split(":")[-1].rstrip("/")) if ":" in url.replace("http://", "").split("/")[0] else 8123
    ws = Ws(host, port, "/api/websocket")
    msg_id = 0
    def cmd(cmdtype, **kw):
        nonlocal msg_id
        msg_id += 1
        ws.send({"id": msg_id, "type": cmdtype, **kw})
        while True:
            m = ws.recv()
            if m.get("id") == msg_id:
                if m.get("success") is False:
                    raise RuntimeError(f"{cmdtype} échoué: {m.get('error')}")
                return m.get("result")
    # auth
    while True:
        m = ws.recv()
        if m.get("type") == "auth_required":
            ws.send({"type": "auth", "access_token": token})
        elif m.get("type") == "auth_ok":
            break
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    if action == "list":
        dashboards = cmd("lovelace/dashboards/list")
        print(json.dumps(dashboards, ensure_ascii=False, indent=1))
    elif action == "get":
        dash_id = sys.argv[2]
        cfg = cmd("lovelace/config/get", url_path=dash_id)
        print(json.dumps(cfg, ensure_ascii=False, indent=1))
    elif action == "save":
        dash_id = sys.argv[2]
        cfg = json.load(open(sys.argv[3]))
        r = cmd("lovelace/config/save", url_path=dash_id, config=cfg)
        print("saved:", r)
    elif action == "create":
        title = sys.argv[2]
        r = cmd("lovelace/dashboards/create", title=title, mode="storage")
        print(json.dumps(r, ensure_ascii=False))
    ws.close()

if __name__ == "__main__":
    main()
