from __future__ import annotations

import json
import os
from dataclasses import dataclass
from contextlib import contextmanager
from threading import Lock

from groq import Groq
from config import GROQ_API_KEY

print("KEY LOADED:", bool(GROQ_API_KEY))
print("KEY PREFIX:", GROQ_API_KEY[:8] if GROQ_API_KEY else "EMPTY")
from config import GROQ_API_KEY, USER_NAME
groq_client = Groq(api_key=GROQ_API_KEY)
from .online_settings import MODEL_CATALOG, PROVIDER_LABELS, online_settings
from .personality import MAHIRU_SYSTEM_PROMPT


PROVIDER_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
}
PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)


@dataclass(slots=True)
class OnlineRuntimeStatus:
    primary_provider: str
    fallback_provider: str
    active_provider: str
    active_model: str
    last_switch_reason: str


_runtime_lock = Lock()
_runtime_status = OnlineRuntimeStatus(
    primary_provider=online_settings.get().primary_provider,
    fallback_provider=online_settings.get_fallback_provider(),
    active_provider=online_settings.get().primary_provider,
    active_model=online_settings.get_selected_model(online_settings.get().primary_provider),
    last_switch_reason="Ready",
)


def build_messages(user_message: str, companion_context: str = "") -> list[dict[str, str]]:
    user_content = f"{USER_NAME} said: {user_message}"
    if companion_context.strip():
        user_content += f"\n\nCompanion memory and context:\n{companion_context.strip()}"
    return [
        {"role": "system", "content": MAHIRU_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def request_online_response(user_message: str, *, companion_context: str = "") -> str:
    settings = online_settings.get()
    primary_provider = settings.primary_provider
    fallback_provider = online_settings.get_fallback_provider()
    providers_to_try = [primary_provider]
    if fallback_provider != primary_provider:
        providers_to_try.append(fallback_provider)

    messages = build_messages(user_message, companion_context)
    last_error_message = "No online provider response was available."

    for index, provider in enumerate(providers_to_try):
        model = settings.selected_models.get(provider, MODEL_CATALOG[provider][0])
        raw_content, error_message = call_provider(provider, model, messages)
        if raw_content is not None:
            switch_reason = "Primary online provider responded."
            if index > 0:
                switch_reason = f"Switched to {PROVIDER_LABELS[provider]} because the primary provider did not respond."
            set_runtime_status(
                primary_provider=primary_provider,
                fallback_provider=fallback_provider,
                active_provider=provider,
                active_model=model,
                last_switch_reason=switch_reason,
            )
            return raw_content

        if error_message:
            last_error_message = error_message

    set_runtime_status(
        primary_provider=primary_provider,
        fallback_provider=fallback_provider,
        active_provider=primary_provider,
        active_model=settings.selected_models.get(primary_provider, MODEL_CATALOG[primary_provider][0]),
        last_switch_reason=f"Both online providers failed. Last error: {last_error_message}",
    )
    raise RuntimeError(last_error_message)

def call_provider(provider: str, model: str, messages: list[dict[str, str]]) -> tuple[str | None, str | None]:

    if provider != "groq":
        return None, "Unsupported provider."

    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.75,
            max_tokens=300,
        )

        content = response.choices[0].message.content.strip()
        return content, None

    except Exception as exc:
        return None, f"Groq request failed: {exc}"


def get_api_key(provider: str) -> str:

    if provider == "groq":
        return GROQ_API_KEY.strip()
    return ""


def get_runtime_status() -> OnlineRuntimeStatus:
    with _runtime_lock:
        return OnlineRuntimeStatus(
            primary_provider=_runtime_status.primary_provider,
            fallback_provider=_runtime_status.fallback_provider,
            active_provider=_runtime_status.active_provider,
            active_model=_runtime_status.active_model,
            last_switch_reason=_runtime_status.last_switch_reason,
            
        )
    


def set_runtime_status(*, primary_provider: str, fallback_provider: str, active_provider: str, active_model: str, last_switch_reason: str):
    with _runtime_lock:
        _runtime_status.primary_provider = primary_provider
        _runtime_status.fallback_provider = fallback_provider
        _runtime_status.active_provider = active_provider
        _runtime_status.active_model = active_model
        _runtime_status.last_switch_reason = last_switch_reason


def sync_runtime_preferences():
    settings = online_settings.get()
    primary_provider = settings.primary_provider
    fallback_provider = online_settings.get_fallback_provider()
    active_provider = primary_provider
    active_model = settings.selected_models.get(primary_provider, MODEL_CATALOG[primary_provider][0])
    set_runtime_status(
        primary_provider=primary_provider,
        fallback_provider=fallback_provider,
        active_provider=active_provider,
        active_model=active_model,
        last_switch_reason="Online preference updated from settings.",
    )


@contextmanager
def disable_proxy_environment():
    saved_values = {key: os.environ.pop(key, None) for key in PROXY_ENV_KEYS}
    try:
        yield
    finally:
        for key, value in saved_values.items():
            if value is not None:
                os.environ[key] = value
                