# Mahiru AI Desktop Companion

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![Status](https://img.shields.io/badge/Status-Experimental-orange)
![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red)

Mahiru AI Desktop Companion is a Windows-focused anime desktop assistant built with Python. It combines a Tkinter chat interface, Live2D avatar rendering, online LLM providers, voice input, text-to-speech, PC controls, app launching, media search, and lightweight companion memory.

The project is designed around a desktop companion workflow: talk or type to Mahiru, get a structured assistant reply, show a matching avatar mood, speak the response aloud, and optionally perform safe local PC actions such as opening apps, controlling windows, searching media, or launching websites.

> This project is experimental and currently optimized for a personal Windows desktop setup.

## ✨ Features

- **Desktop companion UI** with Tkinter chat, text input, microphone toggle, status display, and settings panel.
- **Live2D avatar panel** using Cubism models from `visuals/assets/models/`, with scaling, vertical positioning, idle motion, blink, breath, and basic mood display support.
- **Online LLM support** with Cerebras as the primary provider and Groq as fallback.
- **Provider/model settings** for switching between supported Cerebras and Groq models from the UI.
- **Structured assistant replies** using JSON fields for text, expression, mood, motion, and status text.
- **Voice output** with selectable online Edge TTS or offline Kokoro TTS.
- **Kokoro local TTS service mode** so the Kokoro model can stay loaded during the app session instead of reloading for every reply.
- **Voice input** through `speech_recognition` using microphone capture and Google speech recognition.
- **Smart companion memory** for simple remembered likes, dislikes, notes, reminders, idle greetings, and welcome-back behavior.
- **PC control commands** for opening apps, files, folders, websites, controlling windows, volume, clipboard shortcuts, lock screen, screenshots, and typing text into the foreground window.
- **Media handling** with local-first audio/video search, platform hints, and fallback searches for YouTube, Spotify, SoundCloud, and other web services.
- **Browser automation** through Selenium and Brave for opening/searching supported platforms and attempting autoplay.
- **Workflow modes** for opening grouped tools such as study, editing, gaming, and work setups.

## 📁 Project Structure

```text
.
├── main.py                         # App entry point
├── config.py                       # API keys and default model/TTS settings
├── requirements.txt                # Python dependencies
├── features/
│   ├── actions.py                  # System, app, file, media, and web actions
│   ├── app_index.py                # Installed app discovery/indexing
│   ├── browser_automation.py       # Brave/Selenium browser automation
│   ├── media_finder.py             # Local audio/video search
│   ├── resolver.py                 # Natural-language command routing
│   ├── web_search.py               # Platform and search URL helpers
│   └── window_control.py           # Close/minimize/maximize/focus windows
├── mahiru/
│   ├── brain.py                    # Main assistant response orchestration
│   ├── online_providers.py         # Cerebras and Groq API calls
│   ├── offline_providers.py        # Reserved for future offline LLM support
│   ├── companion.py                # Memory, reminders, idle behavior
│   ├── listener.py                 # Microphone speech recognition
│   ├── speaker.py                  # Voice service client
│   ├── voice_worker.py             # Edge/Kokoro TTS worker
│   ├── response_types.py           # Reply schema
│   └── KokoroTTS/
│       └── kokorotts.py            # Local Kokoro test script
└── visuals/
    ├── ui.py                       # Tkinter UI and settings
    ├── live2d_frame.py             # Live2D OpenGL frame
    ├── expression_controller.py    # UI/avatar expression state
    └── assets/models/              # Live2D model assets
```

## 📦 Requirements

- Windows 10 or Windows 11
- Python 3.11 or newer recommended
- Microphone for voice input
- Brave Browser for browser automation features
- Internet connection for Cerebras, Groq, Edge TTS, and Google speech recognition
- Local Kokoro model file for offline Kokoro TTS

The project imports several desktop/runtime libraries. Install dependencies from `requirements.txt` first. If optional modules such as Live2D, OpenGL, or Selenium are missing in your environment, install the matching packages required by your local setup.

## 🚀 Installation Guide

1. Clone or download the repository.

```bash
git clone <repository-url>
cd ai_anime_assistant(mahiru-ai)
```

2. Create and activate a virtual environment.

```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Install all dependencies using:

```bash
pip install -r requirements.txt
```

4. Download `Kokoro_espeak_Q4.gguf` and place it inside:

```text
mahiru/KokoroTTS/
```

5. Create a `config.py` file in the project root containing:

```python
GROQ_API_KEY = "your_groq_api_key"
CEREBRAS_API_KEY = "your_cerebras_api_key"
```

6. Run the project using:

```bash
python main.py
```

## ⚙️ Setup Instructions

The app starts from `main.py` and opens the desktop UI. From the UI, you can type messages, toggle the microphone, test voice output, change TTS mode, adjust the avatar scale, and switch online model/provider settings.

For the current codebase, online assistant responses are handled through Cerebras first and Groq fallback second. Offline LLM routing is not implemented yet, although the project contains an `offline_providers.py` placeholder for future local model support.

## 🔧 Configuration

`config.py` controls API keys and default provider settings.

```python
GROQ_API_KEY = "your_groq_api_key"
CEREBRAS_API_KEY = "your_cerebras_api_key"

ONLINE_PROVIDER = "cerebras"
CEREBRAS_MODEL = "llama3.1-8b"
GROQ_MODEL = "llama-3.3-70b-versatile"

TTS_ENGINE = "edge"
EDGE_TTS_VOICE = "en-US-AriaNeural"
KOKORO_MODEL_PATH = "mahiru/KokoroTTS/Kokoro_espeak_Q4.gguf"
KOKORO_VOICE = "af_bella"
```

Runtime settings are saved under `.cache/`, including online model settings, TTS selection, companion memory, and app indexes.

Do not commit real API keys to a public repository.

## 💬 Usage Examples

```text
Open Discord
Close Spotify
Minimize Brave
Maximize VS Code
Open Downloads
Search Mahiru Shiina wallpaper
Play attention
Play death bed from YouTube
Play sahiba from Spotify
Remind me to drink water in 20 minutes
What do you remember about me?
Switch to study mode
Take screenshot
Volume up
Mute volume
```

## 🛠️ Troubleshooting

| Problem | What to Check |
| --- | --- |
| No assistant reply | Verify `CEREBRAS_API_KEY` and `GROQ_API_KEY` in `config.py`. |
| Cerebras fails | Check the selected Cerebras model and API quota, then use Groq fallback from settings. |
| Groq fails | Check the selected Groq model name and API key. |
| No voice output | Test both Edge TTS and Kokoro TTS from settings. |
| Kokoro is slow | Make sure `Kokoro_espeak_Q4.gguf` is inside `mahiru/KokoroTTS/` and the voice worker is running in service mode. |
| Microphone does not work | Check microphone permissions, PyAudio installation, and internet access for Google speech recognition. |
| Live2D model does not render | Check that Live2D, OpenGL, and `pyopengltk` are installed and that a valid `.model3.json` exists under `visuals/assets/models/`. |
| Browser opens but does not autoplay | Make sure Brave is installed at the expected Windows path and that Selenium can control the browser. Some websites block autoplay. |
| App command opens the wrong app | Delete the cached app index in `.cache/` and let the assistant rebuild it. |
| Import or syntax error | Run Python from the project root and check recently edited source files, especially schema files such as `mahiru/response_types.py`. |

## 🗺️ Roadmap

- Add a complete offline LLM provider implementation in `mahiru/offline_providers.py`.
- Add Ollama/local model routing while keeping only one model active at a time.
- Improve Live2D expression mapping and model-level lip sync.
- Harden browser autoplay for YouTube, Spotify, and other platforms.
- Add automated tests for command routing, media search, and provider fallback.
- Improve dependency packaging and document optional Live2D/Selenium dependencies clearly.
- Add Windows `.exe` packaging support.
- Move secrets to environment variables or a safer local configuration flow.
- Add a cleaner open-source license file if the project is intended for public reuse.

## 🙏 Credits

- Project author: Aakash / KairoqX
- Live2D Cubism ecosystem for avatar rendering support
- Kokoro TTS for local voice generation
- Edge TTS for online voice generation
- Cerebras and Groq for online LLM inference
- Python open-source libraries used throughout the project

## 📄 License

Copyright (c) 2026 Aakash (KairoqX).

All rights reserved unless a separate license file is added to this repository.
