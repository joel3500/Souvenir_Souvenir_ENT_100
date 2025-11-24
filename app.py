from logging import log
import os
from urllib.parse import quote_plus
from flask import Flask, current_app, render_template, request, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO
from models import ChatMessage
from database import db
from peewee import fn
from peewee import PostgresqlDatabase, SqliteDatabase
import logging 
from playhouse.db_url import connect
from urllib.parse import quote_plus
from flask_cors import CORS


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

# SocketIO, compatible avec eventlet / gevent / threading. En prod: worker eventlet.
socketio = SocketIO(app, cors_allowed_origins="*")

# =====Vient avec Flask-CORS

PAGES_ORIGINS = [
    "https://joel3500.github.io",
    "https://joel3500.github.io/Souvenir_Souvenir_ENT_100",
]

CORS(
    app,
    resources={
        r"/api/*":   {"origins": PAGES_ORIGINS},
        r"/post":    {"origins": PAGES_ORIGINS},
        r"/debug/*": {"origins": PAGES_ORIGINS},   # si tu gardes /debug/db
        r"/api/health": {"origins": PAGES_ORIGINS} # ajoute cette ligne
    },
    supports_credentials=False,
    allow_headers=["Content-Type"],
    methods=["GET","POST","OPTIONS"],
)

# ----- Fin de Flask-CORS

MAX_MESSAGES = 100

# Logs propres
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("souvenir_souvenir_ent_100")

IS_PROD = os.getenv("APP_ENV") == "production" or os.getenv("RENDER") == "true"

def init_schema_once():
    with db:
        try:
            # safe=True évite l’exception si la table existe déjà
            db.create_tables([ChatMessage], safe=True)
            log.info("[DB] schema OK (tables créées si nécessaire)")
        except Exception as e:
            log.exception("[DB] init schema failed: %s", e)

init_schema_once()

def enforce_cap(max_rows=MAX_MESSAGES):
    """Garde au plus `max_rows` messages en supprimant les plus anciens."""
    with db.atomic():
        total = ChatMessage.select(fn.COUNT(ChatMessage.id)).scalar()
        if total and total > max_rows:
            excess = total - max_rows
            # Récupère les IDs les plus anciens à supprimer
            old_ids = (ChatMessage
                       .select(ChatMessage.id)
                       .order_by(ChatMessage.created_at.asc())
                       .limit(excess))
            # Supprime en un coup
            (ChatMessage
             .delete()
             .where(ChatMessage.id.in_(old_ids))
             .execute())
            
@app.route("/", methods=["GET"])
def index():
    messages = (ChatMessage
                .select()
                .order_by(ChatMessage.created_at.desc()))
    return render_template("index.html", messages=messages)

@app.get("/api/health")
def api_health():
    try:
        # touche la DB pour la “réveiller”
        from database import db
        db.connect(reuse_if_open=True)
        db.execute_sql("SELECT 1;").fetchone()

        # (optionnel) un petit indicateur utile pour le front
        total = ChatMessage.select(fn.COUNT(ChatMessage.id)).scalar() or 0

        return jsonify({"ok": True, "rows": total}), 200
    except Exception as e:
        current_app.logger.exception("health error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/chat")
def api_chat():
    data = request.get_json(silent=True) or {}
    prenom = (data.get("prenom") or "").strip()
    filiaire = (data.get("filiaire") or "").strip()
    commentaire = (data.get("commentaire") or "").strip()

    if not prenom or not filiaire or not commentaire:
        return jsonify({"ok": False, "error": "Tous les champs sont requis."}), 400

    prenom = prenom[:50]
    filiaire = filiaire[:120]
    commentaire = commentaire[:2000]

    msg = ChatMessage.create(prenom=prenom, filiaire=filiaire, commentaire=commentaire)
    
    # On appelle enforce_cap() juste après chaque création de message, pour conserver 50 MESSAGES, PAS PLUS.
    enforce_cap()   # supprime les plus anciens au-delà de 50
    
    # Diffuse à tous les clients connectés
    socketio.emit("chat:new", {
        "prenom": msg.prenom,
        "filiaire": msg.filiaire,
        "commentaire": msg.commentaire
    })

    return jsonify({"ok": True})


@app.post("/post")
def post_form():
    prenom = (request.form.get("prenom") or "").strip()
    filiaire = (request.form.get("filiaire") or "").strip()
    commentaire = (request.form.get("commentaire") or "").strip()
    if prenom and filiaire and commentaire:
        msg = ChatMessage.create(prenom=prenom[:50], filiaire=filiaire[:120], commentaire=commentaire[:2000])
        
        # On appelle enforce_cap() juste après chaque création de message, pour conserver 50 MESSAGES, PAS PLUS.
        enforce_cap()  # supprime les plus anciens au-delà de 50
        
        # Diffuse à tous les clients connectés
        socketio.emit("chat:new", {"prenom": msg.prenom, "filiaire": msg.filiaire, "commentaire": msg.commentaire})
    return redirect(url_for("index"))


# Comment savoir quelle BD est utilisée (à coup sûr) ?
# (Optionnel) mini endpoint pour vérifier en live
# → Aller sur http://127.0.0.1:5000/debug/db et on saura.
@app.get("/debug/db")
def debug_db():
    from database import db
    backend = type(db).__name__

    if IS_PROD:
        # ----- PROD : lecture seule + logs -----
        try:
            version = db.execute_sql("select version()").fetchone()[0]
            total = ChatMessage.select(fn.COUNT(ChatMessage.id)).scalar() or 0
            log.info("[DEBUG/DB] backend=%s, version=%s, total_rows=%s", backend, version, total)
            return jsonify({
                "ok": True,
                "env": "production",
                "backend": backend,
                "version": version,
                "rows": total
            })
        except Exception as e:
            log.exception("[DEBUG/DB] prod error: %s", e)
            return jsonify({"ok": False, "env": "production", "backend": backend, "error": str(e)}), 500

    # ----- LOCAL : ta version actuelle (détaillée) -----
    try:
        if isinstance(db, PostgresqlDatabase):
            kind = "postgresql"; name = db.database; host = getattr(db, "host", None)
        elif isinstance(db, SqliteDatabase):
            kind = "sqlite"; name = db.database; host = None
        else:
            kind = type(db).__name__; name = getattr(db, "database", None); host = None

        version = db.execute_sql("select version()").fetchone()[0]
        total = ChatMessage.select(fn.COUNT(ChatMessage.id)).scalar() or 0
        log.info("[DEBUG/DB] kind=%s, version=%s, total_rows=%s", kind, version, total)
        return jsonify({
            "ok": True,
            "env": "development",
            "backend": kind,
            "database": name,
            "host": host,
            "version": version,
            "rows": total
        })
    except Exception as e:
        log.exception("[DEBUG/DB] local error: %s", e)
        return jsonify({"ok": False, "env": "development", "backend": backend, "error": str(e)}), 500


if __name__ == "__main__":
    # En dev: websocket + auto-reload pratique
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
