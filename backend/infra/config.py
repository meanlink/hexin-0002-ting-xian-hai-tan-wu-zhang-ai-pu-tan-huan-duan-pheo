import os

DB_ENGINE = os.getenv("DB_ENGINE", "postgres")
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "business")
DB_USER = os.getenv("DB_USER", "app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "hexin-db-demo")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
JWT_SECRET = os.getenv("JWT_SECRET", "hexin-demo-jwt-key-change-before-deployment")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "Demo2026!")
SEED_DEMO = os.getenv("SEED_DEMO", "true").lower() == "true"
APP_NAME = os.getenv("APP_NAME", "hexin-local")
