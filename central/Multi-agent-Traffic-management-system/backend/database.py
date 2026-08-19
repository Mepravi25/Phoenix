"""PostgreSQL connection dependency used by FastAPI route handlers."""

from __future__ import annotations

import os
import socket
import sqlite3
from collections.abc import Generator
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection as PgConnection

# Load a deployment-provided environment first, then support a local backend/.env
# file during development. Neither the DSN nor credentials are ever hard-coded.
load_dotenv()
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)


def get_database_url() -> str:
    """Read the PostgreSQL DSN only when a database connection is required."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured in the environment or .env file.")
    return database_url


class SQLiteCompatCursor:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.cur.close()
        self.conn.close()

    def execute(self, sql: str, params: tuple = ()):
        formatted_sql = sql.replace("%s", "?")
        formatted_sql = formatted_sql.replace("ST_Y(geom)", "lat").replace("ST_X(geom)", "lon")
        formatted_sql = formatted_sql.replace("geom::geometry", "geom")
        
        has_returning = "RETURNING" in formatted_sql.upper()
        if has_returning:
            clean_sql = formatted_sql[:formatted_sql.upper().find("RETURNING")].strip()
            self.cur.execute(clean_sql, params)
            last_id = self.cur.lastrowid
            self.cur.execute("SELECT id, username, role FROM users WHERE id = ?", (last_id,))
        else:
            self.cur.execute(formatted_sql, params)

    def fetchone(self):
        row = self.cur.fetchone()
        if row is None:
            return None
        colnames = [desc[0] for desc in self.cur.description]
        return dict(zip(colnames, row))

    def fetchall(self):
        rows = self.cur.fetchall()
        if not rows:
            return []
        colnames = [desc[0] for desc in self.cur.description]
        return [dict(zip(colnames, r)) for r in rows]


class SQLiteCompatConn:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_tables()

    def _init_tables(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'ev_driver'
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS spatial_intersections (
                node_id INTEGER PRIMARY KEY,
                lat REAL NOT NULL,
                lon REAL NOT NULL
            );
        """)
        conn.commit()
        conn.close()

    def cursor(self, cursor_factory=None):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        return SQLiteCompatCursor(conn)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _is_postgres_online() -> bool:
    try:
        s = socket.socket()
        s.settimeout(0.1)
        res = s.connect_ex(("127.0.0.1", 5432))
        s.close()
        return res == 0
    except Exception:
        return False


def get_db() -> Generator[Any, None, None]:
    """Yield one request-scoped database connection (PostgreSQL or SQLite fallback)."""
    if _is_postgres_online():
        try:
            connection = psycopg2.connect(get_database_url(), connect_timeout=1)
            try:
                yield connection
            finally:
                connection.close()
            return
        except Exception:
            pass

    db_path = Path(__file__).resolve().parent.parent / "traffic_command.db"
    connection = SQLiteCompatConn(str(db_path))
    try:
        yield connection
    finally:
        connection.close()

