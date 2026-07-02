from dotenv import load_dotenv
import os

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
USER_NAME = os.getenv("USER_NAME", "User")

DEFAULT_GROQ_MODEL = os.getenv(
    "DEFAULT_GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

VOICE_ID = os.getenv("VOICE_ID", "en-US-AriaNeural")
RATE = os.getenv("RATE", "-10%")
VOLUME = os.getenv("VOLUME", "+0%")
PITCH = os.getenv("PITCH", "+7Hz")
TEMP_AUDIO_FILE = "temp_mahiru_voice.mp3"

KOKORO_MODEL_PATH = os.getenv(
    "KOKORO_MODEL_PATH",
    "mahiru/KokoroTTS/Kokoro_espeak_Q4.gguf"
)

KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_bella")
KOKORO_SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))