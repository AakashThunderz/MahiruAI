from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .file_actions import normalize_name, score_match, tokenize_name
from .web_actions import open_platform_search, open_top_spotify_result, open_top_youtube_result


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
MAX_MEDIA_SCAN = 12000
IGNORED_MEDIA_PREFIXES = ("temp_mahiru_", "piper_temp_")
GENERIC_AUDIO_REQUESTS = {"music", "song", "songs", "audio"}
GENERIC_VIDEO_REQUESTS = {"video", "videos", "movie", "movies"}
VIDEO_STYLE_HINTS = {
    "video",
    "edit",
    "amv",
    "clip",
    "episode",
    "scene",
    "comp",
    "tutorial",
    "reel",
    "short",
    "status",
}
SONG_STYLE_HINTS = {
    "song",
    "music",
    "track",
    "album",
    "lyrics",
    "spotify",
    "audio",
}
MEDIA_ROOT_NAMES = {
    "audio": ("Music",),
    "video": ("Videos",),
    "mixed": ("Music", "Videos", "Downloads", "Desktop"),
}


def play_media(target: str, media_type: str | None, platform: str | None = None) -> tuple[bool, str]:
    if platform:
        return open_platform_search(platform, target)

    preferred_media_type = infer_preferred_media_type(target, media_type)
    match = find_local_media(target, preferred_media_type)
    if match is not None:
        return open_local_media(match)

    fallback_type = choose_fallback_media_type(target, preferred_media_type)
    if fallback_type == "video":
        return open_top_youtube_result(target)

    return open_top_spotify_result(target)


def find_local_media(target: str, media_type: str | None) -> Path | None:
    if is_generic_media_request(target, media_type):
        return None

    best_match: Path | None = None
    best_score = -1
    scanned = 0
    query = target.lower().strip()

    for root in iter_media_search_roots(media_type):
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if should_ignore_media_file(path):
                continue

            scanned += 1
            if scanned > MAX_MEDIA_SCAN:
                return best_match

            suffix = path.suffix.lower()
            if media_type == "video" and suffix not in VIDEO_EXTENSIONS:
                continue
            if media_type == "audio" and suffix not in AUDIO_EXTENSIONS:
                continue
            if media_type is None and suffix not in AUDIO_EXTENSIONS | VIDEO_EXTENSIONS:
                continue

            score = score_local_media_match(path, query, media_type)
            if score > best_score:
                best_score = score
                best_match = path

    return best_match if best_score >= 80 else None


def should_ignore_media_file(path: Path) -> bool:
    lower_name = path.name.lower()
    return any(lower_name.startswith(prefix) for prefix in IGNORED_MEDIA_PREFIXES)


def is_generic_media_request(target: str, media_type: str | None) -> bool:
    cleaned = target.strip().lower()
    if media_type == "video":
        return cleaned in GENERIC_VIDEO_REQUESTS
    if media_type is None:
        return cleaned in GENERIC_AUDIO_REQUESTS | GENERIC_VIDEO_REQUESTS
    return cleaned in GENERIC_AUDIO_REQUESTS


def choose_fallback_media_type(target: str, media_type: str | None) -> str:
    if media_type in {"audio", "video"}:
        return media_type

    cleaned = target.lower()
    if any(hint in cleaned for hint in VIDEO_STYLE_HINTS):
        return "video"
    if any(hint in cleaned for hint in SONG_STYLE_HINTS):
        return "audio"

    return "audio"


def infer_preferred_media_type(target: str, media_type: str | None) -> str | None:
    if media_type in {"audio", "video"}:
        return media_type

    cleaned = target.lower()
    if any(hint in cleaned for hint in VIDEO_STYLE_HINTS):
        return "video"
    if any(hint in cleaned for hint in SONG_STYLE_HINTS):
        return "audio"
    return None


def score_local_media_match(path: Path, query: str, media_type: str | None) -> int:
    normalized_query = normalize_name(query)
    query_tokens = tokenize_name(query)
    normalized_stem = normalize_name(path.stem)
    normalized_parent = normalize_name(path.parent.name)
    stem_tokens = tokenize_name(path.stem)

    if not normalized_query or not query_tokens:
        return 0

    stem_score = score_match(path.stem, query)
    parent_score = score_match(path.parent.name, query)

    all_tokens_in_stem = all(token in normalized_stem for token in query_tokens)
    all_tokens_in_parent = all(token in normalized_parent for token in query_tokens)
    exact_token_hit = len(query_tokens) == 1 and query_tokens[0] in stem_tokens
    exact_or_substring_hit = normalized_query in normalized_stem

    if not (all_tokens_in_stem or all_tokens_in_parent or exact_token_hit or exact_or_substring_hit):
        return 0

    score = max(stem_score, parent_score - 20)

    if exact_or_substring_hit:
        score += 10
    if all_tokens_in_stem:
        score += 12
    elif all_tokens_in_parent:
        score += 4
    if exact_token_hit:
        score += 14

    if media_type == "video" and path.suffix.lower() in VIDEO_EXTENSIONS:
        score += 12
    elif media_type == "audio" and path.suffix.lower() in AUDIO_EXTENSIONS:
        score += 12
    elif media_type is None:
        if path.suffix.lower() in VIDEO_EXTENSIONS and any(hint in query.lower() for hint in VIDEO_STYLE_HINTS):
            score += 10
        if path.suffix.lower() in AUDIO_EXTENSIONS and any(hint in query.lower() for hint in SONG_STYLE_HINTS):
            score += 10

    if looks_like_sand_noise(path):
        score -= 35

    if query_tokens and len(query_tokens) == 1 and path.stem.lower() in {"sand", "sand ambience", "sand sound"}:
        score -= 40

    return score


def looks_like_sand_noise(path: Path) -> bool:
    lowered = path.stem.lower()
    noise_hints = ("sand", "sfx", "effect", "effects", "noise", "ambience", "ambient", "bgm loop")
    return any(hint in lowered for hint in noise_hints)


def open_local_media(path: Path) -> tuple[bool, str]:
    try:
        # Use Windows API ShellExecute (non-blocking)
        win32api.ShellExecute(0, "open", str(path), "", "", win32con.SW_SHOW)
    except OSError as exc:
        return False, f"I found {path.name}, but I could not play it: {exc}"

    return True, f"Playing {path.stem} from your PC."


def iter_media_search_roots(media_type: str | None) -> list[Path]:
    home = Path.home()
    root_names = MEDIA_ROOT_NAMES["mixed"]
    if media_type == "audio":
        root_names = MEDIA_ROOT_NAMES["audio"] + MEDIA_ROOT_NAMES["mixed"]
    elif media_type == "video":
        root_names = MEDIA_ROOT_NAMES["video"] + MEDIA_ROOT_NAMES["mixed"]

    roots: list[Path] = []
    seen: set[Path] = set()
    for name in root_names:
        root = home / name
        if root in seen:
            continue
        seen.add(root)
        roots.append(root)
    return roots
