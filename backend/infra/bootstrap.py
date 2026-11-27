from pathlib import Path

from infra.config import DEMO_PASSWORD
from infra.db import tx
from infra.roles import Role
from infra.security import password_hash

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def migrate():
    with tx() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                       migration VARCHAR(120) PRIMARY KEY)""")
        db.execute("""CREATE TABLE IF NOT EXISTS users (
                       email VARCHAR(150) PRIMARY KEY,
                       password_hash VARCHAR(200) NOT NULL,
                       role VARCHAR(20) NOT NULL CHECK (role IN ('viewer','operator','admin')))""")
        db.execute("""CREATE TABLE IF NOT EXISTS audit_events (
                       request_id VARCHAR(40) PRIMARY KEY, actor VARCHAR(150) NOT NULL,
                       verb VARCHAR(20) NOT NULL, path VARCHAR(500) NOT NULL,
                       status_code INTEGER NOT NULL, occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        for source in sorted(MIGRATIONS.glob("*.sql")):
            if db.one("SELECT migration FROM schema_migrations WHERE migration=%s", (source.name,)):
                continue
            for statement in source.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    db.execute(statement)
            db.execute("INSERT INTO schema_migrations(migration) VALUES (%s)", (source.name,))


def seed_demo():
    from domain import seed
    with tx() as db:
        for role in Role:
            email = f"{role.value}@demo.test"
            if not db.one("SELECT email FROM users WHERE email=%s", (email,)):
                db.execute("INSERT INTO users(email,password_hash,role) VALUES (%s,%s,%s)",
                           (email, password_hash(DEMO_PASSWORD), role.value))
        result = seed(db)
        return {"accounts": db.one("SELECT COUNT(*) AS n FROM users")["n"],
                "domain": result}
