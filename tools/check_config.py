#!/usr/bin/env python3
"""Vérifie la configuration Ha3D avant lancement : .env, connexion HA, layout.

Usage : python3 tools/check_config.py
Retour : 0 si tout est OK, 1 sinon (message explicite).
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OK = "\033[32m✓\033[0m"
KO = "\033[31m✗\033[0m"


def load_env():
    env = {}
    for p in (BASE / ".env", Path.home() / ".env"):
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main():
    problems = 0
    env = load_env()
    ha_url = (env.get("HASS_URL") or env.get("HA_URL") or os.environ.get("HASS_URL")
              or "http://localhost:8123").rstrip("/")
    ha_token = env.get("HA_TOKEN") or env.get("HASS_TOKEN") or os.environ.get("HASS_TOKEN")

    print(f"Configuration : {BASE / '.env'}")
    if not ha_token:
        print(f"  {KO} HA_TOKEN absent — copiez .env.example vers .env et remplissez")
        problems += 1
    else:
        print(f"  {OK} HA_TOKEN présent")

    if ha_token:
        try:
            req = urllib.request.Request(ha_url + "/api/", headers={"Authorization": f"Bearer {ha_token}"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.load(r)
            if data.get("message") == "API running.":
                print(f"  {OK} Connexion HA : {ha_url} (API opérationnelle)")
            else:
                print(f"  {KO} Réponse HA inattendue : {data}")
                problems += 1
        except urllib.error.HTTPError as e:
            print(f"  {KO} Connexion HA : HTTP {e.code} (token invalide ?)")
            problems += 1
        except Exception as e:
            print(f"  {KO} Connexion HA : {e}")
            problems += 1

    layout = BASE / "layout.json"
    if layout.exists():
        try:
            data = json.loads(layout.read_text(encoding="utf-8"))
            sys.path.insert(0, str(BASE))
            import ha3d_server as h
            ok, err = h.validate_layout(data)
            if ok:
                print(f"  {OK} layout.json valide ({len(data.get('sensors', []))} capteurs)")
            else:
                print(f"  {KO} layout.json invalide : {err}")
                problems += 1
        except Exception as e:
            print(f"  {KO} layout.json illisible : {e}")
            problems += 1
    else:
        print(f"  {OK} layout.json absent — démarrage en mode démonstration")

    print()
    if problems:
        print(f"{KO} {problems} problème(s) — corriger puis relancer")
        return 1
    print(f"{OK} Configuration prête — lancez : python3 ha3d_server.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
