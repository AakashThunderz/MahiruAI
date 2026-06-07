from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock


SETTINGS_PATH = Path(__file__).resolve().parent.parent / ".cache" / "tts_settings.json"

TTS_ENGINES = {
    "edge": "Online Edge TTS",
    "kokoro": "Offline Kokoro TTS",
}


@dataclass(slots=True)
class TtsSettings:
    selected_engine: str = "edge"


class TtsSettingsManager:
    def __init__(self, settings_path: Path = SETTINGS_PATH):
        self.settings_path = settings_path
        self._lock = Lock()
        self._settings = self._load()

    def _load(self) -> TtsSettings:
        if not self.settings_path.exists():
            return TtsSettings()
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception:
            return TtsSettings()
        selected_engine = str(payload.get("selected_engine", "edge")).strip().lower()
        if selected_engine not in TTS_ENGINES:
            selected_engine = "edge"
        return TtsSettings(selected_engine=selected_engine)

    def save(self):
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(asdict(self._settings), indent=2), encoding="utf-8")

    def get_engine(self) -> str:
        with self._lock:
            return self._settings.selected_engine

    def set_engine(self, engine: str):
        normalized = engine.strip().lower()
        if normalized not in TTS_ENGINES:
            return
        with self._lock:
            self._settings.selected_engine = normalized
            self.save()

    def get_engine_label(self) -> str:
        return TTS_ENGINES.get(self.get_engine(), TTS_ENGINES["edge"])


tts_settings = TtsSettingsManager()
