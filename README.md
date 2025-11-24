# Chat SOUVENIR-SOUVENIR — temps réel (Flask-SocketIO)

## Lancer en local
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export FLASK_APP=app.py
python app.py
# http://127.0.0.1:5000
```

Sans `DATABASE_URL`, l'app bascule automatiquement vers SQLite.

## Déploiement (Render)
- Var env: `DATABASE_URL` pointant vers PostgreSQL
- Commande de démarrage **SocketIO** :
  ```bash
  gunicorn -k eventlet -w 1 -b 0.0.0.0:$PORT app:app
  ```
  > `-k eventlet` est nécessaire pour le support WebSocket.
