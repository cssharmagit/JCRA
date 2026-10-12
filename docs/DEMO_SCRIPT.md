# JRCA demo video — recording script

Target: 6–8 minutes, 1080p screen capture with narration. Upload to YouTube as **Unlisted** and paste the link into README.md and TECHNICAL_DESIGN.md §5.

## Preparation

1. Reset data for a clean start: `Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/admin/reset` (needs `X-Admin-Token` header if `ADMIN_TOKEN` is set).
2. Have `tests/reciept-samples/` open in Explorer (food and cab.pdf, hotelbill.jpg, expenses.pdf).
3. Browser at http://localhost:8443, hard-refreshed, sidebar visible.
4. Recording tool: Windows Game Bar (`Win+G`), OBS Studio, or Clipchamp screen recorder.

## Script

### Scene 1 — The problem (30s, title slide or voiceover on the empty app)
> "Expense claims mean re-typing receipts, reading policy documents, and chasing missing details. JRCA — the Jio Reimbursement Claims Assistant — replaces all of that with one conversation. You drop receipts; an AI agent does the rest."

### Scene 2 — Multi-receipt magic (90s)
- Drag **food and cab.pdf** onto the drop zone.
- Point at the progress banner ("Reading file 1 of 1 … each receipt is checked against policy") and the **Stop after this file** button.
- When done: "One PDF — twenty separate receipts. The agent split them, read each merchant and amount, inferred the currency as rupees, and checked every one against company policy."
- Show the tabs: All / Needs attention / Ready, and the **Table** view toggle.

### Scene 3 — Evidence and detail (45s)
- Click any expense row → detail drawer.
- "Every number is traceable — the original file, the extracted text, the model's confidence, and exactly what policy found."
- Click **Open original PDF** briefly.

### Scene 4 — The one question (45s)
- Point at the "Needs your input" card: "The agent never gives you a form. It asks the single most important question."
- Type the answer (e.g. a date correction) and show the row re-judged to Ready.

### Scene 5 — Chat does everything (90s)
Type these one after another in the chat:
1. `Call this claim Mumbai field visit — October`  → title changes, uniqueness enforced
2. `Find all receipts above 300 rupees` → listed with count
3. `What is my total hotel spend across all my claims?` → cross-claim answer naming each claim
4. `Export this claim as JSON with only merchant, date and amount` → Download JSON link (custom fields)
5. `Focus the chat` → layout obeys; `show the expenses` → back

### Scene 6 — Duplicates across claims (45s)
- Upload **hotelbill.jpg**, submit the claim.
- Start a new claim, upload **hotelbill.jpg again**.
- "It caught the duplicate — and it names the other claim it was already submitted on." Show the Keep / Remove duplicate buttons.

### Scene 7 — Override with audit (40s)
- Open the flagged expense → **Approve with override…** → type a reason.
- "Human judgment can overrule policy — but only with a recorded reason, and it's written to an immutable audit log."

### Scene 8 — Submit, lock, reopen (40s)
- Submit the claim; show the locked state.
- Type: `I submitted this by mistake — please reopen it` → draft again. "Mistakes are recoverable, and every reopen is audited."

### Scene 9 — Admin and policy-as-prose (45s)
- Settings → Unlock admin (token) → **Edit policy** → change the meal limit → Save.
- "The policy is plain language, interpreted by the model. Change the text, and the very next receipt follows the new rule. No code release. And only admins can touch it."

### Scene 10 — Close (30s, architecture slide from TECHNICAL_DESIGN.md §2.1)
> "FastAPI, React, SQLite, and Claude Sonnet — with a strict split: the model does the judgment, deterministic code guards the money. JRCA v0.1.0."

## Publishing

1. Trim in Clipchamp; add title card "JRCA — Jio Reimbursement Claims Assistant".
2. YouTube Studio → Upload → visibility **Unlisted** → copy link.
3. Paste the link into README.md and docs/TECHNICAL_DESIGN.md §5.
