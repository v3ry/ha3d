#!/usr/bin/env python3
"""Catalogue CC0 de meubles pour ha3d : recherche poly.pizza, filtre CC0, téléchargement GLB.

Usage : python3 fetch_furniture.py [--dry] [--max-mb 12] [--max-tris 60000]
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
API = "https://poly.pizza/api"
STATIC = "https://static.poly.pizza"

# Catégorie -> (requête, nom français pour le fichier)
CATALOG = [
    ("sofa",          "Canape"),
    ("lounge sofa",   "CanapeAngle"),
    ("dining table",  "TableManger"),
    ("coffee table",  "TableBasse"),
    ("bed",           "Lit"),
    ("single bed",    "LitSimple"),
    ("office chair",  "ChaiseBureau"),
    ("chair",         "Chaise"),
    ("armchair",      "Fauteuil"),
    ("bookshelf",     "Bibliotheque"),
    ("wardrobe",      "Armoire"),
    ("floor lamp",    "Lampadaire"),
    ("table lamp",    "LampeTable"),
    ("desk",          "Bureau"),
    ("tv",            "TV"),
    ("fridge",        "Frigo"),
    ("kitchen cabinet", "MeubleCuisine"),
    ("bathtub",       "Baignoire"),
    ("toilet",        "WC"),
    ("sink",          "Evier"),
    ("plant pot",     "Plante"),
    ("bedside table", "TableChevet"),
    ("stool",         "Tabouret"),
    ("shelf",         "Etagere"),
    ("couch",         "CanapeCouch"),
    ("tv stand",      "MeubleTV"),
]

def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))

def search(query, per_page=12):
    d = get(f"{API}/search/{urllib.parse.quote(query)}?per_page={per_page}")
    return d.get("results", [])

def details(public_id):
    return get(f"{API}/model/{public_id}/details")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="affiche les candidats sans télécharger")
    ap.add_argument("--max-mb", type=float, default=12)
    ap.add_argument("--max-tris", type=int, default=60000)
    args = ap.parse_args()

    os.makedirs(BASE, exist_ok=True)
    ok, skipped, failed = [], [], []

    for query, name in CATALOG:
        try:
            res = search(query)
        except Exception as e:
            print(f"[ERR] recherche '{query}' : {e}")
            failed.append((query, name, "recherche"))
            continue

        picked = None
        for r in res:
            lic = r.get("licence", "")
            if not lic.startswith("CC0"):
                continue
            pid = r["publicID"]
            try:
                det = details(pid)
            except Exception:
                continue
            tris = det.get("Tris") or 0
            anim = det.get("Animated")
            if tris > args.max_tris:
                continue
            if anim:
                continue
            picked = (pid, r["title"], det, tris)
            break

        if not picked:
            print(f"[--] '{query}' : aucun candidat CC0 (≤{args.max_tris} tris)")
            skipped.append((query, name, "aucun CC0"))
            continue

        pid, title, det, tris = picked
        rid = det["ResourceID"]
        fname = name + ".glb"
        url = f"{STATIC}/{rid}.glb"

        # Vérifie la taille sans tout télécharger (HEAD-like via Range)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            clen = resp.headers.get("Content-Range", "")
            m = re.search(r"/(\d+)\s*$", clen)
            size = int(m.group(1)) if m else None

        if size is not None and size > args.max_mb * 1e6:
            print(f"[--] '{query}' : {title} trop lourd ({size/1e6:.1f} Mo) — ignoré")
            skipped.append((query, name, f"trop lourd {size/1e6:.1f}Mo"))
            continue

        print(f"[OK] '{query}' → {name} : « {title} » ({tris} tris, {size/1e6:.1f} Mo si dispo)")
        ok.append((query, name, pid, title, tris))
        if args.dry:
            continue

        path = os.path.join(BASE, fname)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(path, "wb") as f:
            f.write(resp.read())
        time.sleep(0.4)

    print("\n=== RÉSUMÉ ===")
    print(f"OK: {len(ok)}  |  ignorés: {len(skipped)}  |  échecs: {len(failed)}")
    for q, n, pid, t, tris in ok:
        print(f"  {n}.glb  ← « {t} » ({pid})")
    for q, n, why in skipped:
        print(f"  -- {n} ({q}) : {why}")

if __name__ == "__main__":
    main()
