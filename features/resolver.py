from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .app_actions import can_resolve_app_name


OPEN_VERBS = ("open", "launch", "start", "run", "show")
PLAY_VERBS = ("play", "watch", "listen to")
CLOSE_VERBS = ("close", "quit", "stop")
MINIMIZE_VERBS = ("minimize",)
MAXIMIZE_VERBS = ("maximize",)
RESTORE_VERBS = ("restore",)
FOCUS_VERBS = ("focus", "switch to", "bring up", "bring", "go to")
WEBSITE_HINTS = (
    "website",
    "site",
    "web",
    "browser",
    ".com",
    ".org",
    ".net",
    ".io",
    ".gg",
    ".ai",
)
FILE_HINTS = (
    "file",
    "folder",
    "document",
    "pdf",
    "image",
    "photo",
    "picture",
    "download",
    "downloads",
    "desktop",
)
MEDIA_AUDIO_HINTS = ("song", "music", "track", "album", "spotify", "audio")
MEDIA_VIDEO_HINTS = ("video", "movie", "episode", "clip", "youtube", "watch")
CHAT_PREFIXES = (
    "who",
    "what",
    "why",
    "how",
    "when",
    "where",
    "can you tell",
    "tell me",
    "do you",
    "are you",
)
MUTE_PHRASES = ("mute", "unmute", "toggle mute")
VOLUME_UP_PHRASES = ("volume up", "increase volume", "turn up the volume", "make it louder")
VOLUME_DOWN_PHRASES = ("volume down", "decrease volume", "turn down the volume", "make it quieter", "lower the volume")
SHOW_DESKTOP_PHRASES = ("show desktop", "go to desktop", "minimize everything")
COPY_PHRASES = ("copy", "copy this", "copy selected", "copy that")
PASTE_PHRASES = ("paste", "paste this", "paste here")
CUT_PHRASES = ("cut", "cut this", "cut selected", "cut that")
SELECT_ALL_PHRASES = ("select all", "highlight everything")
SCREENSHOT_PHRASES = ("take screenshot", "take a screenshot", "capture screen", "screenshot", "capture my screen")
LOCK_SCREEN_PHRASES = ("lock screen", "lock my screen", "lock pc", "lock the computer")
TYPE_PREFIXES = ("type this ", "write this ", "type ", "write ")
MODE_PREFIXES = ("start ", "enable ")
KNOWN_MODES = {"study", "editing", "gaming", "work"}
KNOWN_WEBSITES = {
    "youtube",
    "google",
    "gmail",
    "github",
    "instagram",
    "facebook",
    "x",
    "twitter",
    "reddit",
    "netflix",
    "spotify",
    "discord",
    "amazon",
    "chatgpt",
    "openai",
    "linkedin",
    "notion",
}
KNOWN_APPS = {
    "chrome",
    "brave",
    "spotify",
    "discord",
    "telegram",
    "whatsapp",
    "steam",
    "notepad",
    "calculator",
    "paint",
    "photoshop",
    "vlc",
    "obs",
    "file explorer",
    "explorer",
    "task manager",
    "settings",
    "cmd",
    "powershell",
    "visual studio code",
    "vs code",
    "code",
}


@dataclass(slots=True)
class ActionRequest:
    kind: str
    target: str
    original_text: str
    media_type: str | None = None
    action: str | None = None
    platform: str | None = None


