from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BRAVE_BINARY = Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe")
BRAVE_USER_DATA = Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/User Data"
PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)


def autoplay_youtube(url: str) -> tuple[bool, str]:
    try:
        with brave_driver() as driver:
            driver.get(url)
            wait = WebDriverWait(driver, 20)
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            wait.until(lambda d: d.execute_script("return !!document.querySelector('video')"))
            driver.execute_script(
                """
                const video = document.querySelector('video');
                if (video) {
                    video.muted = false;
                    const result = video.play();
                    if (result && typeof result.catch === 'function') {
                        result.catch(() => {});
                    }
                }
                """
            )
            time.sleep(3)
        return True, "Opening and auto-playing YouTube now."
    except Exception as exc:
        return False, f"I could not auto-play YouTube: {exc}"


def autoplay_spotify(url: str) -> tuple[bool, str]:
    try:
        with brave_driver() as driver:
            driver.get(url)
            wait = WebDriverWait(driver, 25)
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

            button = first_clickable(
                driver,
                wait,
                [
                    (By.CSS_SELECTOR, "button[data-testid='play-button']"),
                    (By.CSS_SELECTOR, "button[aria-label='Play']"),
                    (By.CSS_SELECTOR, "button[aria-label='Pause']"),
                    (By.XPATH, "//button[contains(@aria-label, 'Play')]"),
                ],
            )

            if button is None:
                return False, "I opened Spotify, but I could not find the play button. Make sure the web player is logged in."

            driver.execute_script("arguments[0].click();", button)
            time.sleep(3)
        return True, "Opening and auto-playing Spotify now."
    except Exception as exc:
        return False, f"I could not auto-play Spotify: {exc}"


def first_clickable(driver, wait: WebDriverWait, selectors: list[tuple[str, str]]):
    for by, selector in selectors:
        try:
            return wait.until(EC.element_to_be_clickable((by, selector)))
        except TimeoutException:
            continue
        except WebDriverException:
            continue
    return None


@contextmanager
def brave_driver():
    if not BRAVE_BINARY.exists():
        raise RuntimeError(f"Brave browser was not found at {BRAVE_BINARY}")

    options = ChromeOptions()
    options.binary_location = str(BRAVE_BINARY)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    if BRAVE_USER_DATA.exists():
        options.add_argument(f"--user-data-dir={BRAVE_USER_DATA}")
        options.add_argument("--profile-directory=Default")

    with disable_proxy_environment():
        driver = webdriver.Chrome(service=Service(), options=options)
    try:
        yield driver
    finally:
        try:
            driver.quit()
        except Exception:
            pass


@contextmanager
def disable_proxy_environment():
    saved_values = {key: os.environ.pop(key, None) for key in PROXY_ENV_KEYS}
    try:
        yield
    finally:
        for key, value in saved_values.items():
            if value is not None:
                os.environ[key] = value
