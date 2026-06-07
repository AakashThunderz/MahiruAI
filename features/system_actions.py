from __future__ import annotations

import ctypes
import time
from datetime import datetime
from pathlib import Path

from PIL import ImageGrab


VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_LWIN = 0x5B
VK_D = 0x44
VK_C = 0x43
VK_V = 0x56
VK_X = 0x58
VK_A = 0x41
KEYEVENTF_KEYUP = 0x0002

user32 = ctypes.WinDLL("user32", use_last_error=True)

SCREENSHOT_DIR = Path.home() / 'Pictures' / 'Screenshots'

def perform_system_action(action: str, amount: int | None = None, target: str = '') -> tuple[bool, str]:
    if action == "mute":
        press_virtual_key(VK_VOLUME_MUTE)
        return True, "Toggling mute now."

    if action == "volume_up":
        repeat = amount if amount and amount > 0 else 5
        repeat_virtual_key(VK_VOLUME_UP, repeat)
        return True, f"Turning the volume up a little."

    if action == "volume_down":
        repeat = amount if amount and amount > 0 else 5
        repeat_virtual_key(VK_VOLUME_DOWN, repeat)
        return True, f"Turning the volume down a little."

    if action == "show_desktop":
        hold_combo(VK_LWIN, VK_D)
        return True, "Showing your desktop now."

    if action == 'copy':
        hold_combo(0x11, VK_C)
        return True, "Copying the current selection."

    if action == 'paste':
        hold_combo(0x11, VK_V)
        return True, "Pasting now."

    if action == 'cut':
        hold_combo(0x11, VK_X)
        return True, "Cutting the current selection."

    if action == 'select_all':
        hold_combo(0x11, VK_A)
        return True, "Selecting everything in the active window."

    if action == 'lock_screen':
        if user32.LockWorkStation():
            return True, "Locking your screen now."
        return False, "I tried to lock the screen, but Windows did not allow it."

    if action == 'screenshot':
        return take_screenshot()

    if action == 'type_text':
        if not target.strip():
            return False, "I need some text to type for you."
        send_text(target)
        return True, "Typing that for you now."

    return False, f"I do not know how to handle the system action {action} yet."


def repeat_virtual_key(virtual_key: int, repeat: int):
    for _ in range(max(1, repeat)):
        press_virtual_key(virtual_key)
        time.sleep(0.02)


def press_virtual_key(virtual_key: int):
    user32.keybd_event(virtual_key, 0, 0, 0)
    user32.keybd_event(virtual_key, 0, KEYEVENTF_KEYUP, 0)


def hold_combo(modifier_key: int, action_key: int):
    user32.keybd_event(modifier_key, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(action_key, 0, 0, 0)
    user32.keybd_event(action_key, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.02)
    user32.keybd_event(modifier_key, 0, KEYEVENTF_KEYUP, 0)


def send_text(text: str):
    for character in text:
        user32.SendMessageW(user32.GetForegroundWindow(), 0x0102, ord(character), 0)
        time.sleep(0.005)


def take_screenshot() -> tuple[bool, str]:
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        image = ImageGrab.grab(all_screens=True)
        output_path = SCREENSHOT_DIR / f'mahiru_screenshot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        image.save(output_path)
        return True, f"I saved a screenshot to {output_path}."
    except Exception as exc:
        return False, f"I could not take a screenshot: {exc}"
