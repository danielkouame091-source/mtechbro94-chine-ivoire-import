# China–Côte d'Ivoire Import & Export

Ce dépôt contient une application Streamlit pour la gestion des cotations, des dossiers douaniers et du suivi des importations/expertises Chine–Côte d'Ivoire.

## Démarrage

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Structure importante

- `app.py` : application principale Streamlit
- `actualiser_tarif.py` : script de mise à jour de la grille tarifaire
- `schema.sql` : schéma de base PostgreSQL
- `templates/index.html` : page HTML de démonstration/landing page

## Remarque

Le projet doit être lancé via Streamlit. Ne pas utiliser Flask, Gunicorn ou le port 5000 pour démarrer l'application.
