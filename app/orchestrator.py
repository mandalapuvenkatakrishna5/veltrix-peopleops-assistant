import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

from .config import (
    APP_TODAY,
    DB_PATH,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Company holiday dates, loaded from environment or defaulted to empty.
HOLIDAYS = set()

def _load_holidays():
    """Load optional holiday dates from the HOLIDAYS environment variable."""
    raw = os.getenv("HOLIDAYS", "")
    if not raw.strip():
        return []
    try:
        values = json.loads(raw)
        if isinstance(values, list):
            return values
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in raw.split(",") if item.strip()]


HOLIDAYS = set(_load_holidays())


def _client() -> OpenAI:
    """Create an LLM client for Ollama or OpenAI."""
    if LLM_PROVIDER == "ollama":
        return OpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",
            timeout=120,
            max_retries=1,
        )

    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Configure Ollama or add an OpenAI API key."
        )

    return OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=60,
        max_retries=1,
    )


def _model_name() -> str:
    if LLM_PROVIDER == "ollama":
        return OLLAMA_MODEL
    return OPENAI_MODEL


def _today() -> str:
    return APP_TODAY or date.today().isoformat()


def _get_context(question: str) -> str:
    """Retrieve basic local company-document context when available."""
    corpus_dir = PROJECT_ROOT / "data" / "corpus"
    if not corpus_dir.exists():
        return ""

    terms = {
        word.lower().strip(".,?!:;()[]{}\"'")
        for word in question.split()
        if len(word) > 3
    }

    matches = []
    extensions = {".txt", ".md", ".json", ".csv"}

    try:
        for path in corpus_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in extensions:
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            if not content.strip():
                continue

            content_lower = content.lower()
            score = sum(1 for term in terms if term in content_lower)

            if score:
                matches.append((score, path.name, content[:5000]))

        matches.sort(key=lambda item: item[0], reverse=True)
        selected = matches[:3]

        return "\n\n".join(
            f"Source: {name}\n{content}"
            for _, name, content in selected
        )
    except OSError:
        return ""


def _fallback_response(question: str) -> str:
    """Return a helpful response if the LLM service is unavailable."""
    return (
        "I'm the Veltrix PeopleOps Assistant. I couldn't reach the language "
        "model right now, so I can't reliably answer this request. "
        "Please check that Ollama is running and the configured model is available, "
        "then try again. Your question was: "
        f"{question}"
    )


def chat(
    question: str,
    user: Any = None,
    conversation_history: list | None = None,
    **kwargs,
) -> str:
    """
    Answer an HR/PeopleOps question using the configured LLM.

    Accepts a question string and optional user/history arguments so that
    existing API callers can pass additional context.
    """
    question = str(question or "").strip()
    if not question:
        return "Please enter a question."

    context = _get_context(question)

    system_prompt = f"""
You are the Veltrix PeopleOps Assistant, an HR assistant for a fictional company.

Today's date is {_today()}.

Your responsibilities:
- Answer employee questions about HR policies, leave, benefits, onboarding,
  attendance, and workplace processes.
- Be clear, respectful, concise, and practical.
- Use the provided company context when it is relevant.
- Never invent company policies, employee records, balances, or approvals.
- If information is unavailable, explain that and recommend contacting HR.
- Do not claim to submit, approve, or change an HR request unless a real tool
  has successfully completed that action.
- Treat the user as an employee unless the request provides another role.

Company context:
{context if context else "No matching company-document context was found."}
""".strip()

    messages = [{"role": "system", "content": system_prompt}]

    if conversation_history:
        for item in conversation_history[-10:]:
            if not isinstance(item, dict):
                continue

            role = item.get("role")
            content = item.get("content") or item.get("message")

            if role in {"user", "assistant"} and isinstance(content, str):
                messages.append({"role": role, "content": content[:4000]})

    messages.append({"role": "user", "content": question})

    try:
        client = _client()
        response = client.chat.completions.create(
            model=_model_name(),
            messages=messages,
            temperature=0.2,
        )

        answer = response.choices[0].message.content
        if answer and answer.strip():
            return answer.strip()

        return "I couldn't generate an answer. Please try asking in a different way."

    except Exception:
        return _fallback_response(question)