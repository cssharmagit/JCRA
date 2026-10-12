from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger("expense_agent")

from pydantic import ValidationError

from app.config import Settings
from app.db import Database
from app.errors import AgentError, CognitionError
from app.schemas import DocumentReading, Judgment, Plan, Turn, Understanding
from app.services.files import extract_text, needs_vision, sniff
from app.services.llm import Attachment, LLM
from app.services.present import present

SEED_FILES = (
    "01-blue-bottle.txt",
    "02-united.txt",
    "03-hoxton.txt",
    "04-lyft.txt",
    "05-nopa-receipt.txt",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def to_amount(value: float | None) -> str | None:
    if value is None:
        return None
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def clean(value: str | None, limit: int = 160) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split())
    return text[:limit] or None


def date_facts(value: str | None) -> dict:
    """Deterministic date checks so the model never does calendar math itself."""
    from datetime import date

    today = date.today()
    facts = {"today": today.isoformat(), "is_future": False, "is_older_than_24_months": False, "parseable": False}
    if not value:
        return facts
    try:
        parsed = date.fromisoformat(str(value)[:10])
    except ValueError:
        return facts
    facts["parseable"] = True
    facts["is_future"] = parsed > today
    try:
        cutoff = today.replace(year=today.year - 2)
    except ValueError:
        cutoff = today.replace(year=today.year - 2, day=28)
    facts["is_older_than_24_months"] = parsed < cutoff
    return facts


