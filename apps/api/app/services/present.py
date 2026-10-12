from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

MARKS = {"the hoxton": "H", "lyft": "Ly", "nopa": "N"}
TONES = {
    "blue bottle coffee": "blue",
    "united airlines": "navy",
    "the hoxton": "cream",
    "lyft": "pink",
    "nopa": "orange",
}
TONE_CYCLE = ["blue", "navy", "cream", "pink", "orange"]


def present(
    claim: dict,
    expenses: list[dict],
    question: dict | None,
    messages: list[dict],
    provider: str,
    notice: str | None = None,
    home_currency: str | None = None,
    fx_rates: dict | None = None,
    employee_name: str = "Alex Morgan",
    employee_dept: str = "Product Design",
) -> dict:
    home = (home_currency or claim["currency"] or "USD").upper()
    rates = fx_rates or {}
    currencies = {(expense["currency"] or home).upper() for expense in expenses if expense.get("amount")}
    total = Decimal("0")
    unconverted = set()
    for expense in expenses:
        if not expense.get("amount"):
            continue
        amount = Decimal(expense["amount"])
        code = (expense.get("currency") or home).upper()
        if code == home:
            total += amount
        elif code in rates:
            total += amount * Decimal(str(rates[code]))
        else:
            unconverted.add(code)
    total = total.quantize(Decimal("0.01"))
    if unconverted:
        total_note = f"No conversion rate configured for {', '.join(sorted(unconverted))}; those amounts are excluded from the total."
    elif currencies - {home}:
        converted = ", ".join(sorted(currencies - {home}))
        total_note = f"Includes {converted} amounts converted to {home} at configured rates."
    else:
        total_note = None
    ready = sum(1 for expense in expenses if expense["status"] == "ready")
    attention = sum(1 for expense in expenses if expense["status"] == "attention")
    duplicates = sum(1 for expense in expenses if expense["is_duplicate"] and not expense["duplicate_accepted"])
    preview_source = next((expense for expense in expenses if expense["status"] == "attention"), None)
    if preview_source is None and expenses:
        preview_source = expenses[-1]
    return {
        "id": claim["id"],
        "title": claim["title"].strip() or "Expenses",
        "subtitle": claim["subtitle"].strip() or "Draft claim",
        "status": claim["status"],
        "currency": home,
        "total": _money(total, home),
        "totalNote": total_note,
        "readiness": round(float(claim["readiness"]) * 100),
        "headline": claim["headline"],
        "detail": claim["detail"],
        "intro": claim["intro"],
        "submittable": bool(claim["submittable"]) and claim["status"] != "SUBMITTED",
        "openQuestion": None
        if question is None
        else {
            "id": question["id"],
            "expenseId": question["expense_id"],
            "field": question["field"],
            "prompt": question["prompt"],
            "reason": question["reason"],
        },
        "expenses": [_expense(expense) for expense in expenses],
        "summary": {
            "processed": len(expenses),
            "ready": ready,
            "needsReview": attention,
            "duplicates": duplicates,
        },
        "messages": [{"id": message["id"], "role": message["role"], "content": message["content"]} for message in messages],
        "preview": _preview(preview_source),
        "notice": notice,
        "provider": provider,
        "employee": {"name": employee_name, "dept": employee_dept},
    }


def _expense(expense: dict) -> dict:
    merchant = expense["merchant"] or "Unread receipt"
    detail = expense["category_detail"] or expense["category"] or "Expense"
    return {
        "id": expense["id"],
        "merchant": merchant,
        "meta": f"{_date(expense['expense_date'])} · {detail}",
        "amount": _money(Decimal(expense["amount"]), expense["currency"] or "USD") if expense["amount"] else "—",
        "mark": _mark(merchant),
        "tone": TONES.get(merchant.lower(), TONE_CYCLE[sum(merchant.encode()) % len(TONE_CYCLE)]),
        "status": expense["status"],
        "policyLabel": expense["policy_label"],
    }


def _preview(expense: dict | None) -> dict | None:
    if expense is None or not expense.get("filename"):
        return None
    confidence = expense.get("confidence")
    merchant = expense["merchant"] or "Receipt"
    amount = _money(Decimal(expense["amount"]), expense["currency"] or "USD") if expense.get("amount") else "—"
    return {
        "filename": expense["filename"],
        "confidence": f"{round(float(confidence) * 100)}% read" if confidence is not None else "Unread",
        "merchant": merchant,
        "amount": amount,
    }


SYMBOLS = {"USD": "$", "INR": "\u20b9", "EUR": "\u20ac", "GBP": "\u00a3"}


def _money(amount: Decimal, currency: str) -> str:
    symbol = SYMBOLS.get(currency.upper())
    return f"{symbol}{amount:,.2f}" if symbol else f"{currency} {amount:,.2f}"


def _date(value: str | None) -> str:
    if not value:
        return "Date missing"
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return value
    return f"{parsed.strftime('%b')} {parsed.day}"


def _mark(merchant: str) -> str:
    if merchant.lower() in MARKS:
        return MARKS[merchant.lower()]
    cleaned = re.sub(r"^(the|a|an)\s+", "", merchant.strip(), flags=re.I)
    parts = cleaned.split()
    if not parts:
        return "?"
    if len(parts) == 1:
        word = parts[0]
        return word[0].upper() if len(word) <= 5 else word[:2].capitalize()
    return (parts[0][0] + parts[1][0]).upper()
