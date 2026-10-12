from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.errors import CognitionError
from app.services.cognition import parse_json, render_prompt

logger = logging.getLogger("expense_agent")


@dataclass
class Attachment:
    filename: str
    media_type: str
    data: bytes


class LLM:
    name: str

    def complete(self, task: str, payload: dict, attachments: list[Attachment] | None = None) -> dict:
        raise NotImplementedError


class GeminiLLM(LLM):
    def __init__(self, api_key: str, model: str):
        self.name = "gemini"
        self.api_key = api_key
        self.model = model

    def complete(self, task: str, payload: dict, attachments: list[Attachment] | None = None) -> dict:
        text = self._generate(render_prompt(task, payload), attachments or [])
        try:
            return parse_json(text)
        except CognitionError:
            repaired = self._generate(
                "Return the following as one JSON object with no markdown:\n" + text[:8000],
                [],
            )
            return parse_json(repaired)

    def _generate(self, prompt: str, attachments: list[Attachment]) -> str:
        parts: list[dict] = [{"text": prompt}]
        for item in attachments:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": item.media_type,
                        "data": base64.b64encode(item.data).decode("ascii"),
                    }
                }
            )
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            json={
                "contents": [{"role": "user", "parts": parts}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
            },
            timeout=90,
        )
        if response.status_code >= 400:
            logger.warning("Gemini error status %s", response.status_code)
            raise CognitionError("The model provider returned an error. Check the API key and try again.")
        body = response.json()
        try:
            return body["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise CognitionError() from exc


class OpenAILLM(LLM):
    def __init__(self, api_key: str, model: str):
        self.name = "openai"
        self.api_key = api_key
        self.model = model

    def complete(self, task: str, payload: dict, attachments: list[Attachment] | None = None) -> dict:
        text = self._generate(render_prompt(task, payload), attachments or [])
        try:
            return parse_json(text)
        except CognitionError:
            repaired = self._generate("Return the following as one JSON object with no markdown:\n" + text[:8000], [])
            return parse_json(repaired)

    def _generate(self, prompt: str, attachments: list[Attachment]) -> str:
        content: list[dict] = [{"type": "text", "text": prompt}]
        for item in attachments:
            encoded = base64.b64encode(item.data).decode("ascii")
            if item.media_type.startswith("image/"):
                content.append({"type": "image_url", "image_url": {"url": f"data:{item.media_type};base64,{encoded}"}})
            elif item.media_type == "application/pdf":
                content.append(
                    {
                        "type": "file",
                        "file": {"filename": item.filename, "file_data": f"data:application/pdf;base64,{encoded}"},
                    }
                )
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": content}],
            },
            timeout=90,
        )
        if response.status_code >= 400:
            logger.warning("OpenAI error status %s", response.status_code)
            raise CognitionError("The model provider returned an error. Check the API key and try again.")
        body = response.json()
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise CognitionError() from exc


class AnthropicLLM(LLM):
    def __init__(self, api_key: str, model: str):
        self.name = "anthropic"
        self.api_key = api_key
        self.model = model

    def complete(self, task: str, payload: dict, attachments: list[Attachment] | None = None) -> dict:
        text = self._generate(render_prompt(task, payload), attachments or [])
        try:
            return parse_json(text)
        except CognitionError:
            repaired = self._generate("Return the following as one JSON object with no markdown:\n" + text[:8000], [])
            return parse_json(repaired)

    def _generate(self, prompt: str, attachments: list[Attachment]) -> str:
        content: list[dict] = []
        for item in attachments:
            encoded = base64.b64encode(item.data).decode("ascii")
            if item.media_type.startswith("image/"):
                content.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": item.media_type, "data": encoded},
                    }
                )
            elif item.media_type == "application/pdf":
                content.append(
                    {
                        "type": "document",
                        "source": {"type": "base64", "media_type": "application/pdf", "data": encoded},
                    }
                )
        content.append({"type": "text", "text": prompt})
        try:
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 32000,
                    "temperature": 0.2,
                    "messages": [{"role": "user", "content": content}],
                },
                timeout=httpx.Timeout(300, connect=20),
            )
        except httpx.HTTPError as exc:
            logger.warning("Anthropic request failed: %s", exc)
            raise CognitionError("The model took too long or the connection dropped. Try again, or upload fewer files at once.") from exc
        if response.status_code >= 400:
            logger.warning("Anthropic error status %s: %s", response.status_code, response.text[:500])
            raise CognitionError("The model provider returned an error. Check the API key and try again.")
        body = response.json()
        if body.get("stop_reason") == "max_tokens":
            logger.warning("Anthropic output truncated at max_tokens")
        try:
            return "".join(block.get("text", "") for block in body["content"] if block.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise CognitionError() from exc


def build_llm(settings: Settings) -> LLM:
    from app.services.replay import ReplayLLM

    choice = settings.llm_provider
    if choice == "auto":
        if settings.anthropic_api_key:
            choice = "anthropic"
        elif settings.gemini_api_key:
            choice = "gemini"
        elif settings.openai_api_key:
            choice = "openai"
        else:
            choice = "mock"
    if choice == "anthropic":
        if not settings.anthropic_api_key:
            raise CognitionError("ANTHROPIC_API_KEY is not set.")
        return AnthropicLLM(settings.anthropic_api_key, settings.anthropic_model)
    if choice == "gemini":
        if not settings.gemini_api_key:
            raise CognitionError("GEMINI_API_KEY is not set.")
        return GeminiLLM(settings.gemini_api_key, settings.gemini_model)
    if choice == "openai":
        if not settings.openai_api_key:
            raise CognitionError("OPENAI_API_KEY is not set.")
        return OpenAILLM(settings.openai_api_key, settings.openai_model)
    return ReplayLLM()
