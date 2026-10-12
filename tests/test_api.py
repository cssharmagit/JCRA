import sqlite3

from fastapi.testclient import TestClient

from app.config import APP_ROOT, Settings
from app.main import create_app
from app.services.llm import LLM


class ScriptedLLM(LLM):
    name = "script"

    def __init__(self, handlers: dict):
        self.handlers = handlers

    def complete(self, task: str, payload: dict, attachments=None) -> dict:
        handler = self.handlers[task]
        return handler(payload) if callable(handler) else handler


def settings(tmp_path, seed: bool = False, admin_token: str = "") -> Settings:
    return Settings(
        database_path=tmp_path / "expense.db",
        files_dir=tmp_path / "files",
        policy_path=APP_ROOT / "seed" / "policy.md",
        seed_dir=APP_ROOT / "seed" / "receipts",
        seed_demo=seed,
        llm_provider="mock",
        admin_token=admin_token,
    )


def test_admin_endpoints_require_token_when_configured(tmp_path):
    app = create_app(settings(tmp_path, admin_token="secret-token"))
    with TestClient(app) as client:
        assert client.get("/api/admin/config").status_code == 200  # reading stays open
        assert client.put("/api/admin/policy", json={"text": "Meals over $10 need a reason."}).status_code == 401
        assert client.post("/api/admin/reset").status_code == 401
        assert client.post("/api/admin/verify", headers={"X-Admin-Token": "wrong"}).status_code == 401
        ok = client.put(
            "/api/admin/policy",
            json={"text": "Meals over $10 need a reason."},
            headers={"X-Admin-Token": "secret-token"},
        )
        assert ok.status_code == 200
        assert client.post("/api/admin/verify", headers={"X-Admin-Token": "secret-token"}).json() == {"admin": True}


def test_demo_claim_asks_only_for_the_dinner_then_submits(tmp_path):
    app = create_app(settings(tmp_path, seed=True))
    with TestClient(app) as client:
        claim = client.get("/api/claims/active").json()
        assert claim["title"] == "March business trip"
        assert claim["subtitle"] == "San Francisco customer visit · Mar 10–14, 2025"
        assert claim["total"] == "$1,060.00"
        assert claim["readiness"] == 80
        assert claim["headline"] == "Almost ready to submit"
        assert claim["detail"] == "I checked 5 receipts. One detail needs your review."
        assert claim["summary"] == {"processed": 5, "ready": 4, "needsReview": 1, "duplicates": 0}
        assert claim["openQuestion"]["prompt"] == "Who attended the dinner at Nopa?"
        assert [item["merchant"] for item in claim["expenses"]] == [
            "Blue Bottle Coffee",
            "United Airlines",
            "The Hoxton",
            "Lyft",
            "Nopa",
        ]
        blocked = client.post("/api/claims/active/submit")
        assert blocked.status_code == 409

        answered = client.post(
            f"/api/claims/active/questions/{claim['openQuestion']['id']}/answer",
            json={"text": "Alex Morgan and Priya Shah from Acme"},
        ).json()
        assert answered["submittable"] is True
        assert answered["readiness"] == 100
        assert answered["openQuestion"] is None
        assert answered["headline"] == "Everything looks good"

        submitted = client.post("/api/claims/active/submit").json()
        assert submitted["status"] == "SUBMITTED"
        assert client.post("/api/claims/active/submit").status_code == 409

    tasks = [row[0] for row in sqlite3.connect(tmp_path / "expense.db").execute("SELECT task FROM judgments")]
    assert "understand_document" in tasks
    assert "judge_expense" in tasks
    assert "plan_claim" in tasks
    assert "interpret_turn" in tasks
    assert "submit" in tasks


