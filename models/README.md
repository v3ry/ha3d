# Modèles 3D du catalogue (tous CC0 1.0)

Téléchargés depuis [poly.pizza](https://poly.pizza) (licence **CC0 1.0** — aucun crédit requis, usage libre y compris commercial).
`Duck.glb` et `SheenChair.glb` proviennent des [Khronos glTF Sample Models](https://github.com/KhronosGroup/glTF-Sample-Assets) (CC0).

| Fichier | Modèle source (poly.pizza) | PublicID |
|---|---|---|
| Canape.glb | Sofa | X5kQPKzAWp |
| CanapeAngle.glb | Lounge Sofa Long | gX7VhrgdIE |
| CanapeCouch.glb | Couch Large | 6MoOyPtetL |
| TableManger.glb | Table | KndwzSWSHR |
| TableBasse.glb | Coffee Table | y4ZU5S7RuD |
| TableChevet.glb | Night Stand | 7cobkfclNv |
| Lit.glb | Bed Single | sn8az3odMR |
| LitSimple.glb | Bed Single | ianC28eMOF |
| Bureau.glb | Desk | V86Go2rlnq |
| Chaise.glb | Chair | iMNqRzPwwe |
| ChaiseBureau.glb | Office Chair | UfKvrZBK6C |
| Fauteuil.glb | Armchair | myd1WSucAz |
| Tabouret.glb | Stool | FQj3bKSzdw |
| Armoire.glb | Closet | BHEVb1DIuH |
| Bibliotheque.glb | Bookcase with Books | tACDGJ4CGW |
| Etagere.glb | Shelf Tall | TDgvIuorcX |
| MeubleTV.glb | Cabinet Television Doo | GUe1tUupFn |
| MeubleCuisine.glb | Kitchen Cabinet | jRPnkxtk8s |
| TV.glb | Television Vintage | aSmz6H8aeu |
| Frigo.glb | Kitchen Fridge | 8sjRm8fnHh |
| Lampadaire.glb | Light Floor | eBQtooeh43 |
| LampeTable.glb | Light Desk | uJDWrSJGVH |
| Baignoire.glb | Bathtub | kVFRyNEn4F |
| WC.glb | Toilet | WAu50yGFVt |
| Evier.glb | Bathroom Sink | OMCJDgMUui |
| Plante.glb | Potted Plant | 23Dx9CC95C |

## Ajouter un modèle

1. Télécharger un `.glb` (ex. `curl -L -o models/MonMeuble.glb https://static.poly.pizza/<ResourceID>.glb`)
2. Le nom du fichier (sans `.glb`) apparaît automatiquement dans le sélecteur Type du panneau objet.
3. Script de rafraîchissement du catalogue : `python3 /tmp/fetch_furniture.py` (recherche CC0 par catégorie, filtre taille/tris, téléchargement dans `models/`).
