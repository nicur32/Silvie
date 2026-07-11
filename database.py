import sqlite3
from datetime import datetime


class LeadDatabase:
    def __init__(self, db_path: str = "silvie_leads.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre      TEXT NOT NULL,
                    empresa     TEXT NOT NULL,
                    email       TEXT UNIQUE NOT NULL,
                    cargo       TEXT,
                    created_at  TEXT DEFAULT (datetime('now')),
                    bpmn_xml    TEXT,
                    narrative   TEXT,
                    status      TEXT DEFAULT 'new'
                )
            """)
            conn.commit()

    def get_lead(self, email: str) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM leads WHERE email = ?", (email.lower().strip(),)
            ).fetchone()
            return dict(row) if row else None

    def create_lead(self, lead_data: dict) -> int:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO leads (nombre, empresa, email, cargo) VALUES (?, ?, ?, ?)",
                (
                    lead_data["nombre"],
                    lead_data["empresa"],
                    lead_data["email"].lower().strip(),
                    lead_data.get("cargo", ""),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def update_lead_process(self, email: str, bpmn_xml: str, narrative: str):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE leads SET bpmn_xml = ?, narrative = ?, status = 'completed' WHERE email = ?",
                (bpmn_xml, narrative, email.lower().strip()),
            )
            conn.commit()

    def get_all_leads(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM leads ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
