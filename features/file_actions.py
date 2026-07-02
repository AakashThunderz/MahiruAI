from __future__ import annotations

from pathlib import Path
import os
import re


SEARCH_ROOT_NAMES = ("Desktop", "Documents", "Downloads", "Music", "Pictures", "Videos")
MAX_RESULTS_TO_SCAN = 3000


def open_file_or_folder(target: str) -> tuple[bool, str]:
    match = find_path_match(target)
    if match is None:
        return False, f"I could not find a file or folder matching {target}."

    try:
        # Use Windows API ShellExecute (non-blocking)
        win32api.ShellExecute(0, "open", str(match), "", "", win32con.SW_SHOW)
    except OSError as exc:
        return False, f"I found {match.name}, but I could not open it: {exc}"

    item_type = "folder" if match.is_dir() else "file"
    return True, f"Opening that {item_type} for you."


def find_path_match(target: str) -> Path | None:
    candidate = Path(target).expanduser()
    if candidate.exists():
        return candidate

    target_lower = target.lower()
    if target_lower in {"downloads", "desktop", "documents", "music", "pictures", "videos"}:
        folder = Path.home() / target_lower.capitalize()
        if folder.exists():
            return folder

    query = normalize_name(target)
    best_match: Path | None = None
    best_score = -1

    for root in iter_search_roots():
        if not root.exists():
            continue

        scanned = 0
        for path in root.rglob("*"):
            scanned += 1
            if scanned > MAX_RESULTS_TO_SCAN:
                break

            score = score_match(path.name, query)
            if score > best_score:
                best_score = score
                best_match = path

    return best_match if best_score > 0 else None


def iter_search_roots(include_cwd: bool = True) -> list[Path]:
    roots = [Path.cwd()] if include_cwd else []
    home = Path.home()
    roots.extend(home / name for name in SEARCH_ROOT_NAMES)
    return roots


def normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def tokenize_name(name: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", name.lower()) if token]


def score_match(candidate_name: str, query: str) -> int:
    normalized_candidate = normalize_name(candidate_name)
    normalized_query = normalize_name(query)
    query_tokens = tokenize_name(query)
    candidate_tokens = tokenize_name(candidate_name)

    if not normalized_candidate or not normalized_query:
        return 0
    if normalized_candidate == normalized_query:
        return 100
    if normalized_query in normalized_candidate:
        return 90
    if query_tokens and all(token in candidate_tokens for token in query_tokens):
        return 85
    if query_tokens and all(token in normalized_candidate for token in query_tokens):
        return 75
    if query_tokens and any(token in normalized_candidate for token in query_tokens):
        return 40
    return 0