def test_new_text_receipt_asks_for_purpose_then_starts_fresh_after_submit(tmp_path):
    app = create_app(settings(tmp_path, seed=False))
    with TestClient(app) as client:
        first = client.post(
            "/api/claims/active/documents",
            files=[("files", ("cafe.txt", b"Merchant: Corner Cafe\nDate: 2025-04-02\nAmount: 24.00\nCurrency: USD\n", "text/plain"))],
        ).json()
        assert first["summary"]["processed"] == 1
        assert first["openQuestion"]["field"] == "purpose"
        assert first["submittable"] is False

        same = client.post(
            "/api/claims/active/documents",
            files=[("files", ("cafe-copy.txt", b"Merchant: Corner Cafe\nDate: 2025-04-02\nAmount: 24.00\nCurrency: USD\n", "text/plain"))],
        ).json()
        assert same["summary"]["processed"] == 1
        assert "same file" in same["notice"]

        ready = client.post(
            f"/api/claims/active/questions/{first['openQuestion']['id']}/answer",
            json={"text": "Coffee with a customer"},
        ).json()
        assert ready["submittable"] is True
        submitted = client.post("/api/claims/active/submit").json()
        assert submitted["status"] == "SUBMITTED"

        nxt = client.post(
            "/api/claims/active/documents",
            files=[("files", ("train.txt", b"Merchant: Caltrain\nDate: 2025-05-01\nAmount: 12.50\nCurrency: USD\n", "text/plain"))],
        ).json()
        assert nxt["status"] == "DRAFT"
        assert nxt["summary"]["processed"] == 1
        assert nxt["expenses"][0]["merchant"] == "Caltrain"


def test_asking_about_policy_does_not_clear_the_open_question(tmp_path):
    app = create_app(settings(tmp_path, seed=True))
    with TestClient(app) as client:
        before = client.get("/api/claims/active").json()
        after = client.post("/api/claims/active/messages", json={"text": "What does the meal policy cover?"}).json()
        assert after["submittable"] is False
        assert after["openQuestion"]["prompt"] == before["openQuestion"]["prompt"]
        assert "150" in after["messages"][-1]["content"]
        assert after["expenses"][-1]["status"] == "attention"


def test_similar_receipt_is_flagged_as_duplicate(tmp_path):
    app = create_app(settings(tmp_path, seed=False))
    original = b"Merchant: Corner Cafe\nDate: 2025-04-02\nAmount: 24.00\nCurrency: USD\n"
    variant = original + b"Printed copy\n"
    with TestClient(app) as client:
        client.post("/api/claims/active/documents", files=[("files", ("a.txt", original, "text/plain"))])
        claim = client.post("/api/claims/active/documents", files=[("files", ("b.txt", variant, "text/plain"))]).json()
        assert claim["summary"]["duplicates"] == 1
        assert claim["submittable"] is False
        assert any(item["policyLabel"] == "Possible duplicate" for item in claim["expenses"])


def test_model_cannot_mark_a_claim_ready_without_an_amount(tmp_path):
    def plan(_payload):
        return {
            "title": "Expenses",
            "subtitle": "Draft",
            "readiness": 1,
            "submittable": True,
            "headline": "Everything looks good",
            "detail": "Ready",
            "intro": "Done",
            "note": "Ready",
            "next_question": None,
            "labels": [],
        }

    llm = ScriptedLLM(
        {
            "understand_document": {
                "merchant": "Cafe",
                "date": "2025-04-01",
                "amount": None,
                "currency": "USD",
                "summary": "Unreadable total",
                "confidence": 0.4,
                "uncertainties": ["amount"],
            },
            "judge_expense": {
                "category": "Other",
                "policy_status": "ready",
                "policy_label": "Policy checked",
                "missing": [],
                "merchant": "Cafe",
                "date": "2025-04-01",
                "amount": None,
                "currency": "USD",
            },
            "plan_claim": plan,
        }
    )
    app = create_app(settings(tmp_path, seed=False), llm)
    with TestClient(app) as client:
        claim = client.post(
            "/api/claims/active/documents",
            files=[("files", ("cafe.txt", b"unreadable", "text/plain"))],
        ).json()
        assert claim["submittable"] is False
        assert claim["expenses"][0]["amount"] == "—"
        assert claim["openQuestion"]["field"] == "amount"
        assert client.post("/api/claims/active/submit").status_code == 409


def test_unsupported_file_is_rejected(tmp_path):
    app = create_app(settings(tmp_path, seed=False))
    with TestClient(app) as client:
        response = client.post("/api/claims/active/documents", files=[("files", ("notes.exe", b"MZ", "application/octet-stream"))])
        assert response.status_code == 415
