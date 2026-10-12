from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  subtitle TEXT NOT NULL,
  status TEXT NOT NULL,
  currency TEXT NOT NULL,
  headline TEXT NOT NULL,
  detail TEXT NOT NULL,
  intro TEXT NOT NULL,
  readiness REAL NOT NULL,
  submittable INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  submitted_at TEXT
);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  filename TEXT NOT NULL,
  media_type TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  path TEXT NOT NULL,
  extracted_text TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS expenses (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  document_id TEXT,
  merchant TEXT,
  expense_date TEXT,
  amount TEXT,
  currency TEXT,
  category TEXT,
  category_detail TEXT,
  attendees TEXT,
  purpose TEXT,
  status TEXT NOT NULL,
  policy_label TEXT NOT NULL,
  confidence REAL,
  is_duplicate INTEGER NOT NULL,
  duplicate_of TEXT,
  duplicate_reason TEXT,
  duplicate_accepted INTEGER NOT NULL,
  findings_json TEXT NOT NULL,
  missing_json TEXT NOT NULL,
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS questions (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  expense_id TEXT NOT NULL,
  field TEXT NOT NULL,
  prompt TEXT NOT NULL,
  reason TEXT NOT NULL,
  status TEXT NOT NULL,
  answer TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS judgments (
  id TEXT PRIMARY KEY,
  claim_id TEXT,
  task TEXT NOT NULL,
  model TEXT NOT NULL,
  output_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""

EXPENSE_FIELDS = {
    "merchant",
    "expense_date",
    "amount",
    "currency",
    "category",
    "category_detail",
    "attendees",
    "purpose",
    "status",
    "policy_label",
    "confidence",
    "is_duplicate",
    "duplicate_of",
    "duplicate_reason",
    "duplicate_accepted",
    "findings_json",
    "missing_json",
    "summary",
    "document_id",
    "override_reason",
    "override_by",
}


def _row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as conn:
            conn.executescript(SCHEMA)
            for migration in (
                "ALTER TABLE claims ADD COLUMN title_locked INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE expenses ADD COLUMN override_reason TEXT",
                "ALTER TABLE expenses ADD COLUMN override_by TEXT",
            ):
                try:
                    conn.execute(migration)
                except sqlite3.OperationalError:
                    pass

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def wipe(self) -> None:
        with self.transaction() as conn:
            for table in ("claims", "documents", "expenses", "questions", "messages", "judgments"):
                conn.execute(f"DELETE FROM {table}")

    def create_claim(self, row: dict) -> dict:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO claims
                   (id, title, subtitle, status, currency, headline, detail, intro, readiness, submittable, created_at)
                   VALUES (:id, :title, :subtitle, :status, :currency, :headline, :detail, :intro, :readiness, :submittable, :created_at)""",
                row,
            )
        return self.get_claim(row["id"])

    def get_claim(self, claim_id: str) -> dict:
        with self.transaction() as conn:
            found = _row(conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone())
        if found is None:
            raise KeyError(claim_id)
        return found

    def latest_claim(self) -> dict | None:
        with self.transaction() as conn:
            return _row(conn.execute("SELECT * FROM claims ORDER BY created_at DESC LIMIT 1").fetchone())

    def list_claims(self) -> list[dict]:
        with self.transaction() as conn:
            rows = conn.execute(
                """SELECT c.*, (SELECT COUNT(*) FROM expenses e WHERE e.claim_id = c.id) AS expense_count
                   FROM claims c ORDER BY c.created_at DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def rename_claim(self, claim_id: str, title: str) -> None:
        with self.transaction() as conn:
            conn.execute("UPDATE claims SET title = ?, title_locked = 1 WHERE id = ?", (title, claim_id))

    def delete_claim(self, claim_id: str) -> None:
        with self.transaction() as conn:
            for table in ("expenses", "documents", "questions", "messages", "judgments"):
                conn.execute(f"DELETE FROM {table} WHERE claim_id = ?", (claim_id,))
            conn.execute("DELETE FROM claims WHERE id = ?", (claim_id,))

    def expense_count(self) -> int:
        with self.transaction() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0])

    def add_document(self, row: dict) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO documents
                   (id, claim_id, filename, media_type, sha256, path, extracted_text, created_at)
                   VALUES (:id, :claim_id, :filename, :media_type, :sha256, :path, :extracted_text, :created_at)""",
                row,
            )

    def find_document(self, claim_id: str, digest: str) -> dict | None:
        with self.transaction() as conn:
            return _row(
                conn.execute(
                    "SELECT * FROM documents WHERE claim_id = ? AND sha256 = ?",
                    (claim_id, digest),
                ).fetchone()
            )

    def expense_for_document(self, document_id: str) -> dict | None:
        with self.transaction() as conn:
            return _row(conn.execute("SELECT * FROM expenses WHERE document_id = ?", (document_id,)).fetchone())

    def get_expense(self, expense_id: str) -> dict | None:
        with self.transaction() as conn:
            return _row(conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone())

    def get_document(self, document_id: str) -> dict | None:
        with self.transaction() as conn:
            return _row(conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone())

    def list_conversations(self, query: str | None = None) -> list[dict]:
        with self.transaction() as conn:
            claims = conn.execute(
                "SELECT id, title, status, created_at FROM claims ORDER BY created_at DESC"
            ).fetchall()
            conversations = []
            for claim in claims:
                if query:
                    rows = conn.execute(
                        """SELECT role, content, created_at FROM messages
                           WHERE claim_id = ? AND content LIKE ? ORDER BY created_at""",
                        (claim["id"], f"%{query}%"),
                    ).fetchall()
                    if not rows:
                        continue
                else:
                    rows = conn.execute(
                        "SELECT role, content, created_at FROM messages WHERE claim_id = ? ORDER BY created_at",
                        (claim["id"],),
                    ).fetchall()
                messages = [dict(row) for row in rows]
                conversations.append(
                    {
                        "claimId": claim["id"],
                        "title": claim["title"],
                        "status": claim["status"],
                        "messageCount": len(messages),
                        "lastAt": messages[-1]["created_at"] if messages else claim["created_at"],
                        "messages": messages,
                    }
                )
        return conversations

    def search_expenses(self, query: str, limit: int = 100) -> list[dict]:
        like = f"%{query}%"
        with self.transaction() as conn:
            rows = conn.execute(
                """SELECT e.merchant, e.expense_date AS date, e.amount, e.currency, e.category, e.status,
                          c.title AS claim_title, c.status AS claim_status
                   FROM expenses e JOIN claims c ON c.id = e.claim_id
                   WHERE e.merchant LIKE ? OR e.category LIKE ? OR e.category_detail LIKE ?
                      OR e.summary LIKE ? OR e.expense_date LIKE ? OR e.amount LIKE ? OR c.title LIKE ?
                   ORDER BY e.created_at DESC LIMIT ?""",
                (like, like, like, like, like, like, like, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def expenses_in_other_claims(self, claim_id: str, limit: int = 200) -> list[dict]:
        with self.transaction() as conn:
            rows = conn.execute(
                """SELECT e.merchant, e.expense_date, e.amount, e.currency, c.title AS claim_title, c.status AS claim_status
                   FROM expenses e JOIN claims c ON c.id = e.claim_id
                   WHERE e.claim_id != ? AND e.amount IS NOT NULL
                   ORDER BY e.created_at DESC LIMIT ?""",
                (claim_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_expense(self, row: dict) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO expenses (
                     id, claim_id, document_id, merchant, expense_date, amount, currency, category,
                     category_detail, attendees, purpose, status, policy_label, confidence, is_duplicate,
                     duplicate_of, duplicate_reason, duplicate_accepted, findings_json, missing_json, summary, created_at
                   ) VALUES (
                     :id, :claim_id, :document_id, :merchant, :expense_date, :amount, :currency, :category,
                     :category_detail, :attendees, :purpose, :status, :policy_label, :confidence, :is_duplicate,
                     :duplicate_of, :duplicate_reason, :duplicate_accepted, :findings_json, :missing_json, :summary, :created_at
                   )""",
                row,
            )

    def update_expense(self, expense_id: str, fields: dict) -> None:
        unknown = set(fields) - EXPENSE_FIELDS
        if unknown:
            raise KeyError(", ".join(sorted(unknown)))
        if not fields:
            return
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [expense_id]
        with self.transaction() as conn:
            conn.execute(f"UPDATE expenses SET {assignments} WHERE id = ?", values)

    def delete_expense(self, expense_id: str) -> None:
        with self.transaction() as conn:
            conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            conn.execute("DELETE FROM questions WHERE expense_id = ?", (expense_id,))

    def list_expenses(self, claim_id: str) -> list[dict]:
        with self.transaction() as conn:
            rows = conn.execute(
                """SELECT e.*, d.filename AS filename
                   FROM expenses e
                   LEFT JOIN documents d ON d.id = e.document_id
                   WHERE e.claim_id = ?
                   ORDER BY e.created_at""",
                (claim_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_message(self, row: dict) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO messages (id, claim_id, role, content, created_at) VALUES (:id, :claim_id, :role, :content, :created_at)",
                row,
            )

    def list_messages(self, claim_id: str) -> list[dict]:
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE claim_id = ? ORDER BY created_at",
                (claim_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_judgment(self, row: dict) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO judgments (id, claim_id, task, model, output_json, created_at) VALUES (:id, :claim_id, :task, :model, :output_json, :created_at)",
                row,
            )

    def get_question(self, question_id: str) -> dict | None:
        with self.transaction() as conn:
            return _row(conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone())

    def open_question(self, claim_id: str) -> dict | None:
        with self.transaction() as conn:
            return _row(
                conn.execute(
                    "SELECT * FROM questions WHERE claim_id = ? AND status = 'open' ORDER BY created_at DESC LIMIT 1",
                    (claim_id,),
                ).fetchone()
            )

    def save_outcome(self, claim_id: str, claim_fields: dict, labels: list[dict], question: dict | None) -> None:
        with self.transaction() as conn:
            # a user-chosen title is never overwritten by the model's replan
            conn.execute(
                """UPDATE claims
                   SET title = CASE WHEN title_locked = 1 THEN title ELSE ? END,
                       subtitle = ?, headline = ?, detail = ?, intro = ?, readiness = ?, submittable = ?
                   WHERE id = ?""",
                (
                    claim_fields["title"],
                    claim_fields["subtitle"],
                    claim_fields["headline"],
                    claim_fields["detail"],
                    claim_fields["intro"],
                    claim_fields["readiness"],
                    claim_fields["submittable"],
                    claim_id,
                ),
            )
            for label in labels:
                conn.execute(
                    "UPDATE expenses SET status = ?, policy_label = ? WHERE id = ? AND claim_id = ?",
                    (label["status"], label["policy_label"], label["expense_id"], claim_id),
                )
            conn.execute("DELETE FROM questions WHERE claim_id = ? AND status = 'open'", (claim_id,))
            if question is not None:
                conn.execute(
                    """INSERT INTO questions
                       (id, claim_id, expense_id, field, prompt, reason, status, created_at)
                       VALUES (:id, :claim_id, :expense_id, :field, :prompt, :reason, 'open', :created_at)""",
                    question,
                )

    def reopen_claim(self, claim_id: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                """UPDATE claims SET status = 'DRAFT', submitted_at = NULL,
                   headline = 'Claim reopened', detail = 'Review the receipts and submit again when ready.'
                   WHERE id = ?""",
                (claim_id,),
            )

    def mark_submitted(self, claim_id: str, when: str, headline: str, detail: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                """UPDATE claims
                   SET status = 'SUBMITTED', submitted_at = ?, submittable = 1, readiness = 1, headline = ?, detail = ?
                   WHERE id = ?""",
                (when, headline, detail, claim_id),
            )
            conn.execute("DELETE FROM questions WHERE claim_id = ? AND status = 'open'", (claim_id,))
