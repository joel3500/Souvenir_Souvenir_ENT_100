import os, sys
from urllib.parse import quote_plus
from dotenv import load_dotenv
from peewee import SqliteDatabase
from playhouse.db_url import connect

load_dotenv()  # <-- charge .env dans os.environ

def get_database():
    url = os.getenv("DATABASE_URL")
    
    if not url:
        # Construire depuis variables séparées (recommandé)
        pg_user = os.getenv("PGUSER")
        pg_pass = os.getenv("PGPASSWORD")
        pg_host = os.getenv("PGHOST", "localhost")
        pg_port = os.getenv("PGPORT", "5432")
        pg_db   = os.getenv("PGDATABASE")

        if pg_user and pg_pass and pg_db:
            safe_user = quote_plus(pg_user)
            safe_pass = quote_plus(pg_pass)   # <- encode ? @ : / # & % +
            url = f"postgresql://{safe_user}:{safe_pass}@{pg_host}:{pg_port}/{pg_db}"
    if url:
        try:
            db = connect(url)
            db.connect(reuse_if_open=True)
            return db
        except Exception as e:
            print(f"[WARN] PostgreSQL indisponible, bascule vers SQLite: {e}", file=sys.stderr)

    db = SqliteDatabase("souvenir_souvenir_ent_100.db")
    db.connect(reuse_if_open=True)
    return db

db = get_database()

# Comment savoir quelle BD est utilisée (à coup sûr) ?
from peewee import PostgresqlDatabase, SqliteDatabase

def _print_backend(db):
    try:
        if isinstance(db, PostgresqlDatabase):
            print("[DB] Backend = PostgreSQL", file=sys.stderr)
        elif isinstance(db, SqliteDatabase):
            print(f"[DB] Backend = SQLite (fichier: {db.database})", file=sys.stderr)
        else:
            print(f"[DB] Backend = {type(db).__name__}", file=sys.stderr)
    except Exception as e:
        print(f"[DB] Impossible d’identifier le backend: {e}", file=sys.stderr)

_print_backend(db)