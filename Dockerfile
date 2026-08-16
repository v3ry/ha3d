# Ha3D — visualiseur 3D des capteurs Home Assistant
FROM python:3.11-slim

# Pas de dépendances pip : serveur pur stdlib + client three.js (CDN)
WORKDIR /app

# Utilisateur non-root
RUN useradd --create-home --uid 1000 ha3d \
    && mkdir -p /ha3d_layout_backups

COPY --chown=ha3d:ha3d . /app

RUN chown -R ha3d:ha3d /app /ha3d_layout_backups

USER ha3d

# Variables par défaut (surchargeables via docker-compose / -e)
ENV MAISON3D_HOST=0.0.0.0 \
    MAISON3D_PORT=9125

EXPOSE 9125

# Vérifie la configuration au démarrage, puis lance le serveur
CMD ["sh", "-c", "python3 tools/check_config.py || true; python3 ha3d_server.py"]
