---
title: JRCA
emoji: 🧾
colorFrom: green
colorTo: gray
sdk: docker
app_port: 8000
pinned: false
---

# JRCA — Jio Reimbursement Claims Assistant

An AI agent that turns piles of receipts into submission-ready reimbursement claims. Drop photos, PDFs (including files containing many receipts), or text bills — the agent reads them with Claude vision, categorizes each expense, checks the company policy (written as prose, not code), flags duplicates within and across claims, and asks only for what is still missing. Everything the screen offers can also be done through chat.

- **Technical design, architecture diagrams, setup, assumptions**: [docs/TECHNICAL_DESIGN.md](docs/TECHNICAL_DESIGN.md)
- **Original design rationale**: [docs/DESIGN.md](docs/DESIGN.md)
- **Demo video**: https://youtu.be/NAwRPTj_b50

## Run

Backend, from this folder:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r apps\api\requirements.txt
copy .env.example .env    # add your ANTHROPIC_API_KEY
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

With no key, the app uses an offline replay of a demo trip so the screen still works end to end.

Frontend (Node ≥ 20.19 or 22.x):

```powershell
cd "Expense Reimbursement Assistant"
npm install
npm run dev
```

Open http://localhost:8443 — it proxies `/api` to `http://127.0.0.1:8000`.

## Feature highlights

- Multi-receipt batch extraction (one PDF with 70+ receipts becomes 70+ expense rows)
- Policy-as-prose: admins edit the policy text; the next receipt follows it — no code change
- Chat does everything: fix fields, rename, export CSV/JSON (custom fields), query spend across claims, reopen a mistakenly submitted claim, change the layout
- Multi-currency totals with configurable FX rates (₹ home currency for Jio)
- Deterministic guardrails: no submit with missing merchant/date/amount, locked after submit, audited human overrides and reopens
- Admin module: token-protected policy/config/reset (`ADMIN_TOKEN` + `X-Admin-Token` header)
- Views: Overview, Expenses, Claims, Insights (spend by category/claim), Settings
- Conversation history with full-text search across all claims

## Tests

```powershell
.venv\Scripts\python.exe -m pytest    # 13 tests, no API key needed
```

## Versioning

`v0.1.0` is the first working prototype. Minor bumps per feature round; `v1.0.0` when it reaches real users.
