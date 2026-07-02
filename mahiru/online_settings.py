from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Lock

from config import (
    DEFAULT_GROQ_MODEL,
)


SETTINGS_PATH = Path(__file__).resolve().parent.parent / ".cache" / "online_settings.json"

MODEL_CATALOG = {
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
    ]
}

PROVIDER_LABELS = {
    "groq": "Groq"
}

@dataclass(slots=True)
class OnlineSettings:
    primary_provider: str = "groq"
    selected_models: dict[str, str] = field(
        default_factory=lambda: {
            "groq": DEFAULT_GROQ_MODEL,
        }
    )

class OnlineSettingsManager:
    def __init__(self, settings_path: Path = SETTINGS_PATH):
        self.settings_path = settings_path
        self._lock = Lock()
        self._settings = self._load()

    def _load(self) -> OnlineSettings:
        if not self.settings_path.exists():
            return OnlineSettings()
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception:
            return OnlineSettings()

        settings = OnlineSettings()
        primary_provider = str(payload.get("primary_provider", settings.primary_provider)).strip().lower()
        if primary_provider in MODEL_CATALOG:
            settings.primary_provider = primary_provider

        selected_models = payload.get("selected_models", {})
        if isinstance(selected_models, dict):
            for provider, model in selected_models.items():
                provider_name = str(provider).strip().lower()
                model_name = str(model).strip()
                if provider_name in MODEL_CATALOG and model_name in MODEL_CATALOG[provider_name]:
                    settings.selected_models[provider_name] = model_name

        return settings

    def save(self):
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(asdict(self._settings), indent=2), encoding="utf-8")

    def get(self) -> OnlineSettings:
        with self._lock:
            return OnlineSettings(
                primary_provider=self._settings.primary_provider,
                selected_models=dict(self._settings.selected_models),
            )

    def set_primary_provider(self, provider: str):
        normalized = provider.strip().lower()
        if normalized not in MODEL_CATALOG:
            return
        with self._lock:
            self._settings.primary_provider = normalized
            self.save()

    def set_selected_model(self, provider: str, model: str):
        normalized_provider = provider.strip().lower()
        normalized_model = model.strip()
        if normalized_provider not in MODEL_CATALOG:
            return
        if normalized_model not in MODEL_CATALOG[normalized_provider]:
            return
        with self._lock:
            self._settings.selected_models[normalized_provider] = normalized_model
            self.save()

    def get_selected_model(self, provider: str) -> str:
        settings = self.get()
        return settings.selected_models.get(provider, MODEL_CATALOG[provider][0])

    def get_fallback_provider(self) -> str:
        settings = self.get()
        return "groq"


online_settings = OnlineSettingsManager()
