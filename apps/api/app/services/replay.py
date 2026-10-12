"""Offline stand-in for the cognitive model.

Recorded readings for the March trip, plus a labeled-text reader for other
plain receipts. Live Gemini or OpenAI calls replace this class entirely.
"""

from __future__ import annotations

import copy
import re
from datetime import datetime

from app.services.llm import Attachment, LLM

DEMO_DOCS = {
    "blue bottle": {
        "merchant": "Blue Bottle Coffee",
        "date": "2025-03-14",
        "amount": 18.40,
        "currency": "USD",
        "summary": "Coffee at the Ferry Building",
        "confidence": 0.99,
        "uncertainties": [],
    },
    "united airlines": {
        "merchant": "United Airlines",
        "date": "2025-03-12",
        "amount": 486.20,
        "currency": "USD",
        "summary": "Economy fare to San Francisco",
        "confidence": 0.99,
        "uncertainties": [],
    },
    "hoxton": {
        "merchant": "The Hoxton",
        "date": "2025-03-12",
        "amount": 328.00,
        "currency": "USD",
        "summary": "One night in San Francisco",
        "confidence": 0.97,
        "uncertainties": [],
    },
    "lyft": {
        "merchant": "Lyft",
        "date": "2025-03-11",
        "amount": 42.80,
        "currency": "USD",
        "summary": "Rideshare in San Francisco",
        "confidence": 0.99,
        "uncertainties": [],
    },
    "nopa": {
        "merchant": "Nopa",
        "date": "2025-03-10",
        "amount": 184.60,
        "currency": "USD",
        "summary": "Dinner in San Francisco",
        "confidence": 0.98,
        "uncertainties": [],
    },
}

DEMO_JUDGMENTS = {
    "blue bottle": {
        "category": "Meals",
        "category_detail": "",
        "policy_status": "ready",
        "policy_label": "Policy checked",
        "findings": [],
        "is_duplicate": False,
        "duplicate_of": None,
        "duplicate_reason": "",
        "missing": [],
        "clears_when": [],
    },
    "united airlines": {
        "category": "Travel",
        "category_detail": "",
        "policy_status": "ready",
        "policy_label": "Policy checked",
        "findings": [],
        "is_duplicate": False,
        "duplicate_of": None,
        "duplicate_reason": "",
        "missing": [],
        "clears_when": [],
    },
    "hoxton": {
        "category": "Lodging",
        "category_detail": "",
        "policy_status": "ready",
        "policy_label": "Policy checked",
        "findings": [],
        "is_duplicate": False,
        "duplicate_of": None,
        "duplicate_reason": "",
        "missing": [],
        "clears_when": [],
    },
    "lyft": {
        "category": "Ground transport",
        "category_detail": "",
        "policy_status": "ready",
        "policy_label": "Policy checked",
        "findings": [],
        "is_duplicate": False,
        "duplicate_of": None,
        "duplicate_reason": "",
        "missing": [],
        "clears_when": [],
    },
    "nopa": {
        "category": "Meals",
        "category_detail": "Client dinner",
        "policy_status": "attention",
        "policy_label": "Add details",
        "findings": [
            {
                "severity": "blocker",
                "code": "meal-attendees",
                "message": "Meals over $150 require attendees or a business purpose.",
            }
        ],
        "is_duplicate": False,
        "duplicate_of": None,
        "duplicate_reason": "",
        "missing": [
            {
                "field": "attendees",
                "question": "Who attended the dinner at Nopa?",
                "reason": "Meals over $150 require attendees or a business purpose.",
            }
        ],
        "clears_when": ["attendees", "purpose"],
    },
}

DEMO_KEYS = ("blue bottle", "united airlines", "hoxton", "lyft", "nopa")
LABELS = {
    "merchant": "merchant",
    "vendor": "merchant",
    "date": "date",
    "amount": "amount",
    "total": "amount",
    "currency": "currency",
}


