from __future__ import annotations

import csv
import ctypes
from ctypes import wintypes
import io
from pathlib import Path
import subprocess

from .file_actions import normalize_name, tokenize_name


SW_MAXIMIZE = 3
SW_MINIMIZE = 6
SW_RESTORE = 9
WM_CLOSE = 0x0010

user32 = ctypes.WinDLL("user32", use_last_error=True)


def control_application_window(target: str, action: str, resolved_command: str | None = None) -> tuple[bool, str]:
    process_infos = find_matching_processes(target, resolved_command)
    if not process_infos:
        return False, f"I could not find a running app matching {target}."

    hwnds = find_window_handles([info["pid"] for info in process_infos])
    if action == "close":
        return close_application(target, process_infos, hwnds)
    if action == "minimize":
        return show_windows(target, hwnds, SW_MINIMIZE, "minimized")
    if action == "maximize":
        return show_windows(target, hwnds, SW_MAXIMIZE, "maximized")
    if action == "restore":
        return show_windows(target, hwnds, SW_RESTORE, "restored")
    if action == "focus":
        return focus_windows(target, hwnds)

    return False, f"I do not know how to {action} {target} yet."


def close_application(target: str, process_infos: list[dict[str, str]], hwnds: list[int]) -> tuple[bool, str]:
    if hwnds:
        for hwnd in hwnds:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return True, f"Closing {target} now."

    closed_any = False
    for info in process_infos:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(info["pid"]), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
            )
            closed_any = True
        except OSError:
            continue

    if closed_any:
        return True, f"Closing {target} now."
    return False, f"I found {target}, but I could not close it."


def show_windows(target: str, hwnds: list[int], show_command: int, action_word: str) -> tuple[bool, str]:
    if not hwnds:
        return False, f"I could not find a visible window for {target}."

    changed = 0
    for hwnd in hwnds:
        user32.ShowWindow(hwnd, show_command)
        changed += 1

    if changed:
        return True, f"I {action_word} {target}."
    return False, f"I found {target}, but I could not change its window state."


def focus_windows(target: str, hwnds: list[int]) -> tuple[bool, str]:
    if not hwnds:
        return False, f"I could not find a visible window for {target}."

    for hwnd in hwnds:
        user32.ShowWindow(hwnd, SW_RESTORE)
        if user32.SetForegroundWindow(hwnd):
            return True, f"Switching to {target} now."

    return False, f"I found {target}, but I could not bring it to the front."


def find_matching_processes(target: str, resolved_command: str | None = None) -> list[dict[str, str]]:
    target_tokens = tokenize_name(target)
    command_stem = extract_command_stem(resolved_command)
    best_matches: list[dict[str, str]] = []
    best_score = -1

    for info in get_running_processes():
        score = score_process_match(info, target_tokens, command_stem)
        if score > best_score:
            best_score = score
            best_matches = [info]
        elif score == best_score and score > 0:
            best_matches.append(info)

    return best_matches if best_score >= 60 else []


def score_process_match(process_info: dict[str, str], target_tokens: list[str], command_stem: str) -> int:
    if not target_tokens and not command_stem:
        return 0

    image_name = process_info["image"].lower()
    image_stem = normalize_name(Path(image_name).stem)
    title_normalized = normalize_name(process_info["title"])

    score = 0
    if command_stem and command_stem == image_stem:
        score = max(score, 100)
    if target_tokens and all(token in image_stem for token in target_tokens):
        score = max(score, 95)
    if target_tokens and all(token in title_normalized for token in target_tokens):
        score = max(score, 85)
    if target_tokens and any(token in image_stem for token in target_tokens):
        score = max(score, 60)
    if target_tokens and any(token in title_normalized for token in target_tokens):
        score = max(score, 60)

    return score


def extract_command_stem(resolved_command: str | None) -> str:
    if not resolved_command:
        return ""
    return normalize_name(Path(resolved_command).stem)


def get_running_processes() -> list[dict[str, str]]:
    try:
        completed = subprocess.run(
            ["tasklist", "/v", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []

    reader = csv.reader(io.StringIO(completed.stdout))
    processes: list[dict[str, str]] = []
    for row in reader:
        if len(row) < 9:
            continue
        try:
            pid = int(row[1])
        except ValueError:
            continue
        processes.append({"image": row[0], "pid": pid, "title": row[8]})
    return processes


def find_window_handles(process_ids: list[int]) -> list[int]:
    pid_set = set(process_ids)
    hwnds: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_windows_proc(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if process_id.value in pid_set:
            hwnds.append(hwnd)
        return True

    user32.EnumWindows(enum_windows_proc, 0)
    return hwnds