def classify_user_request(command: str) -> ActionRequest | None:
    text = normalize(command)
    if not text:
        return None

    if looks_like_chat(text):
        return None

    if is_play_request(text):
        media_platform = extract_media_platform(text)
        return ActionRequest(
            kind="media",
            target=clean_media_target(extract_target(text, PLAY_VERBS)),
            original_text=command,
            media_type=guess_media_type(text),
            platform=media_platform,
        )

    window_request = classify_window_request(text, command)
    if window_request is not None:
        return window_request

    system_request = classify_system_request(text, command)
    if system_request is not None:
        return system_request

    mode_request = classify_mode_request(text, command)
    if mode_request is not None:
        return mode_request

    if is_open_request(text):
        target = extract_target(text, OPEN_VERBS)
        if not target:
            return None

        if looks_like_file_request(text, target):
            return ActionRequest(kind="file", target=target, original_text=command)
        if looks_like_explicit_website_request(text, target):
            return ActionRequest(kind="website", target=target, original_text=command)
        if looks_like_app_request(target):
            return ActionRequest(kind="app", target=target, original_text=command)
        if looks_like_website_request(text, target):
            return ActionRequest(kind="website", target=target, original_text=command)
        if looks_like_path(target):
            return ActionRequest(kind="file", target=target, original_text=command)
        if len(target.split()) <= 4:
            return ActionRequest(kind="app", target=target, original_text=command)

        return ActionRequest(kind="website", target=target, original_text=command)

    if text.startswith("visit "):
        target = extract_target(text, ("visit",))
        return ActionRequest(kind="website", target=target, original_text=command)

    return None


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def looks_like_chat(text: str) -> bool:
    if text.endswith("?"):
        return True
    return any(text.startswith(prefix) for prefix in CHAT_PREFIXES)


def is_open_request(text: str) -> bool:
    return any(verb in text for verb in OPEN_VERBS)


def is_play_request(text: str) -> bool:
    return any(verb in text for verb in PLAY_VERBS)


def classify_window_request(text: str, original_text: str) -> ActionRequest | None:
    for verbs, action_name in (
        (CLOSE_VERBS, "close"),
        (MINIMIZE_VERBS, "minimize"),
        (MAXIMIZE_VERBS, "maximize"),
        (RESTORE_VERBS, "restore"),
        (FOCUS_VERBS, "focus"),
    ):
        if any(text.startswith(f"{verb} ") for verb in verbs):
            target = extract_target(text, verbs)
            if target and looks_like_app_request(target):
                return ActionRequest(
                    kind="app_control",
                    target=target,
                    original_text=original_text,
                    action=action_name,
                )
    return None


def classify_system_request(text: str, original_text: str) -> ActionRequest | None:
    if text in MUTE_PHRASES or any(text.startswith(f"{phrase} ") for phrase in MUTE_PHRASES):
        return ActionRequest(kind="system_control", target="", original_text=original_text, action="mute")

    if any(phrase in text for phrase in VOLUME_UP_PHRASES):
        return ActionRequest(kind="system_control", target="", original_text=original_text, action="volume_up")

    if any(phrase in text for phrase in VOLUME_DOWN_PHRASES):
        return ActionRequest(kind="system_control", target="", original_text=original_text, action="volume_down")

    if text in SHOW_DESKTOP_PHRASES:
        return ActionRequest(kind="system_control", target="", original_text=original_text, action="show_desktop")

    if text in COPY_PHRASES:
        return ActionRequest(kind="system_control", target="", original_text=original_text, action="copy")

    if text in PASTE_PHRASES:
        return ActionRequest(kind="system_control", target="", original_text=original_text, action="paste")

    if text in CUT_PHRASES:
        return ActionRequest(kind="system_control", target="", original_text=original_text, action="cut")

    if text in SELECT_ALL_PHRASES:
        return ActionRequest(kind="system_control", target="", original_text=original_text, action="select_all")

    if text in SCREENSHOT_PHRASES:
        return ActionRequest(kind="system_control", target="", original_text=original_text, action="screenshot")

    if text in LOCK_SCREEN_PHRASES:
        return ActionRequest(kind="system_control", target="", original_text=original_text, action="lock_screen")

    for prefix in TYPE_PREFIXES:
        if text.startswith(prefix):
            target = extract_text_payload(original_text, prefix)
            if target:
                return ActionRequest(kind="system_control", target=target, original_text=original_text, action="type_text")

    return None


