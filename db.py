"""PostgreSQL connection configuration."""

import os

import psycopg
from psycopg import Connection


def get_connection() -> Connection:
    """Open a PostgreSQL connection using libpq environment variables.

    DATABASE_URL takes precedence. Otherwise PGHOST, PGPORT, PGDATABASE,
    PGUSER, and PGPASSWORD are used, with defaults matching docker-compose.yml.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg.connect(database_url)

    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "app"),
        user=os.getenv("PGUSER", "app"),
        password=os.getenv("PGPASSWORD", "password123"),
    )
