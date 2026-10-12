import hmac

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.services.agent import ClaimAgent

router = APIRouter(prefix="/api")


def require_admin(request: Request, x_admin_token: str | None = Header(default=None)) -> None:
    """Admin endpoints need X-Admin-Token when ADMIN_TOKEN is configured.

    With no ADMIN_TOKEN set (local development), admin access stays open.
    """
    settings = request.app.state.agent.settings
    if not settings.admin_enabled:
        return
    if not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status_code=401, detail="Admin access requires a valid X-Admin-Token header.")


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ConfigIn(BaseModel):
    home_currency: str | None = None
    fx_rates: dict[str, float] | None = None
    max_files: int | None = Field(default=None, ge=1, le=100)
    max_file_mb: int | None = Field(default=None, ge=1, le=50)
    policy_text: str | None = None
    employee_name: str | None = Field(default=None, max_length=80)
    employee_dept: str | None = Field(default=None, max_length=80)


def get_agent(request: Request) -> ClaimAgent:
    return request.app.state.agent


@router.get("/health")
def health(agent: ClaimAgent = Depends(get_agent)) -> dict:
    return {"status": "ok", "provider": agent.llm.name}


@router.get("/claims/active")
def active_claim(agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.view()


@router.post("/claims/active/documents")
async def upload_documents(
    files: list[UploadFile] = File(...),
    agent: ClaimAgent = Depends(get_agent),
) -> dict:
    batch = []
    for item in files:
        batch.append((item.filename or "receipt", item.content_type or "", await item.read()))
    return agent.ingest_many(batch)


@router.post("/claims/active/messages")
def post_message(body: MessageIn, agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.converse(body.text)


@router.post("/claims/active/questions/{question_id}/answer")
def answer_question(question_id: str, body: MessageIn, agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.answer(question_id, body.text)


@router.post("/claims/active/submit")
def submit_claim(agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.submit()


class RenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)


@router.patch("/claims/active/title")
def rename_claim(body: RenameIn, agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.rename_claim(body.title)


@router.get("/claims")
def list_claims(agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.list_claims()


@router.post("/claims")
def new_claim(agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.new_claim()


@router.post("/claims/{claim_id}/open")
def open_claim(claim_id: str, agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.open_claim(claim_id)


@router.delete("/claims/{claim_id}")
def delete_claim(claim_id: str, agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.delete_claim(claim_id)


@router.post("/claims/{claim_id}/reopen")
def reopen_claim(claim_id: str, agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.reopen_claim(claim_id)


@router.get("/claims/active/expenses/{expense_id}")
def expense_detail(expense_id: str, agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.expense_detail(expense_id)


@router.delete("/claims/active/expenses/{expense_id}")
def delete_expense(expense_id: str, agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.delete_expense(expense_id)


class OverrideIn(BaseModel):
    reason: str = Field(min_length=5, max_length=400)


@router.post("/claims/active/expenses/{expense_id}/override")
def override_expense(expense_id: str, body: OverrideIn, agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.override_expense(expense_id, body.reason)


@router.get("/claims/active/documents/{document_id}/file")
def document_file(document_id: str, agent: ClaimAgent = Depends(get_agent)):
    from fastapi.responses import Response

    filename, media_type, data = agent.document_file(document_id)
    return Response(content=data, media_type=media_type, headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.get("/claims/active/export.csv")
def export_csv(agent: ClaimAgent = Depends(get_agent)):
    from fastapi.responses import Response

    filename, csv_text = agent.export_csv()
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/claims/active/export.json")
def export_json(fields: str | None = None, agent: ClaimAgent = Depends(get_agent)):
    """fields is a comma-separated list, e.g. ?fields=merchant,date,amount"""
    import json as json_module

    from fastapi.responses import Response

    wanted = [item.strip() for item in fields.split(",") if item.strip()] if fields else None
    filename, payload = agent.export_json(wanted)
    return Response(
        content=json_module.dumps(payload, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/expenses/search")
def search_expenses(q: str, agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.search_expenses(q)


@router.get("/conversations")
def list_conversations(q: str | None = None, agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.list_conversations(q)


@router.get("/insights")
def insights(agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.insights()


class PolicyIn(BaseModel):
    text: str = Field(min_length=20, max_length=20000)


@router.get("/admin/policy")
def get_policy(agent: ClaimAgent = Depends(get_agent)) -> dict:
    return {"text": agent.get_policy()}


@router.put("/admin/policy", dependencies=[Depends(require_admin)])
def set_policy(body: PolicyIn, agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.set_policy(body.text)


def _config_payload(agent: ClaimAgent) -> dict:
    settings = agent.settings
    return {
        "home_currency": settings.home_currency,
        "fx_rates": settings.fx_rates,
        "max_files": settings.max_files,
        "max_file_mb": settings.max_file_mb,
        "policy_text": agent.policy,
        "provider": agent.llm.name,
        "employee_name": settings.employee_name,
        "employee_dept": settings.employee_dept,
    }


@router.get("/admin/config")
def get_config(agent: ClaimAgent = Depends(get_agent)) -> dict:
    payload = _config_payload(agent)
    payload["admin_enabled"] = agent.settings.admin_enabled
    return payload


@router.put("/admin/config", dependencies=[Depends(require_admin)])
def update_config(body: ConfigIn, agent: ClaimAgent = Depends(get_agent)) -> dict:
    agent.settings.apply_overrides(body.model_dump(exclude_none=True))
    agent.settings.save_overrides()
    return _config_payload(agent)


@router.post("/admin/reset", dependencies=[Depends(require_admin)])
def reset_data(agent: ClaimAgent = Depends(get_agent)) -> dict:
    return agent.reset()


@router.post("/admin/verify")
def verify_admin(request: Request, x_admin_token: str | None = Header(default=None)) -> dict:
    require_admin(request, x_admin_token)
    return {"admin": True}
