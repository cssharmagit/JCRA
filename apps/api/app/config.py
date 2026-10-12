from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FX_RATES = {"INR": 0.012, "EUR": 1.08, "GBP": 1.27}
DEFAULT_MAX_FILES = 10
DEFAULT_MAX_FILE_MB = 8


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Settings:
    database_path: Path
    files_dir: Path
    policy_path: Path
    seed_dir: Path
    llm_provider: str = "auto"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    seed_demo: bool = True
    policy_text: str | None = None
    llm: object | None = None
    home_currency: str = "USD"
    fx_rates: dict = field(default_factory=lambda: dict(DEFAULT_FX_RATES))
    max_files: int = DEFAULT_MAX_FILES
    max_file_mb: int = DEFAULT_MAX_FILE_MB
    employee_name: str = "Chandra Sharma"
    employee_dept: str = "Engineering"
    admin_token: str = ""

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_token)

    @property
    def config_path(self) -> Path:
        return self.database_path.parent / "config.json"

    def load_overrides(self) -> None:
        """Apply admin-saved overrides from config.json, if present."""
        if not self.config_path.exists():
            return
        try:
            saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.apply_overrides(saved)

    def apply_overrides(self, data: dict) -> None:
        if isinstance(data.get("home_currency"), str) and data["home_currency"].strip():
            self.home_currency = data["home_currency"].strip().upper()[:3]
        if isinstance(data.get("fx_rates"), dict):
            rates = {}
            for code, rate in data["fx_rates"].items():
                try:
                    value = float(rate)
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    rates[str(code).strip().upper()[:3]] = value
            self.fx_rates = rates
        if isinstance(data.get("max_files"), int) and 1 <= data["max_files"] <= 100:
            self.max_files = data["max_files"]
        if isinstance(data.get("max_file_mb"), int) and 1 <= data["max_file_mb"] <= 50:
            self.max_file_mb = data["max_file_mb"]
        if isinstance(data.get("policy_text"), str) and data["policy_text"].strip():
            self.policy_text = data["policy_text"]
        if isinstance(data.get("employee_name"), str) and data["employee_name"].strip():
            self.employee_name = data["employee_name"].strip()[:80]
        if isinstance(data.get("employee_dept"), str) and data["employee_dept"].strip():
            self.employee_dept = data["employee_dept"].strip()[:80]

    def save_overrides(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "home_currency": self.home_currency,
            "fx_rates": self.fx_rates,
            "max_files": self.max_files,
            "max_file_mb": self.max_file_mb,
            "employee_name": self.employee_name,
            "employee_dept": self.employee_dept,
        }
        if self.policy_text is not None:
            payload["policy_text"] = self.policy_text
        self.config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def from_env(cls) -> Settings:
        load_env_file(APP_ROOT / ".env")
        load_env_file(APP_ROOT.parents[1] / ".env")
        data = Path(os.environ.get("DATA_DIR", APP_ROOT / "data"))
        return cls(
            database_path=Path(os.environ.get("DATABASE_PATH", data / "expense.db")),
            files_dir=Path(os.environ.get("FILES_DIR", data / "files")),
            policy_path=Path(os.environ.get("POLICY_PATH", APP_ROOT / "seed" / "policy.md")),
            seed_dir=APP_ROOT / "seed" / "receipts",
            llm_provider=os.environ.get("LLM_PROVIDER", "auto"),
            gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
            gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
            seed_demo=os.environ.get("SEED_DEMO", "1") != "0",
            home_currency=os.environ.get("HOME_CURRENCY", "USD").upper(),
            employee_name=os.environ.get("EMPLOYEE_NAME", "Chandra Sharma"),
            employee_dept=os.environ.get("EMPLOYEE_DEPT", "Engineering"),
            admin_token=os.environ.get("ADMIN_TOKEN", ""),
        )
