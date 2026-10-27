"""SQLite: заявка зберігається першою, ще до відправки в Telegram і таблицю, тож не губиться ніколи."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,          -- UTC ISO
    appliance     TEXT NOT NULL,
    problem       TEXT NOT NULL,
    brand         TEXT NOT NULL,
    age           TEXT NOT NULL,
    urgency       TEXT NOT NULL,
    zip           TEXT NOT NULL,
    in_area       INTEGER NOT NULL,
    name          TEXT NOT NULL,
    phone         TEXT NOT NULL,
    email         TEXT NOT NULL DEFAULT '',
    utm           TEXT NOT NULL DEFAULT '{}',
    page_url      TEXT NOT NULL DEFAULT '',
    ip            TEXT NOT NULL DEFAULT '',
    telegram_ok   INTEGER NOT NULL DEFAULT 0,
    sheets_ok     INTEGER NOT NULL DEFAULT 0,
    last_error    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_leads_phone ON leads (phone, created_at);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class LeadStore:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def add(self, lead, in_area: bool, ip: str, now: datetime | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO leads (created_at, appliance, problem, brand, age, urgency, zip, in_area, name, phone,"
            " email, utm, page_url, ip) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ((now or utcnow()).isoformat(), lead.appliance, lead.problem, lead.brand, lead.age, lead.urgency,
             lead.zip, int(in_area), lead.name, lead.phone, lead.email, json.dumps(lead.utm.model_dump()),
             lead.page_url, ip))
        self.conn.commit()
        return cur.lastrowid

    def recent_by_phone(self, phone: str, minutes: int, now: datetime | None = None) -> int | None:
        since = ((now or utcnow()) - timedelta(minutes=minutes)).isoformat()
        row = self.conn.execute("SELECT id FROM leads WHERE phone = ? AND created_at >= ? ORDER BY id DESC LIMIT 1",
                                (phone, since)).fetchone()
        return row["id"] if row else None

    def get(self, lead_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["utm"] = json.loads(d["utm"])
        return d

    def mark(self, lead_id: int, **flags) -> None:
        allowed = {"telegram_ok", "sheets_ok", "last_error"}
        sets = {k: v for k, v in flags.items() if k in allowed}
        if sets:
            self.conn.execute(f"UPDATE leads SET {', '.join(f'{k} = ?' for k in sets)} WHERE id = ?",
                              (*sets.values(), lead_id))
            self.conn.commit()

    def undelivered(self) -> list[dict]:
        rows = self.conn.execute("SELECT id FROM leads WHERE telegram_ok = 0 ORDER BY id").fetchall()
        return [self.get(r["id"]) for r in rows]
