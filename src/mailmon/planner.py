import os
import sqlite3
from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import Enum
from typing import List, Optional

from jmapc import Email

from mailmon.llm import Classifier
from mailmon.mailbox import get_mailboxes


class PlanSource(Enum):
    RULE = "rule"
    LLM = "llm"
    HYBRID = "hybrid"


class PlanAction(Enum):
    MOVE = "move"
    TRASH = "trash"
    ARCHIVE = "archive"
    MARK_READ = "mark-read"
    MARK_UNREAD = "mark-unread"
    MARK_PINNED = "mark-pinned"


@dataclass
class Plan:
    email_id: str
    source: PlanSource
    action: PlanAction
    llm_model: Optional[str] = None
    llm_confidence: Optional[str] = None
    llm_reasoning: Optional[str] = None
    rule_ids: List[str] = field(default_factory=list)
    target_ids: List[str] = field(default_factory=list)
    planned_at: datetime = field(default_factory=datetime.utcnow)

    def __str__(self) -> str:
        out = f"{self.action.name.upper()}"
        if self.action == PlanAction.MOVE:
            out += f" [{self.email_id}] -> [{', '.join(self.target_ids)}]"
        if self.source == PlanSource.LLM or self.source == PlanSource.HYBRID:
            out += "\n"
            out += f"LLM({self.llm_model}, {self.llm_confidence}):\n"
            out += self.llm_reasoning or ""
        return out


class Planner:
    def __init__(self) -> None:
        self.mailboxes = get_mailboxes()
        self.classifier = Classifier(self.mailboxes)
        self.db = PlanDB(os.path.expanduser(os.environ["PLAN_DB_FILE"]))

    def plan(self, email: Email, override=False):
        if not email.id:
            return None
        saved_plan = self.db.get(email.id)
        if not saved_plan or override:
            generated_plan = self.generate_plan(email)
            return self.db.insert(generated_plan)
        else:
            return saved_plan

    def generate_plan(self, email: Email) -> Optional[Plan]:
        if not email.id:
            return None
        res = self.classifier.classify(email)
        target = self.mailboxes[res.folder].id
        if not target:
            return None
        return Plan(
            source=PlanSource.LLM,
            action=PlanAction.MOVE,
            email_id=email.id,
            llm_model=self.classifier.model,
            llm_confidence=res.confidence,
            llm_reasoning=res.reason,
            target_ids=[target],
        )


class PlanDB:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS plan (
                email_id       TEXT PRIMARY KEY,
                source         TEXT NOT NULL,
                action         TEXT NOT NULL,
                llm_model      TEXT,
                llm_confidence TEXT,
                llm_reasoning  TEXT,
                rule_ids       TEXT,
                target_ids     TEXT,
                planned_at     TIMESTAMP NOT NULL
            )
        """)
        self.conn.commit()
        plan_fields = [f.name for f in fields(Plan)]
        self.fields = ", ".join(plan_fields)
        self.placeholders = ", ".join("?" * len(plan_fields))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.conn.close()

    @staticmethod
    def _encode_list(values: List[str]) -> str:
        return ",".join(values)

    @staticmethod
    def _decode_list(value: str) -> List[str]:
        return value.split(",") if value else []

    def _to_row(self, plan: Plan) -> tuple:
        return (
            plan.email_id,
            plan.source.value,
            plan.action.value,
            plan.llm_model,
            plan.llm_confidence,
            plan.llm_reasoning,
            ",".join(plan.rule_ids),
            ",".join(plan.target_ids),
            plan.planned_at.isoformat(),
        )

    def _from_row(self, row: sqlite3.Row) -> Plan:
        return Plan(
            email_id=row["email_id"],
            source=PlanSource(row["source"]),
            action=PlanAction(row["action"]),
            llm_model=row["llm_model"],
            llm_confidence=row["llm_confidence"],
            llm_reasoning=row["llm_reasoning"],
            rule_ids=row["rule_ids"].split(","),
            target_ids=row["target_ids"].split(","),
            planned_at=datetime.fromisoformat(row["planned_at"]),
        )

    def insert(self, plan: Optional[Plan]) -> Optional[Plan]:
        if not plan:
            return None
        self.conn.execute(
            f"INSERT OR REPLACE INTO plan ({self.fields}) VALUES ({self.placeholders})",
            self._to_row(plan),
        )
        self.conn.commit()
        return plan

    def delete(self, email_id: str) -> None:
        self.conn.execute("DELETE FROM plan WHERE email_id = ?", (email_id,))
        self.conn.commit()

    def get(self, email_id: str) -> Optional[Plan]:
        row = self.conn.execute(
            "SELECT * FROM plan WHERE email_id = ?", (email_id,)
        ).fetchone()
        return self._from_row(row) if row else None
