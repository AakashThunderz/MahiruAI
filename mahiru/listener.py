import speech_recognition as sr

from .voice import speak


def listen_to_you() -> str | None:
    """Listen for a short voice command."""
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("Mahiru is listening...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)

        try:
            audio = recognizer.listen(source, timeout=7, phrase_time_limit=8)
            text = recognizer.recognize_google(audio).lower().strip()
            print(f"You said: {text}")
            return text
        except sr.WaitTimeoutError:
            return None
        except Exception:
            speak("I'm sorry, Aakash. I couldn't hear you clearly. Could you say that again?")
            return None
