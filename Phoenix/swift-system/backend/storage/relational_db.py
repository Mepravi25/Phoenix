"""
SWIFT SYSTEM - Relational Storage Abstraction
Stores relational records: emergency missions, incident reports, audit logs, and decisions.
Supports SQLite / PostgreSQL dialect abstractions.
"""

import sqlite3
import json
import os
import time
from typing import Dict, List, Any


class RelationalDB:
    def __init__(self, db_path: str = "swift_system.db"):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_tables(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS decision_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    agent TEXT,
                    event TEXT,
                    junction TEXT,
                    decision TEXT,
                    reason TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS missions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ambulance_id TEXT,
                    start_junction TEXT,
                    dest_junction TEXT,
                    urgency_level TEXT,
                    mode TEXT,
                    total_travel_time REAL,
                    time_saved REAL,
                    timestamp REAL
                )
            """)
            conn.commit()

    def log_decision(self, agent: str, event: str, junction: str, decision: str, reason: str):
        ts = time.time()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO decision_logs (timestamp, agent, event, junction, decision, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ts, agent, event, junction, decision, reason))
            conn.commit()

    def get_recent_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, agent, event, junction, decision, reason
                FROM decision_logs ORDER BY id DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [
                {
                    "timestamp": r[0],
                    "agent": r[1],
                    "event": r[2],
                    "junction": r[3],
                    "decision": r[4],
                    "reason": r[5]
                }
                for r in rows
            ]


relational_db = RelationalDB()