class ClaimAgent:
    """Runs the cognitive steps. Code stores the result and blocks submission when money fields are missing."""

    def __init__(self, db: Database, llm: LLM, settings: Settings):
        self.db = db
        self.llm = llm
        self.settings = settings
        self.active_claim_id: str | None = None

    @property
    def policy(self) -> str:
        if self.settings.policy_text is not None:
            return self.settings.policy_text
        return self.settings.policy_path.read_text(encoding="utf-8")

    def bootstrap(self) -> None:
        self.db.init()
        self.settings.files_dir.mkdir(parents=True, exist_ok=True)
        if self.settings.seed_demo and self.llm.name == "replay" and self.db.expense_count() == 0:
            files = []
            for name in SEED_FILES:
                path = self.settings.seed_dir / name
                files.append((name, "text/plain", path.read_bytes()))
            self.ingest_many(files)
        elif self.db.latest_claim() is None:
            self._create_blank(with_message=True)

    def _current_claim(self) -> dict | None:
        if self.active_claim_id:
            try:
                return self.db.get_claim(self.active_claim_id)
            except KeyError:
                self.active_claim_id = None
        return self.db.latest_claim()

    def view(self, notice: str | None = None) -> dict:
        claim = self._current_claim()
        if claim is None:
            claim = self._create_blank(with_message=True)
        return present(
            claim,
            self.db.list_expenses(claim["id"]),
            self.db.open_question(claim["id"]),
            self.db.list_messages(claim["id"]),
            self.llm.name,
            notice,
            home_currency=self.settings.home_currency,
            fx_rates=self.settings.fx_rates,
            employee_name=self.settings.employee_name,
            employee_dept=self.settings.employee_dept,
        )

    def ingest_many(self, files: list[tuple[str, str, bytes]]) -> dict:
        if not files:
            raise AgentError("Choose at least one receipt.", 400)
        if len(files) > self.settings.max_files:
            raise AgentError(f"Upload up to {self.settings.max_files} files at a time.", 400)
        claim = self._editable_claim()
        notices = []
        added = 0
        errors = 0
        first_error: AgentError | None = None
        for filename, content_type, data in files:
            try:
                outcome = self._ingest_one(claim["id"], filename, content_type, data)
            except AgentError as exc:
                # one unreadable file must not sink the whole batch
                errors += 1
                first_error = first_error or exc
                notices.append(f"{filename}: {exc}")
                continue
            except Exception:
                logger.exception("Unexpected failure reading %s", filename)
                errors += 1
                notices.append(f"{filename}: I hit an unexpected problem reading this file.")
                continue
            if isinstance(outcome, int):
                added += outcome
            else:
                notices.append(outcome)
        if not added and errors == len(files) and first_error is not None:
            raise first_error
        if added:
            plan = self._replan(claim["id"])
            self._message(claim["id"], "assistant", plan.note)
        notice = " ".join(notices) if notices else None
        if added and not notice:
            notice = f"{added} {'receipt' if added == 1 else 'receipts'} read"
        elif added and notice:
            notice = f"{added} receipts read. {notice}"
        if not added and not notice:
            notice = "I couldn't read anything from those files."
        return self.view(notice)

    def converse(self, text: str) -> dict:
        text = text.strip()
        if not text:
            raise AgentError("Write a message first.", 400)
        if len(text) > 4000:
            raise AgentError("That message is too long.", 400)
        claim = self._current_claim() or self._create_blank(with_message=True)
        self._message(claim["id"], "user", text)
        if claim["status"] == "SUBMITTED":
            if re.search(r"\b(new|another|fresh|next)\b.*\bclaim\b|\bclaim\b.*\b(new|another|fresh)\b|start over", text, re.I):
                self._message(claim["id"], "assistant", "Starting a new claim.")
                fresh = self._create_blank(with_message=True)
                self.active_claim_id = fresh["id"]
                return self.view("Started a new claim.")
            if re.search(r"\b(reopen|re-open|unsubmit|un-submit|unlock|undo\s+submit|submitted?\s+by\s+mistake)\b", text, re.I):
                self.db.reopen_claim(claim["id"])
                self.db.add_judgment(
                    {
                        "id": new_id(),
                        "claim_id": claim["id"],
                        "task": "reopen",
                        "model": "human",
                        "output_json": json.dumps({"by": self.settings.employee_name, "via": "chat"}),
                        "created_at": now(),
                    }
                )
                self._message(claim["id"], "assistant", f'Reopened "{claim["title"]}". It is out of the finance queue; edit what you need and submit again.')
                self._replan(claim["id"])
                return self.view("Claim reopened for editing.")
            # locked claims still answer questions (incl. across claims); they just reject edits
            turn = self._think(
                claim["id"],
                "interpret_turn",
                {
                    "policy": self.policy,
                    "user_text": text,
                    "claim_locked": True,
                    "open_question": None,
                    "expenses": [_model_expense(expense) for expense in self.db.list_expenses(claim["id"])],
                    "other_claim_expenses": self.db.expenses_in_other_claims(claim["id"]),
                    "messages": [_message_payload(message) for message in self.db.list_messages(claim["id"])[-8:]],
                },
                Turn,
            )
            reply = turn.reply.strip() or "This claim is submitted and locked."
            if turn.updates or turn.wants_submit or turn.set_policy_to or turn.rename_claim_to:
                reply = 'This claim is submitted and locked, so I can\'t change it. Say "reopen this claim" to unlock it, or "start a new claim".'
            if turn.start_new_claim:
                self._message(claim["id"], "assistant", "Starting a new claim.")
                fresh = self._create_blank(with_message=True)
                self.active_claim_id = fresh["id"]
                return self.view("Started a new claim.")
            self._message(claim["id"], "assistant", reply)
            view = self.view()
            if turn.ui_action in ("focus_chat", "show_expenses"):
                view["uiAction"] = turn.ui_action
            return view
        question = self.db.open_question(claim["id"])
        turn = self._think(
            claim["id"],
            "interpret_turn",
            {
                "policy": self.policy,
                "user_text": text,
                "open_question": _question_payload(question),
                "expenses": [_model_expense(expense) for expense in self.db.list_expenses(claim["id"])],
                "other_claim_expenses": self.db.expenses_in_other_claims(claim["id"]),
                "messages": [_message_payload(message) for message in self.db.list_messages(claim["id"])[-8:]],
            },
            Turn,
        )
        rejudge_ids = []
        for update in turn.updates:
            expense = self._owned_expense(claim["id"], update.expense_id)
            if expense is None:
                continue
            if update.remove:
                self.db.delete_expense(expense["id"])
                continue
            fields = {}
            if update.attendees is not None:
                fields["attendees"] = clean(update.attendees, 400)
            if update.purpose is not None:
                fields["purpose"] = clean(update.purpose, 400)
            if update.merchant is not None:
                fields["merchant"] = clean(update.merchant)
            if update.date is not None:
                fields["expense_date"] = clean(update.date, 40)
            if update.amount is not None:
                fields["amount"] = to_amount(update.amount)
            if update.category is not None:
                fields["category"] = clean(update.category, 40)
            if update.category_detail is not None:
                fields["category_detail"] = clean(update.category_detail, 80)
            if update.duplicate_accepted is not None:
                fields["duplicate_accepted"] = 1 if update.duplicate_accepted else 0
            if fields:
                self.db.update_expense(expense["id"], fields)
                rejudge_ids.append(expense["id"])
        for expense_id in rejudge_ids:
            self._rejudge(claim["id"], expense_id)
        if turn.rename_claim_to:
            title = clean(turn.rename_claim_to, 80)
            if title and not any(row["title"].lower() == title.lower() and row["id"] != claim["id"] for row in self.db.list_claims()):
                self.db.rename_claim(claim["id"], title)
        policy_refused = False
        if turn.set_policy_to and len(turn.set_policy_to.strip()) >= 20:
            if self.settings.admin_enabled:
                # chat runs as the employee; policy edits need the admin token
                policy_refused = True
            else:
                self.settings.policy_text = turn.set_policy_to.strip()
                self.settings.save_overrides()
        if turn.start_new_claim:
            reply = turn.reply.strip() or "Started a new claim."
            self._message(claim["id"], "assistant", reply)
            fresh = self._create_blank(with_message=True)
            self.active_claim_id = fresh["id"]
            return self.view("Started a new claim.")
        plan = self._replan(claim["id"])
        reply = turn.reply.strip() or plan.note
        if policy_refused:
            reply = "Policy changes need admin access. Use the Settings view with the admin token, or ask your administrator."
        if turn.wants_export:
            if (turn.export_format or "csv").lower() == "json":
                valid = [field for field in turn.export_fields if field in self.EXPORT_FIELDS]
                suffix = f"?fields={','.join(valid)}" if valid else ""
                reply = f"{reply.rstrip('.')}. Download it here: /api/claims/active/export.json{suffix}"
            else:
                reply = f"{reply.rstrip('.')}. Download it here: /api/claims/active/export.csv"
        if turn.wants_submit:
            if self._ready(claim["id"]):
                self._lock(claim["id"])
                reply = f"{reply.rstrip(' .')} I submitted it and locked the claim."
            else:
                reply = f"{reply.rstrip('.')} . {plan.detail}"
        self._message(claim["id"], "assistant", reply)
        view = self.view()
        if turn.ui_action in ("focus_chat", "show_expenses"):
            view["uiAction"] = turn.ui_action
        return view

    def answer(self, question_id: str, text: str) -> dict:
        question = self.db.get_question(question_id)
        claim = self._current_claim()
        if claim is None:
            raise AgentError("There is no active claim.", 404)
        stale = question is None or question["claim_id"] != claim["id"] or question["status"] != "open"
        if stale and self.db.open_question(claim["id"]) is None:
            raise AgentError("That question is no longer open.", 404)
        # a replan may have re-issued the question under a new id; the
        # conversation flow resolves against the current open question
        return self.converse(text)

    def reset(self) -> dict:
        """Admin: wipe all claims and start fresh so receipts can be re-tested."""
        self.db.wipe()
        self.active_claim_id = None
        self._create_blank(with_message=True)
        return self.view("All data cleared. Drop receipts to start fresh.")

    def list_claims(self) -> dict:
        active = self._current_claim()
        return {
            "activeId": active["id"] if active else None,
            "claims": [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "subtitle": row["subtitle"],
                    "status": row["status"],
                    "expenseCount": row["expense_count"],
                    "createdAt": row["created_at"],
                    "submittedAt": row["submitted_at"],
                }
                for row in self.db.list_claims()
            ],
        }

    def new_claim(self) -> dict:
        claim = self._create_blank(with_message=True)
        self.active_claim_id = claim["id"]
        return self.view("Started a new claim.")

    def rename_claim(self, title: str) -> dict:
        title = clean(title, 80)
        if not title:
            raise AgentError("Give the claim a name first.", 400)
        claim = self._current_claim()
        if claim is None:
            raise AgentError("There is no claim to rename.", 404)
        if claim["status"] == "SUBMITTED":
            raise AgentError("This claim is submitted and locked.", 409)
        taken = any(row["title"].lower() == title.lower() and row["id"] != claim["id"] for row in self.db.list_claims())
        if taken:
            raise AgentError(f'A claim named "{title}" already exists. Pick a different name.', 409)
        self.db.rename_claim(claim["id"], title)
        return self.view(f'Renamed to "{title}".')

    def open_claim(self, claim_id: str) -> dict:
        try:
            self.db.get_claim(claim_id)
        except KeyError:
            raise AgentError("That claim no longer exists.", 404)
        self.active_claim_id = claim_id
        return self.view()

    def reopen_claim(self, claim_id: str | None = None) -> dict:
        """Unlock a submitted claim back to draft, with an audit record."""
        claim = self.db.get_claim(claim_id) if claim_id else self._current_claim()
        if claim is None:
            raise AgentError("There is no claim to reopen.", 404)
        if claim["status"] != "SUBMITTED":
            raise AgentError("This claim is not submitted; it is already editable.", 409)
        self.db.reopen_claim(claim["id"])
        self.active_claim_id = claim["id"]
        self.db.add_judgment(
            {
                "id": new_id(),
                "claim_id": claim["id"],
                "task": "reopen",
                "model": "human",
                "output_json": json.dumps({"by": self.settings.employee_name}),
                "created_at": now(),
            }
        )
        self._message(claim["id"], "assistant", f'Reopened "{claim["title"]}" for editing. It is out of the finance queue until you submit it again.')
        self._replan(claim["id"])
        return self.view("Claim reopened for editing.")

    def delete_claim(self, claim_id: str) -> dict:
        try:
            claim = self.db.get_claim(claim_id)
        except KeyError:
            raise AgentError("That claim no longer exists.", 404)
        if claim["status"] == "SUBMITTED":
            raise AgentError("Submitted claims are locked and kept for the finance queue.", 409)
        self.db.delete_claim(claim_id)
        if self.active_claim_id == claim_id:
            self.active_claim_id = None
        if self.db.latest_claim() is None:
            self._create_blank(with_message=True)
        return self.view("Claim deleted.")

    def expense_detail(self, expense_id: str) -> dict:
        claim = self._current_claim()
        expense = self.db.get_expense(expense_id)
        if claim is None or expense is None or expense["claim_id"] != claim["id"]:
            raise AgentError("That expense is not on this claim.", 404)
        document = self.db.get_document(expense["document_id"]) if expense["document_id"] else None
        return {
            "id": expense["id"],
            "merchant": expense["merchant"],
            "date": expense["expense_date"],
            "amount": expense["amount"],
            "currency": expense["currency"],
            "category": expense["category"],
            "categoryDetail": expense["category_detail"],
            "attendees": expense["attendees"],
            "purpose": expense["purpose"],
            "status": expense["status"],
            "policyLabel": expense["policy_label"],
            "confidence": expense["confidence"],
            "summary": expense["summary"],
            "findings": json.loads(expense["findings_json"] or "[]"),
            "missing": json.loads(expense["missing_json"] or "[]"),
            "isDuplicate": bool(expense["is_duplicate"]),
            "duplicateReason": expense["duplicate_reason"],
            "overrideReason": expense.get("override_reason"),
            "overrideBy": expense.get("override_by"),
            "document": None
            if document is None
            else {
                "id": document["id"],
                "filename": document["filename"],
                "mediaType": document["media_type"],
                "extractedText": (document["extracted_text"] or "")[:4000],
            },
        }

    def override_expense(self, expense_id: str, reason: str) -> dict:
        """Approve an expense past a policy flag, with a persisted explanation."""
        reason = clean(reason, 400)
        if not reason:
            raise AgentError("An override needs an explanation.", 400)
        claim = self._current_claim()
        expense = self.db.get_expense(expense_id)
        if claim is None or expense is None or expense["claim_id"] != claim["id"]:
            raise AgentError("That expense is not on this claim.", 404)
        if claim["status"] == "SUBMITTED":
            raise AgentError("This claim is submitted and locked.", 409)
        if not expense["merchant"] or not expense["expense_date"] or not expense["amount"]:
            raise AgentError("Merchant, date, and amount are required even with an override.", 409)
        approver = self.settings.employee_name
        self.db.update_expense(
            expense_id,
            {
                "status": "ready",
                "policy_label": "Approved with override",
                "is_duplicate": 0,
                "missing_json": "[]",
                "override_reason": reason,
                "override_by": approver,
            },
        )
        self.db.add_judgment(
            {
                "id": new_id(),
                "claim_id": claim["id"],
                "task": "override",
                "model": "human",
                "output_json": json.dumps({"expense_id": expense_id, "reason": reason, "by": approver}),
                "created_at": now(),
            }
        )
        self._replan(claim["id"])
        self._message(claim["id"], "assistant", f"Override recorded by {approver}: {reason}")
        return self.view("Override recorded.")

    def delete_expense(self, expense_id: str) -> dict:
        claim = self._current_claim()
        expense = self.db.get_expense(expense_id)
        if claim is None or expense is None or expense["claim_id"] != claim["id"]:
            raise AgentError("That expense is not on this claim.", 404)
        if claim["status"] == "SUBMITTED":
            raise AgentError("This claim is submitted and locked.", 409)
        self.db.delete_expense(expense_id)
        if self.db.list_expenses(claim["id"]):
            self._replan(claim["id"])
        return self.view("Receipt removed.")

    def export_csv(self) -> tuple[str, str]:
        """Returns (filename, csv_text) for the active claim."""
        import csv
        import io

        claim = self._current_claim()
        if claim is None:
            raise AgentError("There is no claim to export.", 404)
        expenses = self.db.list_expenses(claim["id"])
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(["Merchant", "Date", "Amount", "Currency", "Category", "Detail", "Status", "Policy label", "Attendees", "Purpose", "Override reason", "Override by", "Source file"])
        for expense in expenses:
            writer.writerow([
                expense["merchant"] or "",
                expense["expense_date"] or "",
                expense["amount"] or "",
                expense["currency"] or "",
                expense["category"] or "",
                expense["category_detail"] or "",
                expense["status"],
                expense["policy_label"],
                expense["attendees"] or "",
                expense["purpose"] or "",
                expense.get("override_reason") or "",
                expense.get("override_by") or "",
                expense.get("filename") or "",
            ])
        safe_title = re.sub(r"[^\w\- ]", "", claim["title"]).strip().replace(" ", "_") or "claim"
        return f"{safe_title}.csv", buffer.getvalue()

    EXPORT_FIELDS = {
        "merchant": "merchant",
        "date": "expense_date",
        "amount": "amount",
        "currency": "currency",
        "category": "category",
        "category_detail": "category_detail",
        "status": "status",
        "policy_label": "policy_label",
        "attendees": "attendees",
        "purpose": "purpose",
        "override_reason": "override_reason",
        "override_by": "override_by",
        "source_file": "filename",
        "confidence": "confidence",
        "summary": "summary",
    }

    def export_json(self, fields: list[str] | None = None) -> tuple[str, dict]:
        """Returns (filename, payload). fields filters/orders the per-expense keys."""
        claim = self._current_claim()
        if claim is None:
            raise AgentError("There is no claim to export.", 404)
        if fields:
            unknown = [field for field in fields if field not in self.EXPORT_FIELDS]
            if unknown:
                raise AgentError(f"Unknown fields: {', '.join(unknown)}. Available: {', '.join(self.EXPORT_FIELDS)}.", 400)
            selected = fields
        else:
            selected = list(self.EXPORT_FIELDS)
        expenses = []
        for expense in self.db.list_expenses(claim["id"]):
            row = {}
            for field in selected:
                value = expense.get(self.EXPORT_FIELDS[field])
                if field == "amount" and value is not None:
                    value = float(value)
                row[field] = value
            expenses.append(row)
        payload = {
            "claim": {
                "id": claim["id"],
                "title": claim["title"],
                "status": claim["status"],
                "currency": self.settings.home_currency,
                "employee": {"name": self.settings.employee_name, "dept": self.settings.employee_dept},
                "created_at": claim["created_at"],
                "submitted_at": claim["submitted_at"],
            },
            "expenses": expenses,
        }
        safe_title = re.sub(r"[^\w\- ]", "", claim["title"]).strip().replace(" ", "_") or "claim"
        return f"{safe_title}.json", payload

    def search_expenses(self, query: str) -> dict:
        """Case-insensitive substring search across every claim."""
        query = (query or "").strip()
        if not query:
            raise AgentError("Give me something to search for.", 400)
        matches = self.db.search_expenses(query)
        return {"query": query, "count": len(matches), "results": matches}

    def list_conversations(self, query: str | None = None) -> dict:
        return {"conversations": self.db.list_conversations((query or "").strip() or None)}

    def insights(self) -> dict:
        """Spend aggregates across every claim, in the home currency."""
        home = self.settings.home_currency
        rates = self.settings.fx_rates
        by_category: dict[str, float] = {}
        by_claim: list[dict] = []
        total = 0.0
        expense_count = 0
        for claim in self.db.list_claims():
            claim_total = 0.0
            for expense in self.db.list_expenses(claim["id"]):
                if not expense.get("amount"):
                    continue
                amount = float(expense["amount"])
                code = (expense.get("currency") or home).upper()
                if code != home:
                    rate = rates.get(code)
                    if rate is None:
                        continue
                    amount *= float(rate)
                category = expense.get("category") or "Other"
                by_category[category] = by_category.get(category, 0.0) + amount
                claim_total += amount
                expense_count += 1
            total += claim_total
            by_claim.append(
                {
                    "id": claim["id"],
                    "title": claim["title"],
                    "status": claim["status"],
                    "expenseCount": claim["expense_count"],
                    "total": round(claim_total, 2),
                }
            )
        return {
            "currency": home,
            "total": round(total, 2),
            "expenseCount": expense_count,
            "claimCount": len(by_claim),
            "byCategory": sorted(
                ({"category": name, "total": round(value, 2)} for name, value in by_category.items()),
                key=lambda item: -item["total"],
            ),
            "byClaim": by_claim,
        }

    def get_policy(self) -> str:
        return self.policy

    def set_policy(self, text: str) -> dict:
        text = (text or "").strip()
        if len(text) < 20:
            raise AgentError("The policy text looks too short to be real.", 400)
        self.settings.policy_text = text
        self.settings.save_overrides()
        return self.view("Policy updated. New receipts will be checked against it.")

    def document_file(self, document_id: str) -> tuple[str, str, bytes]:
        claim = self._current_claim()
        document = self.db.get_document(document_id)
        if claim is None or document is None or document["claim_id"] != claim["id"]:
            raise AgentError("That document is not on this claim.", 404)
        path = Path(document["path"])
        if not path.exists():
            raise AgentError("The original file is no longer stored.", 404)
        return document["filename"], document["media_type"], path.read_bytes()

    def submit(self) -> dict:
        claim = self._current_claim()
        if claim is None:
            raise AgentError("There is no claim to submit.", 409)
        if claim["status"] == "SUBMITTED":
            raise AgentError("This claim is already submitted.", 409)
        if not self._ready(claim["id"]):
            raise AgentError(claim["detail"] or "This claim still needs attention.", 409)
        self._lock(claim["id"])
        self._message(claim["id"], "assistant", "Submitted. I locked the claim for the finance queue.")
        return self.view()

    def _ingest_one(self, claim_id: str, filename: str, content_type: str, data: bytes) -> int | str:
        if len(data) > self.settings.max_file_mb * 1024 * 1024:
            raise AgentError(f"{filename} is larger than {self.settings.max_file_mb} MB.", 413)
        media = sniff(filename, content_type)
        if media is None:
            raise AgentError("Use a photo, PDF, or text receipt.", 415)
        digest = hashlib.sha256(data).hexdigest()
        existing = self.db.find_document(claim_id, digest)
        if existing and self.db.expense_for_document(existing["id"]):
            return f"{filename} is the same file I already filed."
        text = extract_text(media, data)
        path = self.settings.files_dir / digest
        if not path.exists():
            path.write_bytes(data)
        document_id = existing["id"] if existing else new_id()
        if existing is None:
            self.db.add_document(
                {
                    "id": document_id,
                    "claim_id": claim_id,
                    "filename": filename or "receipt",
                    "media_type": media,
                    "sha256": digest,
                    "path": str(path),
                    "extracted_text": text[:20000],
                    "created_at": now(),
                }
            )
        attachments = [Attachment(filename or "receipt", media, data)] if needs_vision(media, text) else None
        reading = self._think(
            claim_id,
            "understand_document",
            {"policy": self.policy, "filename": filename, "media_type": media, "text": text},
            DocumentReading,
            attachments,
        )
        receipts = reading.receipts or [Understanding()]
        for understanding in receipts:
            candidates = [_model_expense(expense) for expense in self.db.list_expenses(claim_id)]
            judgment = self._judge(
                claim_id,
                {
                    "policy": self.policy,
                    "extraction": understanding.model_dump(),
                    "date_facts": date_facts(understanding.date),
                    "employee_context": {},
                    "candidates": candidates,
                    "other_claim_expenses": self.db.expenses_in_other_claims(claim_id),
                },
            )
            self.db.add_expense(self._expense_row(claim_id, document_id, understanding, judgment))
        return len(receipts)

    def _judge(self, claim_id: str, payload: dict) -> Judgment:
        judgment = self._think(claim_id, "judge_expense", payload, Judgment)
        if not _asks_for_filled_meal_gap(judgment, payload.get("employee_context") or {}):
            return judgment
        retry = dict(payload)
        retry["correction"] = (
            "Your previous judgment asked for attendees or a business purpose, and the employee has already supplied one of them. "
            "The policy accepts either. Remove that request. Keep a blocker only when a different rule still applies."
        )
        return self._think(claim_id, "judge_expense", retry, Judgment)

    def _rejudge(self, claim_id: str, expense_id: str) -> None:
        expense = self._owned_expense(claim_id, expense_id)
        if expense is None:
            return
        if expense.get("override_reason"):
            return  # a recorded human override stands until it is explicitly removed
        candidates = [
            _model_expense(item)
            for item in self.db.list_expenses(claim_id)
            if item["id"] != expense_id
        ]
        judgment = self._judge(
            claim_id,
            {
                "policy": self.policy,
                "extraction": {
                    "merchant": expense["merchant"],
                    "date": expense["expense_date"],
                    "amount": float(expense["amount"]) if expense["amount"] else None,
                    "currency": expense["currency"],
                    "summary": expense["summary"],
                    "confidence": expense["confidence"],
                },
                "date_facts": date_facts(expense["expense_date"]),
                "employee_context": {
                    "attendees": expense["attendees"],
                    "purpose": expense["purpose"],
                    "duplicate_accepted": bool(expense["duplicate_accepted"]),
                },
                "candidates": candidates,
                "other_claim_expenses": self.db.expenses_in_other_claims(claim_id),
            },
        )
        self.db.update_expense(expense_id, self._judgment_fields(expense, judgment))

    def _replan(self, claim_id: str) -> Plan:
        claim = self.db.get_claim(claim_id)
        expenses = self.db.list_expenses(claim_id)
        plan = self._think(
            claim_id,
            "plan_claim",
            {
                "policy": self.policy,
                "current_title": claim["title"],
                "expenses": [_model_expense(expense) for expense in expenses],
            },
            Plan,
        )
        plan = self._finalize(plan, expenses)
        question = None
        if plan.next_question is not None and not plan.submittable:
            question = {
                "id": new_id(),
                "claim_id": claim_id,
                "expense_id": plan.next_question.expense_id,
                "field": plan.next_question.field,
                "prompt": plan.next_question.prompt,
                "reason": plan.next_question.reason,
                "created_at": now(),
            }
        self.db.save_outcome(
            claim_id,
            {
                "title": plan.title,
                "subtitle": plan.subtitle,
                "headline": plan.headline,
                "detail": plan.detail,
                "intro": plan.intro,
                "readiness": plan.readiness,
                "submittable": 1 if plan.submittable else 0,
            },
            [label.model_dump() for label in plan.labels],
            question,
        )
        return plan

    def _finalize(self, plan: Plan, expenses: list[dict]) -> Plan:
        attention_ids = []
        for expense in expenses:
            missing = json.loads(expense["missing_json"] or "[]")
            unresolved = bool(expense["is_duplicate"]) and not bool(expense["duplicate_accepted"])
            incomplete = not expense["merchant"] or not expense["expense_date"] or not expense["amount"]
            if expense["status"] == "attention" or missing or unresolved or incomplete:
                attention_ids.append(expense["id"])
        computed_ready = bool(expenses) and not attention_ids
        model_ready = plan.submittable and plan.next_question is None
        known = {expense["id"] for expense in expenses}
        if plan.next_question is not None and plan.next_question.expense_id not in known:
            plan.next_question = None
        if not computed_ready and plan.next_question is None and attention_ids:
            plan.next_question = self._question_for(expenses, attention_ids[0])
        if model_ready != computed_ready:
            count = len(expenses)
            gaps = len(attention_ids)
            if computed_ready:
                plan.headline = "Everything looks good"
                plan.detail = (
                    f"All {count} expenses passed your company policy."
                    if count != 1
                    else "This expense passed your company policy."
                )
                plan.note = "Nice — your claim is complete and ready to submit."
                plan.next_question = None
            else:
                plan.headline = "Almost ready to submit" if gaps == 1 else "A few details need you"
                plan.detail = (
                    f"I checked {count} receipts. One detail needs your review."
                    if gaps == 1
                    else f"I checked {count} receipts. {gaps} details need your review."
                )
        if computed_ready:
            plan.readiness = 1
            plan.next_question = None
        elif expenses:
            plan.readiness = min(plan.readiness, (len(expenses) - len(attention_ids)) / len(expenses))
        else:
            plan.readiness = 0
        labels = []
        for expense in expenses:
            if expense["id"] in attention_ids:
                label = expense["policy_label"] or "Add details"
                if bool(expense["is_duplicate"]) and not bool(expense["duplicate_accepted"]):
                    label = "Possible duplicate"
                elif label == "Policy checked":
                    label = "Add details"
                labels.append({"expense_id": expense["id"], "status": "attention", "policy_label": label})
            else:
                label = "Approved with override" if expense.get("override_reason") else "Policy checked"
                labels.append({"expense_id": expense["id"], "status": "ready", "policy_label": label})
        plan.labels = [_label(label) for label in labels]
        plan.submittable = computed_ready
        return plan

    def _question_for(self, expenses: list[dict], expense_id: str):
        from app.schemas import NextQuestion

        expense = next(item for item in expenses if item["id"] == expense_id)
        missing = json.loads(expense["missing_json"] or "[]")
        if missing:
            item = missing[0]
            return NextQuestion(expense_id=expense_id, field=item["field"], prompt=item["question"], reason=item["reason"])
        if expense["is_duplicate"] and not expense["duplicate_accepted"]:
            return NextQuestion(
                expense_id=expense_id,
                field="duplicate",
                prompt="This looks like the same charge I already have. Is it a separate expense?",
                reason=expense["duplicate_reason"] or "Possible duplicate.",
            )
        if not expense["amount"]:
            field, prompt = "amount", "What was the total on this receipt?"
        elif not expense["merchant"]:
            field, prompt = "merchant", "Which merchant is this receipt from?"
        else:
            field, prompt = "date", "What date is on this receipt?"
        return NextQuestion(
            expense_id=expense_id,
            field=field,
            prompt=prompt,
            reason=f"I still need the {field} before this can be submitted.",
        )

    def _expense_row(self, claim_id: str, document_id: str, understanding: Understanding, judgment: Judgment) -> dict:
        fields = self._judgment_fields(
            {
                "merchant": understanding.merchant,
                "expense_date": understanding.date,
                "amount": to_amount(understanding.amount),
                "currency": understanding.currency or "USD",
                "summary": understanding.summary,
                "duplicate_accepted": 0,
            },
            judgment,
        )
        fields.update(
            {
                "id": new_id(),
                "claim_id": claim_id,
                "document_id": document_id,
                "attendees": None,
                "purpose": None,
                "confidence": understanding.confidence,
                "duplicate_accepted": 0,
                "created_at": now(),
            }
        )
        return fields

    def _judgment_fields(self, expense: dict, judgment: Judgment) -> dict:
        merchant = clean(judgment.merchant or expense.get("merchant"))
        date = judgment.date or expense.get("expense_date")
        amount = to_amount(judgment.amount) if judgment.amount is not None else expense.get("amount")
        missing = [item.model_dump() for item in judgment.missing]
        accepted = bool(expense.get("duplicate_accepted"))
        duplicate = bool(judgment.is_duplicate) and not accepted
        incomplete = not merchant or not date or not amount
        status = "attention" if duplicate or missing or incomplete or judgment.policy_status == "attention" else "ready"
        label = judgment.policy_label or ("Add details" if status == "attention" else "Policy checked")
        if duplicate:
            label = "Possible duplicate"
        elif status == "attention" and label == "Policy checked":
            label = "Add details"
        return {
            "merchant": merchant,
            "expense_date": date,
            "amount": amount,
            "currency": (judgment.currency or expense.get("currency") or "USD").upper(),
            "category": clean(judgment.category, 40) or "Other",
            "category_detail": clean(judgment.category_detail, 80) or "",
            "status": status,
            "policy_label": label,
            "is_duplicate": 1 if duplicate else 0,
            "duplicate_of": judgment.duplicate_of,
            "duplicate_reason": judgment.duplicate_reason,
            "findings_json": json.dumps([item.model_dump() for item in judgment.findings]),
            "missing_json": json.dumps(missing),
            "summary": expense.get("summary") or "",
        }

    def _think(self, claim_id: str, task: str, payload: dict, model_cls, attachments: list[Attachment] | None = None):
        payload.setdefault("employee", f"{self.settings.employee_name}, {self.settings.employee_dept}")
        try:
            raw = self.llm.complete(task, payload, attachments)
            parsed = model_cls.model_validate(raw)
        except (CognitionError, ValidationError) as exc:
            if isinstance(exc, ValidationError):
                logger.warning("Invalid %s output: %s", task, exc)
            else:
                logger.warning("Cognition error on %s: %s", task, exc)
            if isinstance(exc, CognitionError):
                raise
            raise CognitionError() from exc
        self.db.add_judgment(
            {
                "id": new_id(),
                "claim_id": claim_id,
                "task": task,
                "model": getattr(self.llm, "name", "llm"),
                "output_json": parsed.model_dump_json(),
                "created_at": now(),
            }
        )
        return parsed

    def _editable_claim(self) -> dict:
        claim = self._current_claim()
        if claim is None or claim["status"] == "SUBMITTED":
            return self._create_blank(with_message=False)
        return claim

    def _default_title(self) -> str:
        stamp = datetime.now().strftime("%d %b %Y")
        existing = {row["title"] for row in self.db.list_claims()}
        title = f"Claim \u2013 {stamp}"
        serial = 2
        while title in existing:
            title = f"Claim \u2013 {stamp} ({serial})"
            serial += 1
        return title

    def _create_blank(self, with_message: bool) -> dict:
        self.active_claim_id = None
        claim = self.db.create_claim(
            {
                "id": new_id(),
                "title": self._default_title(),
                "subtitle": "Drop receipts to start",
                "status": "DRAFT",
                "currency": self.settings.home_currency,
                "headline": "Drop your receipts",
                "detail": "I'll read them and ask only if something is missing.",
                "intro": "Drop photos, PDFs, or other bills.",
                "readiness": 0,
                "submittable": 0,
                "created_at": now(),
            }
        )
        if with_message:
            self._message(claim["id"], "assistant", "Drop photos, PDFs, or other bills. I'll prepare the claim and ask only if something is missing.")
        return claim

    def _message(self, claim_id: str, role: str, content: str) -> None:
        self.db.add_message({"id": new_id(), "claim_id": claim_id, "role": role, "content": content, "created_at": now()})

    def _owned_expense(self, claim_id: str, expense_id: str) -> dict | None:
        for expense in self.db.list_expenses(claim_id):
            if expense["id"] == expense_id:
                return expense
        return None

    def _ready(self, claim_id: str) -> bool:
        claim = self.db.get_claim(claim_id)
        expenses = self.db.list_expenses(claim_id)
        if claim["status"] == "SUBMITTED" or not claim["submittable"] or not expenses:
            return False
        return all(expense["status"] == "ready" and expense["merchant"] and expense["expense_date"] and expense["amount"] for expense in expenses)

    def _lock(self, claim_id: str) -> None:
        claim = self.db.get_claim(claim_id)
        self.db.mark_submitted(claim_id, now(), claim["headline"], claim["detail"])
        self.db.add_judgment(
            {
                "id": new_id(),
                "claim_id": claim_id,
                "task": "submit",
                "model": self.llm.name,
                "output_json": json.dumps({"status": "SUBMITTED"}),
                "created_at": now(),
            }
        )


