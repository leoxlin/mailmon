import sqlite3
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from mailmon.config import Config
from mailmon.llm import Classifier
from mailmon.mailbox import Email


class PlanSource(Enum):
    RULE = "rule"
    LLM = "llm"
    HYBRID = "hybrid"


class PlanAction(Enum):
    MOVE = "move"
    TRASH = "trash"
    REVIEW = "review"
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
    rule_ids: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    planned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __str__(self) -> str:
        out = f"{self.action.name.upper()}"
        if self.targets:
            out += f" -> [{', '.join(self.targets)}]"
        if self.source in (PlanSource.LLM, PlanSource.HYBRID):
            out += "\n"
            out += f"LLM({self.llm_model}, {self.llm_confidence}): "
            out += self.llm_reasoning or ""
        return out


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
                targets        TEXT,
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

    def _to_row(self, plan: Plan) -> tuple:
        return (
            plan.email_id,
            plan.source.value,
            plan.action.value,
            plan.llm_model,
            plan.llm_confidence,
            plan.llm_reasoning,
            ",".join(plan.rule_ids),
            ",".join(plan.targets),
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
            targets=row["targets"].split(","),
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

    def get_by_target(self, target: str) -> list[Plan]:
        rows = self.conn.execute(
            "SELECT * FROM plan WHERE INSTR(targets, ?)", (target,)
        ).fetchall()
        return [self._from_row(row) for row in rows]


class Planner(PlanDB):
    def __init__(
        self,
        config: Config,
        classifier: Classifier,
    ) -> None:
        super().__init__(config.plan_file)
        self.classifier = classifier

    def plan(self, email: Email, regenerate=False):
        if not email.id:
            return None
        if not (saved_plan := self.get(email.id)) or regenerate:
            return self.insert(self._generate_plan(email))
        return saved_plan

    def _generate_plan(self, email: Email) -> Optional[Plan]:
        if not email.id:
            return None
        res = self.classifier.classify(email)
        action = PlanAction.MOVE
        if res.folder == "Unknown" or res.confidence != "high":
            action = PlanAction.REVIEW
        return Plan(
            source=PlanSource.LLM,
            action=action,
            email_id=email.id,
            llm_model=self.classifier.model,
            llm_confidence=res.confidence,
            llm_reasoning=res.reason,
            targets=[res.folder],
        )
