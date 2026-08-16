# 🏠 Maison 3D — Visualiseur 3D des capteurs Home Assistant

Visualiseur 3D interactif (three.js) de la maison avec les capteurs Home Assistant en temps réel : températures, clims, lumières cliquables, portes, solaire, batteries.

## Fonctionnalités

- **Rendu 3D** de la maison (plain-pied, vue isométrique par défaut, OrbitControls)
- **24+ capteurs** en direct depuis Home Assistant (temps réel WebSocket HA → SSE, fallback 60 s)
- **Icônes 3D par type** : thermomètre (temp), goutte (humidité), flocon (clim), ampoule (lumière, culot métal), éclair (conso), batterie, panneau solaire, porte, alerte — plus de sphères uniformes
- **Lumières 3D** : clic sur une ampoule/prise → toggle via l'API HA (halo + ombres portées)
- **Portes réelles** : les murs sont découpés aux ouvertures (`layout.doors`), cadres (jambages + linteau) + vantaux pivotants animés selon l'état HA (on = ouverte, transition douce)
- **Murs fusionnés** : les murs partagés entre pièces sont dédupliqués (pas de clipping)
- **Mode jour/nuit** : bouton 🌗 (auto selon l'heure / ☀️ / 🌙), transition douce
- **Étiquettes anti-chevauchement** : projection écran + séparation itérative (145 px)
- **Mode debug 🔧** :
  - Drag & drop des entités sur le sol (X/Z) ou en hauteur (Y)
  - Édition des pièces 🏠 : déplacer / redimensionner à la souris — au déplacement, capteurs, meubles et modèles suivent ; au redimensionnement, les capteurs gardent leur position absolue. Pièces polygonales (sommets libres 🟡) possibles
  - Édition des portes 🚪 et objets 🛋️ : clic = panneau (nom, dimensions, capteur associé…), drag = déplacer (les portes s'accrochent à n'importe quel mur), ➕ ajouter, 🗑️ supprimer
  - **Undo/Redo : Ctrl+Z / Ctrl+Shift+Z** (toutes les éditions, jusqu'à 50 étapes)
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
| `models/` | Modèles glTF 3D (CC0 — poly.pizza + Khronos), servis par `/models/*.glb` |

## Catalogue de modèles 3D

Le panneau objet permet de choisir le type : **🟫 Boîte simple** ou **🧊 modèle 3D** (liste chargée depuis `/api/models`). Pour ajouter un modèle : déposer un fichier `.glb` dans `models/` — il apparaît automatiquement dans la liste.

Catalogue actuel (28 modèles, tous CC0) :

| Fichier | Modèle source |
|---|---|
| `Canape.glb`, `CanapeAngle.glb`, `CanapeCouch.glb` | Canapés (poly.pizza, CC0) |
| `TableManger.glb`, `TableBasse.glb`, `TableChevet.glb` | Tables (poly.pizza, CC0) |
| `Lit.glb`, `LitSimple.glb`, `Bureau.glb`, `Chaise.glb`, `ChaiseBureau.glb`, `Fauteuil.glb`, `Tabouret.glb` | Chaises & bureau (poly.pizza, CC0) |
| `Armoire.glb`, `Bibliotheque.glb`, `Etagere.glb`, `MeubleTV.glb`, `MeubleCuisine.glb`, `TV.glb`, `Frigo.glb` | Rangements & électroménager (poly.pizza, CC0) |
| `Lampadaire.glb`, `LampeTable.glb` | Lampes (poly.pizza, CC0) |
| `Baignoire.glb`, `WC.glb`, `Evier.glb` | Salle de bain (poly.pizza, CC0) |
| `Plante.glb` | Plante verte (poly.pizza, CC0) |
| `Duck.glb`, `SheenChair.glb` | Khronos Sample Models (CC0) |

Source : [poly.pizza](https://poly.pizza) (recherche CC0 1.0) — voir `models/README.md` pour la liste détaillée.
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
- `doors` : portes réelles — `rotY`/`fixed` (mur porteur), `t` (centre de l'ouverture), `width`/`height`, `hinge` (bord de charnière a0/a1), `openSign` (±1 sens d'ouverture), `entity` (état HA qui anime la porte, on = ouverte), `noPanel` (ouverture brute sans vantail, ex. porte sectionnelle garage)
- `default_camera` : position/target de la caméra par défaut

Backups automatiques du layout dans `~/ha3d_layout_backups/` à chaque sauvegarde.
