# Sécurité

## Signaler une vulnérabilité

**Ne pas ouvrir d'issue publique pour une vulnérabilité de sécurité.** Contactez le mainteneur directement via les Issues GitHub en mode privé, ou ouvrez un ticket avec le label `security`.

## Périmètre connu

- Les endpoints d'écriture du serveur (`/api/save-layout`, `/api/toggle`) **ne sont pas authentifiés**. Le serveur écoute sur `127.0.0.1` par défaut et doit rester **strictement sur un réseau de confiance** (jamais exposé sur Internet sans reverse-proxy + authentification).
- Le token Home Assistant (`HA_TOKEN`) est lu depuis `.env` uniquement, jamais envoyé au navigateur.
- `layout.json` contient des données de votre domicile (plan, entités, position GPS) : il est ignoré par git — ne le committez jamais.

## Bonnes pratiques pour les utilisateurs

1. Garder `MAISON3D_HOST=127.0.0.1` (défaut) sauf besoin réel.
2. Créer un token HA longue durée **dédié** avec les permissions minimales (lecture + toggle des entités utilisées).
3. Ne jamais exposer le port 9125 sur Internet directement.