def _asks_for_filled_meal_gap(judgment: Judgment, context: dict) -> bool:
    if not (str(context.get("attendees") or "").strip() or str(context.get("purpose") or "").strip()):
        return False
    text = " ".join(f"{item.field} {item.question} {item.reason}" for item in judgment.missing).lower()
    return any(token in text for token in ("attendee", "purpose", "business reason"))


def _label(payload: dict):
    from app.schemas import ExpenseLabel

    return ExpenseLabel.model_validate(payload)


def _model_expense(expense: dict) -> dict:
    return {
        "id": expense["id"],
        "merchant": expense["merchant"],
        "date": expense["expense_date"],
        "amount": float(expense["amount"]) if expense["amount"] else None,
        "currency": expense["currency"],
        "category": expense["category"],
        "category_detail": expense["category_detail"],
        "attendees": expense["attendees"],
        "purpose": expense["purpose"],
        "status": expense["status"],
        "policy_label": expense["policy_label"],
        "is_duplicate": bool(expense["is_duplicate"]),
        "duplicate_of": expense["duplicate_of"],
        "duplicate_reason": expense["duplicate_reason"],
        "duplicate_accepted": bool(expense["duplicate_accepted"]),
        "missing": json.loads(expense["missing_json"] or "[]"),
        "findings": json.loads(expense["findings_json"] or "[]"),
        "summary": expense["summary"],
        "confidence": expense["confidence"],
    }


def _question_payload(question: dict | None) -> dict | None:
    if question is None:
        return None
    return {
        "id": question["id"],
        "expense_id": question["expense_id"],
        "field": question["field"],
        "prompt": question["prompt"],
        "reason": question["reason"],
    }


def _message_payload(message: dict) -> dict:
    return {"role": message["role"], "content": message["content"]}
