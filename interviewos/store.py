from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from interviewos.models import CaseRecord, TimelineEvent
from interviewos.textutil import utc_now

ALLOWED: dict[str, set[str]] = {
    "intake": {"researching", "failed", "paused"},
    "researching": {"qualified", "held", "failed", "paused"},
    "qualified": {"ready", "held", "paused", "closed"},
    "held": {"ready", "qualified", "paused", "closed", "failed"},
    "ready": {"outreach_sent", "held", "paused", "closed"},
    "outreach_sent": {"replied", "paused", "closed"},
    "replied": {"scheduling", "closed", "paused"},
    "scheduling": {"meeting_confirmed", "closed", "paused"},
    "meeting_confirmed": {"closed"},
    "paused": {"held", "ready", "qualified", "closed"},
    "closed": set(),
    "failed": {"researching", "closed"},
}


class TransitionError(ValueError):
    pass


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                mode TEXT NOT NULL,
                state TEXT NOT NULL,
                company_name TEXT,
                role_title TEXT,
                opportunity_type TEXT,
                person_name TEXT,
                next_action TEXT,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                at TEXT NOT NULL,
                actor TEXT NOT NULL,
                from_state TEXT,
                to_state TEXT,
                reason TEXT,
                evidence_ids TEXT
            );
            CREATE TABLE IF NOT EXISTS actions (
                action_key TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def save(self, case: CaseRecord) -> None:
        case.updated_at = utc_now()
        person = case.contact.name if case.contact else ""
        self.conn.execute(
            """
            INSERT INTO cases (
                id, created_at, updated_at, mode, state, company_name, role_title,
                opportunity_type, person_name, next_action, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                updated_at = excluded.updated_at,
                mode = excluded.mode,
                state = excluded.state,
                company_name = excluded.company_name,
                role_title = excluded.role_title,
                opportunity_type = excluded.opportunity_type,
                person_name = excluded.person_name,
                next_action = excluded.next_action,
                payload_json = excluded.payload_json
            """,
            (
                case.id,
                case.created_at,
                case.updated_at,
                case.mode,
                case.state,
                case.company_name,
                case.role_title,
                case.opportunity_type,
                person,
                case.next_action,
                case.model_dump_json(),
            ),
        )
        self.conn.commit()

    def get(self, case_id: str) -> CaseRecord | None:
        row = self.conn.execute("SELECT payload_json FROM cases WHERE id = ?", (case_id,)).fetchone()
        if row is None:
            return None
        return CaseRecord.model_validate_json(row["payload_json"])

    def list_cases(self) -> list[CaseRecord]:
        rows = self.conn.execute("SELECT payload_json FROM cases ORDER BY updated_at DESC").fetchall()
        return [CaseRecord.model_validate_json(row["payload_json"]) for row in rows]

    def transition(
        self,
        case: CaseRecord,
        to_state: str,
        *,
        actor: str,
        reason: str,
        evidence_ids: list[str] | None = None,
    ) -> CaseRecord:
        allowed = ALLOWED.get(case.state, set())
        if to_state not in allowed and to_state != case.state:
            raise TransitionError(f"Cannot move {case.state} to {to_state}.")
        event = TimelineEvent(
            at=utc_now(),
            actor=actor,
            from_state=case.state,
            to_state=to_state,
            reason=reason,
            evidence_ids=evidence_ids or [],
        )
        case.timeline.append(event)
        case.state = to_state  # type: ignore[assignment]
        self.conn.execute(
            """
            INSERT INTO events (case_id, at, actor, from_state, to_state, reason, evidence_ids)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case.id,
                event.at,
                actor,
                event.from_state,
                event.to_state,
                reason,
                json.dumps(event.evidence_ids),
            ),
        )
        self.save(case)
        return case

    def record_action(self, action_key: str, case_id: str, kind: str, status: str, detail: str) -> bool:
        """Insert an action once. Returns False when the key already exists."""
        try:
            self.conn.execute(
                """
                INSERT INTO actions (action_key, case_id, kind, status, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (action_key, case_id, kind, status, detail, utc_now()),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_action(self, action_key: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM actions WHERE action_key = ?", (action_key,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def update_action(self, action_key: str, status: str, detail: str) -> None:
        self.conn.execute(
            "UPDATE actions SET status = ?, detail = ? WHERE action_key = ?",
            (status, detail, action_key),
        )
        self.conn.commit()

    def sends_today(self) -> int:
        day = utc_now()[:10]
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS n FROM actions
            WHERE kind = 'send' AND status = 'sent' AND created_at LIKE ?
            """,
            (day + "%",),
        ).fetchone()
        return int(row["n"])

    def counts(self) -> dict[str, int]:
        cases = self.list_cases()
        return {
            "cases": len(cases),
            "replies": sum(1 for case in cases if case.state in {"replied", "scheduling", "meeting_confirmed"}),
            "conversations": sum(1 for case in cases if case.state == "meeting_confirmed"),
        }
