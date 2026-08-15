# 🏠 Maison 3D — Visualiseur 3D des capteurs Home Assistant

Visualiseur 3D interactif (three.js) de la maison avec les capteurs Home Assistant en temps réel : températures, clims, lumières cliquables, portes, solaire, batteries.

## Fonctionnalités

- **Rendu 3D** de la maison (plain-pied, vue isométrique par défaut, OrbitControls)
- **24+ capteurs** en direct depuis Home Assistant (refresh 15 s)
- **Lumières 3D** : clic sur une sphère lumière/prise → toggle via l'API HA (halo + ombres portées)
- **Murs fusionnés** : les murs partagés entre pièces sont dédupliqués (pas de clipping)
- **Mode debug 🔧** :
  - Drag & drop des entités sur le sol (X/Z) ou en hauteur (Y)
  - Ajout / suppression d'entités HA (recherche en direct)
  - Capture de la caméra par défaut
  - Sauvegarde directe sur le serveur (backup automatique)
- **Historique 24 h** par capteur (courbe)
- **Alertes** : porte ouverte, batterie faible, température élevée
- **Filtres** par type (temp, hum, lumière, clim, portes, batterie, conso, solaire, alertes)
- **Capture PNG** du rendu

## Architecture

| Fichier | Rôle |
|---|---|
| `ha3d_server.py` | Serveur HTTP + proxy API HA (layout, status, history, toggle, save-layout, entités) |
| `index.html` | Client three.js (rendu, interactions, mode debug) |
| `layout.json` | Configuration : pièces, entités, positions, caméra par défaut |
| `models/` | Modèles glTF (Khronos Sample Models, CC0) |
| `ha_ws.py` | Client websocket HA (pilotage dashboards Lovelace) |

## Démarrage

```bash
# Prérequis : token HA dans /home/hermes/.env (HASS_URL, HA_TOKEN)
python3 ha3d_server.py
# → http://<host>:9125
```

Systemd user (auto-démarrage + restart) :

```bash
cp maison3d.service ~/.config/systemd/user/
systemctl --user enable --now maison3d
```

## Configuration (layout.json)

- `rooms` : pièces (x, z, w, d, couleur)
- `sensors` : entités avec position absolue `pos: [x, y, z]` (mode debug pour les ajuster)
- `default_camera` : position/target de la caméra par défaut

Backups automatiques du layout dans `~/ha3d_layout_backups/` à chaque sauvegarde.
