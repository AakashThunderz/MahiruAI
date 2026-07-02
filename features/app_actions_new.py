from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import subprocess
from typing import Iterable

try:
    import winreg
    import win32api
    import win32con
except ImportError:
    winreg = None
    win32api = None
    win32con = None

from .file_actions import normalize_name, score_match, tokenize_name


BUILTIN_APP_COMMANDS = {
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "task manager": "taskmgr.exe",
    "settings": "ms-settings:",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
}
SHORTCUT_EXTENSIONS = {".lnk", ".url", ".exe"}
COMMON_APP_ROOTS = (
    Path(r"C:\Program Files"),
    Path(r"C:\Program Files (x86)"),
)


def open_app(target: str) -> tuple[bool, str]:
    app_name = target.strip().lower()
    command = resolve_app_command(app_name)

    if command is None:
        return False, f"I could not find an installed app named {target}."

    try:
        # Try Windows API approach first (most reliable for non-blocking)
        if win32api and win32con:
            try:
                # Use ShellExecute with SW_SHOW which launches and returns immediately
                print(f"DEBUG app_actions: Using ShellExecute for {target}")
                win32api.ShellExecute(
                    0,  # hwnd
                    "open",  # operation
                    command,  # file
                    "",  # parameters
                    "",  # directory
                    win32con.SW_SHOW  # show window
                )
                print(f"DEBUG app_actions: ShellExecute launched {target}")
                return True, f"Opening {target} now."
            except Exception as exc:
                print(f"DEBUG app_actions: ShellExecute failed, falling back to subprocess: {exc}")
        else:
            print(f"DEBUG app_actions: win32api not available, using subprocess")

        # Fallback to subprocess with proper non-blocking flags
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

        if command.endswith(":"):
            # Launch Windows folder - non-blocking
            print(f"DEBUG app_actions: Launching folder: {command}")
            subprocess.Popen(command, shell=True, creationflags=creation_flags)
        elif looks_like_launchable_path(command):
            # Launch file - non-blocking
            print(f"DEBUG app_actions: Launching file: {command}")
            subprocess.Popen(command, shell=True, creationflags=creation_flags)
        else:
            # Launch executable - non-blocking
            print(f"DEBUG app_actions: Launching app: {command}")
            subprocess.Popen(command, shell=True, creationflags=creation_flags)
        print(f"DEBUG app_actions: Successfully launched {target}")
        return True, f"Opening {target} now."
    except FileNotFoundError:
        print(f"DEBUG app_actions: FileNotFoundError for {target}: {command}")
        return False, f"I found a match for {target}, but it does not seem launchable right now."
    except OSError as exc:
        print(f"DEBUG app_actions: OSError launching {target}: {exc}")
        return False, f"I could not open {target}: {exc}"


def can_resolve_app_name(target: str) -> bool:
    return resolve_app_command(target.strip().lower()) is not None


def get_resolved_app_command(target: str) -> str | None:
    return resolve_app_command(target.strip().lower())


def resolve_app_command(target: str) -> str | None:
    if target in BUILTIN_APP_COMMANDS:
        return BUILTIN_APP_COMMANDS[target]

    best_match = find_best_app_match(target)
    if best_match is not None:
        return best_match

    return None


def find_best_app_match(target: str) -> str | None:
    normalized_target = normalize_name(target)
    target_tokens = tokenize_name(target)
    best_command: str | None = None
    best_score = -1

    for app_name, command in build_app_index().items():
        score = score_app_match(app_name, normalized_target, target_tokens)
        if score > best_score:
            best_score = score
            best_command = command
        elif score == best_score and score > 0:
            best_command = command

    return best_command if best_score >= 70 else None


def score_app_match(app_name: str, normalized_target: str, target_tokens: list[str]) -> int:
    base_score = score_match(app_name, normalized_target)
    app_tokens = tokenize_name(app_name)

    if target_tokens and all(token in app_tokens for token in target_tokens):
        base_score = max(base_score, 95)
    elif target_tokens and all(token in normalize_name(app_name) for token in target_tokens):
        base_score = max(base_score, 80)

    return base_score


@lru_cache(maxsize=1)
def build_app_index() -> dict[str, str]:
    index: dict[str, str] = {}

    for app_name, command in BUILTIN_APP_COMMANDS.items():
        register_app_entry(index, app_name, command)

    for app_name, command in iter_shortcut_entries():
        register_app_entry(index, app_name, command)

    for app_name, command in iter_common_install_entries():
        register_app_entry(index, app_name, command)

    for app_name, command in iter_registry_app_paths():
        register_app_entry(index, app_name, command)

    return index