class ReplayLLM(LLM):
    name = "replay"

    def complete(self, task: str, payload: dict, attachments: list[Attachment] | None = None) -> dict:
        if task == "understand_document":
            return self._understand(payload, attachments or [])
        if task == "judge_expense":
            return self._judge(payload)
        if task == "plan_claim":
            return self._plan(payload)
        if task == "interpret_turn":
            return self._interpret(payload)
        raise KeyError(task)

    def _understand(self, payload: dict, attachments: list[Attachment]) -> dict:
        text = f"{payload.get('filename', '')}\n{payload.get('text', '')}"
        key = _demo_key(text)
        if key:
            return copy.deepcopy(DEMO_DOCS[key])
        labeled = _labeled(payload.get("text") or "")
        if labeled:
            amount = _number(labeled.get("amount"))
            return {
                "merchant": labeled.get("merchant"),
                "date": _iso_date(labeled.get("date")),
                "amount": amount,
                "currency": (labeled.get("currency") or "USD").upper(),
                "summary": (payload.get("text") or "")[:240],
                "confidence": 0.9 if amount is not None and labeled.get("merchant") else 0.45,
                "uncertainties": [],
            }
        if attachments:
            return {
                "merchant": None,
                "date": None,
                "amount": None,
                "currency": "USD",
                "summary": "",
                "confidence": 0,
                "uncertainties": ["This file needs a vision model. Set GEMINI_API_KEY or OPENAI_API_KEY."],
            }
        return {
            "merchant": None,
            "date": None,
            "amount": None,
            "currency": "USD",
            "summary": (payload.get("text") or "")[:240],
            "confidence": 0.2,
            "uncertainties": ["I could not find a merchant, date, and amount."],
        }

    def _judge(self, payload: dict) -> dict:
        extraction = payload.get("extraction") or {}
        context = payload.get("employee_context") or {}
        key = _demo_key(f"{extraction.get('merchant') or ''} {extraction.get('summary') or ''}")
        if key:
            base = copy.deepcopy(DEMO_JUDGMENTS[key])
        else:
            base = _generic_judgment(extraction, context)
        clears = base.pop("clears_when", [])
        if clears and any(str(context.get(field) or "").strip() for field in clears):
            base["missing"] = []
            base["findings"] = []
            base["policy_status"] = "ready"
            base["policy_label"] = "Policy checked"
        base["merchant"] = extraction.get("merchant")
        base["date"] = extraction.get("date")
        base["amount"] = extraction.get("amount")
        base["currency"] = extraction.get("currency") or "USD"
        if not context.get("duplicate_accepted"):
            duplicate = _same_charge(extraction, payload.get("candidates") or [])
            if duplicate:
                base["is_duplicate"] = True
                base["duplicate_of"] = duplicate
                base["duplicate_reason"] = "Same merchant, date, and amount as another receipt on this claim."
                base["policy_status"] = "attention"
                base["policy_label"] = "Possible duplicate"
                base["missing"] = [
                    {
                        "field": "duplicate",
                        "question": "This looks like the same charge I already have. Is it a separate expense?",
                        "reason": base["duplicate_reason"],
                    }
                ]
        else:
            base["is_duplicate"] = False
            base["duplicate_of"] = None
        if base["policy_status"] == "attention" and not base["missing"]:
            base["missing"] = [
                {
                    "field": "purpose",
                    "question": "What was this expense for?",
                    "reason": "I still need a business reason before this can be submitted.",
                }
            ]
        return base

    def _plan(self, payload: dict) -> dict:
        expenses = payload.get("expenses") or []
        attention = [item for item in expenses if item.get("status") == "attention" or item.get("missing")]
        count = len(expenses)
        ready = count - len(attention)
        submittable = count > 0 and not attention
        demo = _demo_set(expenses) or payload.get("current_title") == "March business trip"
        if demo and count:
            title = "March business trip"
            subtitle = "San Francisco customer visit · Mar 10–14, 2025"
        elif count:
            title = payload.get("current_title") if payload.get("current_title") not in (None, "", "New reimbursement") else "Expenses"
            subtitle = _span(expenses)
        else:
            title = "New reimbursement"
            subtitle = "Drop receipts to start"
        question = None
        if attention:
            missing = attention[0].get("missing") or []
            if missing:
                question = {
                    "expense_id": attention[0]["id"],
                    "field": missing[0]["field"],
                    "prompt": missing[0]["question"],
                    "reason": missing[0]["reason"],
                }
        if count == 0:
            headline, detail, note = (
                "Drop your receipts",
                "I'll read them and ask only if something is missing.",
                "Drop photos, PDFs, or other bills and I'll prepare the claim.",
            )
        elif submittable:
            headline = "Everything looks good"
            detail = f"All {count} expenses passed your company policy." if count != 1 else "This expense passed your company policy."
            note = "Nice — your claim is complete and ready to submit."
        elif len(attention) == 1:
            headline = "Almost ready to submit"
            detail = f"I checked {count} receipts. One detail needs your review."
            note = "I found one thing to confirm before this claim is ready."
        else:
            headline = "A few details need you"
            detail = f"I checked {count} receipts. {len(attention)} details need your review."
            note = "A few details still need you before this can be submitted."
        labels = []
        attention_ids = {item["id"] for item in attention}
        for item in expenses:
            if item["id"] in attention_ids:
                labels.append(
                    {
                        "expense_id": item["id"],
                        "status": "attention",
                        "policy_label": item.get("policy_label") or "Add details",
                    }
                )
            else:
                labels.append({"expense_id": item["id"], "status": "ready", "policy_label": "Policy checked"})
        return {
            "title": title,
            "subtitle": subtitle,
            "readiness": 1 if submittable else (ready / count if count else 0),
            "submittable": submittable,
            "headline": headline,
            "detail": detail,
            "intro": "I extracted the details, matched categories, and checked company policy."
            if count
            else "Drop photos, PDFs, or other bills.",
            "note": note,
            "next_question": question,
            "labels": labels,
        }

    def _interpret(self, payload: dict) -> dict:
        text = str(payload.get("user_text") or "").strip()
        question = payload.get("open_question")
        lowered = text.lower()
        inquiry = _is_inquiry(lowered)
        submit_only = bool(re.fullmatch(r"(please\s+)?(submit|submit the claim|submit it)[.!]?", lowered))
        wants_submit = not inquiry and (submit_only or (bool(re.search(r"\bsubmit\b", lowered)) and not question))
        updates = []
        if question and not submit_only and not inquiry:
            update: dict = {"expense_id": question["expense_id"]}
            field = question.get("field")
            if field == "purpose":
                update["purpose"] = text
            elif field == "merchant":
                update["merchant"] = text
            elif field == "date":
                update["date"] = _iso_date(text) or text
            elif field == "amount":
                number = _number(text)
                if number is not None:
                    update["amount"] = number
            elif field == "duplicate":
                if re.search(r"\b(delete|remove|drop)\b", lowered):
                    update["remove"] = True
                else:
                    update["duplicate_accepted"] = True
            else:
                update["attendees"] = text
            updates.append(update)
        if inquiry:
            reply = _answer_inquiry(lowered, payload.get("expenses") or [])
        elif wants_submit:
            reply = "I'll submit it if everything needed is already here."
        elif updates:
            reply = "Thanks — I'll use that and recheck the claim."
        else:
            reply = "I can update a receipt, answer the open question, or submit once the claim is ready."
        return {"reply": reply, "updates": updates, "wants_submit": wants_submit}