def classify_mode_request(text: str, original_text: str) -> ActionRequest | None:
    for prefix in MODE_PREFIXES:
        if text.startswith(prefix):
            target = text[len(prefix):].strip()
            target = target.removesuffix(' mode').strip()
            if target in KNOWN_MODES:
                return ActionRequest(kind='workflow_mode', target=target, original_text=original_text, action='start')
    return None


def extract_text_payload(original_text: str, normalized_prefix: str) -> str:
    stripped = original_text.strip()
    if stripped.lower().startswith(normalized_prefix):
        return stripped[len(normalized_prefix):].strip()
    return ''


def looks_like_website_request(text: str, target: str) -> bool:
    return any(
        site == target or f"{site} " in target or site in target for site in KNOWN_WEBSITES
    ) or looks_like_domain(target)


def looks_like_file_request(text: str, target: str) -> bool:
    return (
        any(hint in text for hint in FILE_HINTS)
        or target in {"downloads", "desktop", "documents", "music", "pictures", "videos"}
        or looks_like_path(target)
    )


def looks_like_explicit_website_request(text: str, target: str) -> bool:
    return any(hint in text for hint in WEBSITE_HINTS) or looks_like_domain(target)


def looks_like_app_request(target: str) -> bool:
    return target in KNOWN_APPS or any(app in target for app in KNOWN_APPS) or can_resolve_app_name(target)


def looks_like_path(target: str) -> bool:
    return (
        "\\" in target
        or "/" in target
        or ":" in target
        or target.startswith(".")
        or bool(re.search(r"\.[a-z0-9]{2,5}$", target))
    )


def looks_like_domain(target: str) -> bool:
    return bool(re.search(r"([a-z0-9-]+\.)+[a-z]{2,}", target))


def extract_target(text: str, verbs: Iterable[str]) -> str:
    target = text
    for verb in verbs:
        if verb in target:
            target = target.split(verb, 1)[1]
            break

    target = re.sub(r"\b(for me|please|now|on my pc|on pc|using brave|in brave)\b", "", target)
    target = re.sub(r"^[\s,:-]+|[\s,:-]+$", "", target)
    return target


def clean_media_target(target: str) -> str:
    cleaned = re.sub(r"\b(from|on)\s+(youtube|yt|spotify|soundcloud|netflix|prime video|amazon prime|jiosaavn|gaana|wynk)\b", "", target)
    cleaned = re.sub(r"\b(play it on|search it on)\s+(youtube|yt|spotify|soundcloud|netflix|prime video|amazon prime|jiosaavn|gaana|wynk)\b", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned


def extract_media_platform(text: str) -> str | None:
    platform_patterns = {
        "youtube": (
            r"\bfrom youtube\b",
            r"\bon youtube\b",
            r"\bfrom yt\b",
            r"\bon yt\b",
            r"\byoutube\b",
            r"\byt\b",
        ),
        "spotify": (r"\bfrom spotify\b", r"\bon spotify\b", r"\bspotify\b"),
        "soundcloud": (r"\bfrom soundcloud\b", r"\bon soundcloud\b", r"\bsoundcloud\b"),
        "netflix": (r"\bfrom netflix\b", r"\bon netflix\b", r"\bnetflix\b"),
        "prime video": (r"\bfrom prime video\b", r"\bon prime video\b", r"\bamazon prime\b", r"\bprime video\b"),
        "jiosaavn": (r"\bfrom jiosaavn\b", r"\bon jiosaavn\b", r"\bjiosaavn\b"),
        "gaana": (r"\bfrom gaana\b", r"\bon gaana\b", r"\bgaana\b"),
        "wynk": (r"\bfrom wynk\b", r"\bon wynk\b", r"\bwynk\b"),
    }
    for platform, patterns in platform_patterns.items():
        if any(re.search(pattern, text) for pattern in patterns):
            return platform
    return None


def guess_media_type(text: str) -> str | None:
    if any(hint in text for hint in MEDIA_AUDIO_HINTS):
        return "audio"
    if any(hint in text for hint in MEDIA_VIDEO_HINTS):
        return "video"
    return None
