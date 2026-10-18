from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from app.config import settings


class QuotaExhausted(Exception):
    pass


@dataclass
class RouterState:
    simulate_quota_failure: bool = False
    active_model: str = settings.primary_model
    last_error: Optional[str] = None
    circuit_open_for: Set[str] = field(default_factory=set)
    log: List[Dict] = field(default_factory=list)
    switch_warning: Optional[str] = None
    switched: bool = False


state = RouterState()


def chain() -> List[str]:
    seen = set()
    models = []
    for m in [settings.primary_model, settings.fallback_model, "gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite", settings.last_resort_model]:
        if m and m not in seen:
            seen.add(m)
            models.append(m)
    return models


def current() -> dict:
    active = state.active_model or settings.primary_model
    is_offline = (active == "offline-fallback")
    is_fallback = active != settings.primary_model
    indicator = "offline" if is_offline else ("fallback" if is_fallback else "primary")
    switch_warning = state.switch_warning
    if not switch_warning and is_fallback:
        switch_warning = f"Primary model token/quota exhausted. Active model switched to {active}."
    return {
        "active_model": active,
        "primary_model": settings.primary_model,
        "is_offline": is_offline,
        "fallback": is_fallback,
        "switched": is_fallback or bool(state.switch_warning),
        "switch_warning": switch_warning,
        "simulate_quota_failure": state.simulate_quota_failure,
        "log": state.log[-12:],
        "indicator": indicator,
        "last_error": state.last_error,
    }


def set_active_model(model_name: str) -> dict:
    prev = state.active_model
    if model_name in ("offline", "offline-fallback", "offline-heuristic-fallback"):
        state.active_model = "offline-fallback"
        state.switched = True
        state.switch_warning = "System switched to Zero-Trust Offline Model Engine."
        state.log.append({"purpose": "router", "from": prev, "model": "offline-fallback", "event": "switched_offline"})
    elif model_name in (settings.primary_model, settings.fallback_model, settings.last_resort_model):
        state.active_model = model_name
        state.simulate_quota_failure = False
        state.circuit_open_for.clear()
        if model_name != settings.primary_model:
            state.switched = True
            state.switch_warning = f"Active model manually switched to {model_name}."
        else:
            state.switched = False
            state.switch_warning = None
        state.log.append({"purpose": "router", "from": prev, "model": model_name, "event": "switched_model"})
    return current()


def set_simulate(on: bool) -> dict:
    state.simulate_quota_failure = on
    if on:
        state.circuit_open_for.add(settings.primary_model)
        state.active_model = settings.fallback_model
        state.switched = True
        state.switch_warning = f"Primary model quota limit simulated. Model automatically switched to {settings.fallback_model}."
        state.log.append({"purpose": "router", "model": settings.primary_model, "event": "quota_simulated"})
        state.log.append({"purpose": "router", "model": settings.fallback_model, "event": "failover"})
    else:
        state.active_model = settings.primary_model
        state.circuit_open_for.clear()
        state.switched = False
        state.switch_warning = None
        state.log.append({"purpose": "router", "model": settings.primary_model, "event": "restored"})
    return current()


def _client():
    api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai

        return genai.Client(api_key=api_key, http_options={"timeout": 30000.0})
    except Exception:
        return None


def generate_json(prompt: str, *, purpose: str) -> Optional[str]:
    """Try models in the fallback chain. Returns None if no live model is available or offline mode active."""
    client = _client()
    if client is None:
        state.active_model = "offline-fallback"
        state.log.append({"purpose": purpose, "model": "offline-fallback", "event": "offline_no_key"})
        return None

    if state.active_model == "offline-fallback" and not state.simulate_quota_failure:
        # Re-attempt live models if key is present
        pass

    models = chain()
    if state.simulate_quota_failure and settings.primary_model in models:
        state.circuit_open_for.add(settings.primary_model)
        state.log.append({"purpose": purpose, "model": settings.primary_model, "event": "quota_simulated"})
        models = [m for m in models if m != settings.primary_model]

    last_err = None
    for model in models:
        if model in state.circuit_open_for and model == settings.primary_model:
            continue
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            text = getattr(response, "text", None) or ""
            if model != settings.primary_model:
                state.switched = True
                state.switch_warning = f"Primary model token/quota exhausted. System switched to {model}."
            else:
                state.switched = False
                state.switch_warning = None
            state.active_model = model
            state.log.append({"purpose": purpose, "model": model, "event": "ok"})
            return text
        except Exception as exc:
            msg = str(exc)
            last_err = msg
            quota = "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower() or "limit" in msg.lower()
            state.log.append(
                {"purpose": purpose, "model": model, "event": "quota" if quota else "error", "detail": msg[:200]}
            )
            state.switched = True
            state.switch_warning = f"Model {model} limit reached. Switching to next available model in chain."
            if quota:
                state.circuit_open_for.add(model)
                continue
            continue
    state.last_error = last_err
    state.active_model = "offline-fallback"
    state.switched = True
    state.switch_warning = "All live Gemini models exhausted or token quotas reached. System switched to Zero-Trust Offline Model Engine."
    return None