def _is_inquiry(lowered: str) -> bool:
    return lowered.startswith(("what ", "why ", "how ", "explain ", "show ", "tell "))


def _answer_inquiry(lowered: str, expenses: list[dict]) -> str:
    if "total" in lowered:
        amounts = [float(item["amount"]) for item in expenses if item.get("amount") is not None]
        total = round(sum(amounts), 2) if amounts else 0
        return f"The claim total is the sum of the receipt amounts I read: ${total:,.2f}."
    if "policy" in lowered or "meal" in lowered:
        return "Meals over $150 need the names of the people who attended, or a business purpose. Meals at or under $150 do not."
    return "Ask me about the policy, the total, or the open question on this claim."


def _demo_key(text: str) -> str | None:
    lowered = text.lower()
    for key in DEMO_KEYS:
        if key in lowered:
            return key
    return None


def _demo_set(expenses: list[dict]) -> bool:
    names = " ".join((item.get("merchant") or "") for item in expenses).lower()
    needed = ("blue bottle", "united", "hoxton", "lyft", "nopa")
    return all(token in names for token in needed)


def _labeled(text: str) -> dict:
    found = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        mapped = LABELS.get(key.strip().lower())
        if mapped and value.strip():
            found[mapped] = value.strip()
    return found


def _number(value) -> float | None:
    if value is None:
        return None
    match = re.search(r"\d+(?:\.\d{1,2})?", str(value).replace(",", ""))
    if not match:
        return None
    return float(match.group(0))


def _iso_date(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    for pattern in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else None


def _generic_judgment(extraction: dict, context: dict) -> dict:
    missing = []
    if extraction.get("amount") is None:
        missing.append(
            {
                "field": "amount",
                "question": "What was the total on this receipt?",
                "reason": "I couldn't read an amount.",
            }
        )
    elif not extraction.get("merchant"):
        missing.append(
            {
                "field": "merchant",
                "question": "Which merchant is this receipt from?",
                "reason": "I couldn't read the merchant.",
            }
        )
    elif not extraction.get("date"):
        missing.append(
            {
                "field": "date",
                "question": "What date is on this receipt?",
                "reason": "I couldn't read the date.",
            }
        )
    elif not str(context.get("purpose") or "").strip():
        missing.append(
            {
                "field": "purpose",
                "question": "What was this expense for?",
                "reason": "I need a short business reason before this can be submitted.",
            }
        )
    ready = not missing
    return {
        "category": "Other",
        "category_detail": "",
        "policy_status": "ready" if ready else "attention",
        "policy_label": "Policy checked" if ready else "Add details",
        "findings": [],
        "is_duplicate": False,
        "duplicate_of": None,
        "duplicate_reason": "",
        "missing": missing,
        "clears_when": ["purpose"] if any(item["field"] == "purpose" for item in missing) else [],
    }


def _same_charge(extraction: dict, candidates: list[dict]) -> str | None:
    merchant = (extraction.get("merchant") or "").strip().lower()
    amount = extraction.get("amount")
    date = extraction.get("date")
    if not merchant or amount is None or not date:
        return None
    for candidate in candidates:
        same_name = merchant == (candidate.get("merchant") or "").strip().lower()
        same_day = date == candidate.get("date")
        try:
            close = abs(float(amount) - float(candidate["amount"])) <= 1
        except (TypeError, ValueError):
            close = False
        if same_name and same_day and close:
            return candidate.get("id")
    return None


def _span(expenses: list[dict]) -> str:
    parsed = []
    for item in expenses:
        iso = _iso_date(item.get("date"))
        if iso and re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso):
            parsed.append(datetime.strptime(iso, "%Y-%m-%d"))
    if not parsed:
        return "Draft claim"
    start, end = min(parsed), max(parsed)
    if start == end:
        return f"{start.strftime('%b')} {start.day}, {start.year}"
    return f"{start.strftime('%b')} {start.day}–{end.strftime('%b')} {end.day}, {end.year}"