def register_app_entry(index: dict[str, str], app_name: str, command: str):
    clean_name = app_name.strip()
    if not clean_name or not command:
        return

    names = {clean_name}
    stem = Path(clean_name).stem
    if stem:
        names.add(stem)

    for name in list(names):
        simplified = name.replace("_", " ").replace("-", " ").strip()
        if simplified:
            names.add(simplified)

    for name in names:
        normalized = " ".join(tokenize_name(name))
        if normalized:
            index.setdefault(normalized, command)


def iter_shortcut_entries() -> Iterable[tuple[str, str]]:
    roots = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path.home() / "Desktop",
        Path(os.environ.get("PUBLIC", "")) / "Desktop",
    ]

    for root in roots:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if path.suffix.lower() not in SHORTCUT_EXTENSIONS:
                continue
            yield path.stem, str(path)


def iter_common_install_entries() -> Iterable[tuple[str, str]]:
    seen: set[str] = set()
    for root in COMMON_APP_ROOTS:
        if not root.exists():
            continue

        for path in root.iterdir():
            if not path.is_dir():
                continue

            direct_exe = path / f"{path.name}.exe"
            if direct_exe.exists() and "uninstall" not in direct_exe.name.lower():
                resolved = str(direct_exe)
                if resolved not in seen:
                    seen.add(resolved)
                    yield path.name, resolved
                continue

            for exe_path in path.glob("*.exe"):
                if "uninstall" in exe_path.name.lower():
                    continue
                resolved = str(exe_path)
                if resolved in seen:
                    continue
                seen.add(resolved)
                yield exe_path.stem, resolved
                break


def iter_registry_app_paths() -> Iterable[tuple[str, str]]:
    if winreg is None:
        return []

    hives = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
    views = [0]
    if hasattr(winreg, "KEY_WOW64_32KEY"):
        views.append(winreg.KEY_WOW64_32KEY)
    if hasattr(winreg, "KEY_WOW64_64KEY"):
        views.append(winreg.KEY_WOW64_64KEY)

    entries: list[tuple[str, str]] = []
    for hive in hives:
        for view in views:
            entries.extend(read_registry_app_paths(hive, view))
            entries.extend(read_uninstall_entries(hive, view))
    return entries


def read_registry_app_paths(hive, view_flag: int) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    try:
        key = winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths", 0, winreg.KEY_READ | view_flag)
    except OSError:
        return results

    with key:
        count = winreg.QueryInfoKey(key)[0]
        for index in range(count):
            try:
                subkey_name = winreg.EnumKey(key, index)
                with winreg.OpenKey(key, subkey_name) as subkey:
                    value, _ = winreg.QueryValueEx(subkey, None)
                    results.append((Path(subkey_name).stem, value))
            except OSError:
                continue

    return results


def read_uninstall_entries(hive, view_flag: int) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    uninstall_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    try:
        key = winreg.OpenKey(hive, uninstall_path, 0, winreg.KEY_READ | view_flag)
    except OSError:
        return results

    with key:
        count = winreg.QueryInfoKey(key)[0]
        for index in range(count):
            try:
                subkey_name = winreg.EnumKey(key, index)
                with winreg.OpenKey(key, subkey_name) as subkey:
                    display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                    command = get_uninstall_launch_command(subkey)
                    if display_name and command:
                        results.append((display_name, command))
            except OSError:
                continue

    return results


def get_uninstall_launch_command(subkey) -> str | None:
    for value_name in ("DisplayIcon", "InstallLocation"):
        try:
            value, _ = winreg.QueryValueEx(subkey, value_name)
        except OSError:
            continue

        command = extract_launchable_command(str(value))
        if command:
            return command

    return None


def extract_launchable_command(value: str) -> str | None:
    cleaned = value.strip().strip('"')
    if not cleaned:
        return None

    lowered = cleaned.lower()
    if lowered.endswith('.exe') and 'uninstall' not in lowered and Path(cleaned).exists():
        return cleaned

    if ',' in cleaned:
        maybe_path = cleaned.split(',', 1)[0].strip().strip('"')
        lowered_path = maybe_path.lower()
        if lowered_path.endswith('.exe') and 'uninstall' not in lowered_path and Path(maybe_path).exists():
            return maybe_path

    path_obj = Path(cleaned)
    if path_obj.is_dir():
        direct_exe = path_obj / f"{path_obj.name}.exe"
        if direct_exe.exists() and 'uninstall' not in direct_exe.name.lower():
            return str(direct_exe)
        for exe_path in path_obj.glob('*.exe'):
            if 'uninstall' in exe_path.name.lower():
                continue
            return str(exe_path)

    return None


def looks_like_launchable_path(command: str) -> bool:
    return command.lower().endswith(('.exe', '.lnk', '.url')) and Path(command).exists()
