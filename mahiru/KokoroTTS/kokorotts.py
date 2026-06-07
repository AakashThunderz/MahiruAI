# =========================
# KOKORO GGUF REALTIME TEST
# =========================
#
# Install:
# pip install sounddevice soundfile kokoro
#
# Put:
# - Kokoro_espeak_Q4.gguf
# in same folder
#
# Run:
# python test.py
# =========================

import time
import sounddevice as sd
from kokoro import KPipeline

# Load pipeline
print("Loading Kokoro...")

start = time.time()

pipeline = KPipeline(
    lang_code='a',  # English
    repo_id=None,
    model='Kokoro_espeak_Q4.gguf'
)

print(f"Loaded in {time.time() - start:.2f}s\n")

while True:

    text = input("Enter text: ")

    if text.lower() == "exit":
        break

    start_gen = time.time()

    generator = pipeline(
        text,
        voice='af_bella',
        speed=1.0
    )

    for _, _, audio in generator:

        gen_time = time.time() - start_gen

        print(f"\nGenerated in: {gen_time:.2f}s")
        print(f"Audio length: {len(audio)/24000:.2f}s")

        realtime_factor = (len(audio)/24000) / gen_time

        print(f"Realtime factor: {realtime_factor:.2f}x")

        # Play audio
        sd.play(audio, 24000)
        sd.wait()