from .assistant import process_user_message
from .listener import listen_to_you
from .voice import speak


def run_mahiru():
    """Run Mahiru in voice mode."""
    speak(
        "Hello Aakash. It's me, Mahiru Shiina. I'm really happy to be here with you, and I'll do my best to take care of you."
    )

    while True:
        command = listen_to_you()
        if not command:
            continue

        should_continue, response = process_user_message(command)
        if response:
            speak(response)
        if not should_continue:
            break
