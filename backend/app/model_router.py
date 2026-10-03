from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.config import settings


class QuotaExhausted(Exception):
    pass


@dataclass
class RouterState:
    simulate_quota_failure: bool = False
    active_model: str | None = None
    last_error: str | None = None
    circuit_open_for: set[str] = field(default_factory=set)
    log: list[dict] = field(default_factory=list)


state = RouterState()


def chain() -> list[str]:
    return [settings.primary_model, settings.fallback_model, settings.last_resort_model]


def current() -> dict:
    active = state.active_model if (state.active_model and state.active_model != "gemini-2.0-flash") else settings.primary_model
    return {
        "active_model": active,
        "fallback": active != settings.primary_model,
        "simulate_quota_failure": state.simulate_quota_failure,
        "log": state.log[-12:],
        "indicator": "fallback" if active != settings.primary_model else "primary",
    }


def set_simulate(on: bool) -> dict:
    state.simulate_quota_failure = on
    if on:
        state.circuit_open_for.add(settings.primary_model)
        state.active_model = settings.fallback_model
        state.log.append({"purpose": "router", "model": settings.primary_model, "event": "quota_simulated"})
        state.log.append({"purpose": "router", "model": settings.fallback_model, "event": "failover"})
    else:
        state.active_model = settings.primary_model
        state.circuit_open_for.clear()
        state.log.append({"purpose": "router", "model": settings.primary_model, "event": "restored"})
    return current()


def _client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai

        return genai.Client(api_key=api_key)
    except Exception:
        return None


def generate_json(prompt: str, *, purpose: str) -> str | None:
    """Try models in the fallback chain. Returns None if no live model is available."""
    client = _client()
    models = chain()
    if state.simulate_quota_failure and settings.primary_model in models:
        state.circuit_open_for.add(settings.primary_model)
        state.log.append({"purpose": purpose, "model": settings.primary_model, "event": "quota_simulated"})
        models = models[1:]

    if client is None:
        state.active_model = models[0] if models else settings.fallback_model
        state.log.append({"purpose": purpose, "model": state.active_model, "event": "offline_demo"})
        return None

    last_err = None
    for model in models:
        if model in state.circuit_open_for and model == settings.primary_model:
            continue
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            text = getattr(response, "text", None) or ""
            state.active_model = model
            state.log.append({"purpose": purpose, "model": model, "event": "ok"})
            return text
        except Exception as exc:
            msg = str(exc)
            last_err = msg
            quota = "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()
            state.log.append(
                {"purpose": purpose, "model": model, "event": "quota" if quota else "error", "detail": msg[:200]}
            )
            if quota:
                state.circuit_open_for.add(model)
                continue
            continue
    state.last_error = last_err
    return None
