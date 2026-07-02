from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import threading
from pathlib import Path
import sys
import tempfile
from contextlib import contextmanager, redirect_stdout

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import edge_tts
import pygame

from config import KOKORO_MODEL_PATH, KOKORO_SPEED, KOKORO_VOICE, PITCH, RATE, VOICE_ID, VOLUME
from mahiru.tts_settings import tts_settings


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
_KOKORO_PIPELINE = None


@contextmanager
def disable_proxy_environment():
    saved_values = {key: os.environ.pop(key, None) for key in PROXY_ENV_KEYS}
    try:
        yield
    finally:
        for key, value in saved_values.items():
            if value is not None:
                os.environ[key] = value


def play_audio_with_pygame(path: Path):
    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
    try:
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.play()
        clock = pygame.time.Clock()
        while pygame.mixer.music.get_busy():
            clock.tick(30)
    finally:
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        try:
            pygame.mixer.music.unload()
        except pygame.error:
            pass
        try:
            pygame.mixer.quit()
        except pygame.error:
            pass


async def generate_edge_voice_file(text: str, output_path: Path):
    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE_ID,
        rate=RATE,
        volume=VOLUME,
        pitch=PITCH,
    )
    await communicate.save(output_path)


def generate_kokoro_voice_file(text: str, output_path: Path):
    try:
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError(
            "Kokoro dependencies are missing. Install kokoro, soundfile, and sounddevice in the project venv."
        ) from exc

    pipeline = get_kokoro_pipeline()
    audio_chunks = []
    with redirect_stdout(io.StringIO()):
        for _graphemes, _phonemes, audio in pipeline(text, voice=KOKORO_VOICE, speed=KOKORO_SPEED):
            audio_chunks.append(audio)

    if not audio_chunks:
        raise RuntimeError("Kokoro did not return any audio.")

    import numpy as np

    full_audio = np.concatenate(audio_chunks)
    sf.write(output_path, full_audio, 24000)


def get_cache_paths(text: str, engine: str) -> tuple[Path, Path]:
    cache_dir = Path(tempfile.gettempdir()) / 'mahiru_voice' / 'cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha1(
        f'{engine}|{VOICE_ID}|{RATE}|{VOLUME}|{PITCH}|{KOKORO_VOICE}|{KOKORO_SPEED}|{text}'.encode('utf-8')
    ).hexdigest()
    mp3_path = cache_dir / f'{cache_key}.mp3'
    wav_path = cache_dir / f'{cache_key}.wav'
    return mp3_path, wav_path


def synthesize_and_play(text: str):
    engine = tts_settings.get_engine()
    mp3_path, wav_path = get_cache_paths(text, engine)

    if engine == "kokoro":
        if not wav_path.exists():
            generate_kokoro_voice_file(text, wav_path)
        # Run audio playback in separate thread
        def play_thread():
            play_audio_with_pygame(wav_path)
        threading.Thread(target=play_thread, daemon=True).start()
        return

    if not mp3_path.exists():
        # Run TTS generation in separate thread
        def tts_thread():
            asyncio.run(generate_edge_voice_file(text, mp3_path))
        threading.Thread(target=tts_thread, daemon=True).start()

    # Run audio playback in separate thread
    def play_thread():
        play_audio_with_pygame(mp3_path)
    threading.Thread(target=play_thread, daemon=True).start()


def get_kokoro_pipeline():
    global _KOKORO_PIPELINE
    if _KOKORO_PIPELINE is not None:
        return _KOKORO_PIPELINE

    try:
        from kokoro import KPipeline
    except ImportError as exc:
        raise RuntimeError(
            "Kokoro dependencies are missing. Install kokoro, soundfile, and sounddevice in the project venv."
        ) from exc

    model_path = resolve_kokoro_model_path()
    with disable_proxy_environment():
        with redirect_stdout(io.StringIO()):
            _KOKORO_PIPELINE = KPipeline(
                lang_code='a',
                repo_id=None,
                model=str(model_path),
                device='cpu',
            )
    return _KOKORO_PIPELINE


def resolve_kokoro_model_path() -> Path:
    configured = Path(KOKORO_MODEL_PATH)
    candidates = []
    if configured.is_absolute():
        candidates.append(configured)
    else:
        project_root = Path(__file__).resolve().parent.parent
        candidates.append(project_root / configured)
        candidates.append(project_root / 'KokoroTTS' / configured.name)
        candidates.append(project_root / 'mahiru' / 'KokoroTTS' / configured.name)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    searched = ', '.join(str(path) for path in candidates)
    raise RuntimeError(f"Kokoro model file was not found. Checked: {searched}")


def main():
    if '--service' in sys.argv[1:]:
        run_service_loop()
        return

    text = ' '.join(arg for arg in sys.argv[1:] if arg != '--service').strip()
    if not text:
        return

    try:
        synthesize_and_play(text)
    except Exception as exc:
        print(f"Voice worker error: {exc}", file=sys.stderr)
        sys.exit(1)


def run_service_loop():
    print(json.dumps({"status": "ready"}), flush=True)
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps({"status": "error", "message": "Invalid voice request payload."}), flush=True)
            continue

        command = str(payload.get("command", "")).strip().lower()
        if command == "shutdown":
            print(json.dumps({"status": "bye"}), flush=True)
            return

        if command != "speak":
            print(json.dumps({"status": "error", "message": f"Unsupported voice command: {command}"}), flush=True)
            continue

        text = str(payload.get("text", "")).strip()
        if not text:
            print(json.dumps({"status": "done"}), flush=True)
            continue

        try:
            synthesize_and_play(text)
            print(json.dumps({"status": "done"}), flush=True)
        except Exception as exc:
            print(json.dumps({"status": "error", "message": str(exc)}), flush=True)


if __name__ == '__main__':
    main()
