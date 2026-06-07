import asyncio
import os
from pathlib import Path

import edge_tts
import pygame

from config import PITCH, RATE, TEMP_AUDIO_FILE, VOICE_ID, VOLUME
from .tts_settings import tts_settings


pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
TEMP_AUDIO_PATH = Path(TEMP_AUDIO_FILE)


async def mahiru_speak(text: str):
    """Generate speech, play it, and delete the temporary audio file."""
    print(f"Mahiru: {text}")

    temp_audio = TEMP_AUDIO_PATH
    try:
        cleanup_temp_audio_file(temp_audio)

        communicate = edge_tts.Communicate(
            text=text,
            voice=VOICE_ID,
            rate=RATE,
            volume=VOLUME,
            pitch=PITCH,
        )

        await communicate.save(temp_audio)
        pygame.mixer.music.load(str(temp_audio))
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.3)
    except Exception as exc:
        print(f"Voice error: {exc}")
    finally:
        cleanup_temp_audio_file(temp_audio)


def speak(text: str):
    """Speak a line of dialogue."""
    engine = tts_settings.get_engine()
    if engine != "edge":
        from .voice_worker import synthesize_and_play

        synthesize_and_play(text)
        return

    asyncio.run(mahiru_speak(text))


def cleanup_old_temp_files():
    """Delete any stale temporary audio files left in the project root."""
    for file in Path(".").glob("temp_mahiru_*.mp3"):
        cleanup_temp_audio_file(file)
    cleanup_temp_audio_file(TEMP_AUDIO_PATH)


def cleanup_temp_audio_file(path: Path):
    """Release the audio handle and remove a temporary file if it exists."""
    try:
        pygame.mixer.music.stop()
    except pygame.error:
        pass

    try:
        pygame.mixer.music.unload()
    except pygame.error:
        pass

    if not path.exists():
        return

    try:
        path.unlink(missing_ok=True)
    except OSError:
        try:
            os.remove(str(path))
        except OSError:
            pass
