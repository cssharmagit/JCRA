from __future__ import annotations

import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings
from app.db import Database
from app.errors import AgentError
from app.routes import router
from app.services.agent import ClaimAgent
from app.services.llm import LLM, build_llm

logger = logging.getLogger("expense_agent")


def create_app(settings: Settings | None = None, llm: LLM | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.load_overrides()
    model = llm or settings.llm or build_llm(settings)
    agent = ClaimAgent(Database(settings.database_path), model, settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        agent.bootstrap()
        logger.info("Expense agent ready (%s)", model.name)
        yield

    app = FastAPI(title="JRCA - Jio Reimbursement Claims Assistant", lifespan=lifespan)
    app.state.agent = agent
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8443", "http://127.0.0.1:8443", "http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.exception_handler(AgentError)
    async def handle_agent_error(_request, exc: AgentError):
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def handle_unexpected(_request, exc: Exception):
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Something went wrong on the server. The receipts already read are saved; refresh and try the rest again."},
        )

    return app


app = create_app()
