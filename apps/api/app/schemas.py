from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def empty_as_false(value):
    if value is None or value == "":
        return False
    return value


class CognitiveModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def drop_nulls_for_defaulted_strings(cls, value):
        if isinstance(value, dict):
            for name, field in cls.model_fields.items():
                if value.get(name) is None and isinstance(field.default, (str, float, int, bool)):
                    value.pop(name, None)
        return value


class Understanding(CognitiveModel):
    merchant: str | None = None
    date: str | None = None
    amount: float | None = None
    currency: str = "USD"
    summary: str = ""
    confidence: float = 0
    uncertainties: list[str] = Field(default_factory=list)

    @field_validator("amount")
    @classmethod
    def non_negative(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("amount cannot be negative")
        return value

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, value: float) -> float:
        return max(0.0, min(1.0, value))


class DocumentReading(CognitiveModel):
    receipts: list[Understanding] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def wrap_single_reading(cls, value):
        if isinstance(value, dict) and "receipts" not in value:
            return {"receipts": [value]}
        return value


class Finding(CognitiveModel):
    severity: Literal["blocker", "warning", "info"] = "info"
    code: str = ""
    message: str = ""


class MissingItem(CognitiveModel):
    field: str
    question: str
    reason: str


class Judgment(CognitiveModel):
    category: str = "Other"
    category_detail: str = ""
    policy_status: Literal["ready", "attention"] = "attention"
    policy_label: str = "Add details"
    findings: list[Finding] = Field(default_factory=list)
    is_duplicate: bool = False

    @field_validator("is_duplicate", mode="before")
    @classmethod
    def duplicate_flag(cls, value):
        return empty_as_false(value)
    duplicate_of: str | None = None
    duplicate_reason: str = ""
    missing: list[MissingItem] = Field(default_factory=list)
    merchant: str | None = None
    date: str | None = None
    amount: float | None = None
    currency: str = "USD"

    @field_validator("amount")
    @classmethod
    def non_negative(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("amount cannot be negative")
        return value


class NextQuestion(CognitiveModel):
    expense_id: str
    field: str
    prompt: str
    reason: str


class ExpenseLabel(CognitiveModel):
    expense_id: str
    status: Literal["ready", "attention"]
    policy_label: str


class Plan(CognitiveModel):
    title: str
    subtitle: str
    readiness: float = 0
    submittable: bool = False

    @field_validator("submittable", mode="before")
    @classmethod
    def submit_flag(cls, value):
        return empty_as_false(value)
    headline: str
    detail: str
    intro: str
    note: str
    next_question: NextQuestion | None = None
    labels: list[ExpenseLabel] = Field(default_factory=list)

    @field_validator("readiness")
    @classmethod
    def clamp_readiness(cls, value: float) -> float:
        return max(0.0, min(1.0, value))


class FieldUpdate(CognitiveModel):
    expense_id: str
    attendees: str | None = None
    purpose: str | None = None
    merchant: str | None = None
    date: str | None = None
    amount: float | None = None
    category: str | None = None
    category_detail: str | None = None
    duplicate_accepted: bool | None = None
    remove: bool = False

    @field_validator("remove", mode="before")
    @classmethod
    def remove_flag(cls, value):
        return empty_as_false(value)

    @field_validator("amount")
    @classmethod
    def non_negative(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("amount cannot be negative")
        return value


class Turn(CognitiveModel):
    reply: str
    updates: list[FieldUpdate] = Field(default_factory=list)
    wants_submit: bool = False
    rename_claim_to: str | None = None
    start_new_claim: bool = False
    wants_export: bool = False
    export_format: str | None = None
    export_fields: list[str] = Field(default_factory=list)
    set_policy_to: str | None = None
    ui_action: str | None = None

    @field_validator("wants_submit", "start_new_claim", "wants_export", mode="before")
    @classmethod
    def submit_request(cls, value):
        return empty_as_false(value)
