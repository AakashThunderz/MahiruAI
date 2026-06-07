from __future__ import annotations

import os
import re
from contextlib import contextmanager
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import ProxyHandler, build_opener

from .browser_automation import autoplay_spotify, autoplay_youtube


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


DIRECT_URLS = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "discord": "https://discord.com/app",
    "amazon": "https://www.amazon.com",
    "chatgpt": "https://chatgpt.com",
    "openai": "https://openai.com",
    "linkedin": "https://www.linkedin.com",
    "notion": "https://www.notion.so",
}


def open_website(target: str) -> tuple[bool, str]:
    cleaned_target = target.strip().lower()
    url = build_url(cleaned_target)

    try:
        os.startfile(url)
        return True, f"Opening {target} in your browser."
    except OSError as exc:
        return False, f"I could not open {target} in the browser: {exc}"


def open_top_search_result(query: str) -> tuple[bool, str]:
    lucky_url = f"https://www.google.com/search?q={quote_plus(query)}&btnI=I"
    try:
        os.startfile(lucky_url)
        return True, f"Opening the top search result for {query}."
    except OSError as exc:
        return False, f"I could not open the top search result for {query}: {exc}"


def open_youtube_search(query: str) -> tuple[bool, str]:
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    try:
        os.startfile(url)
        return True, f"Opening YouTube results for {query}."
    except OSError as exc:
        return False, f"I could not open YouTube for {query}: {exc}"


def open_top_youtube_result(query: str) -> tuple[bool, str]:
    url = find_first_search_result_url(f"site:youtube.com/watch {query}", preferred_domains=("youtube.com", "www.youtube.com"))
    if url:
        autoplay_url = with_youtube_autoplay(url)
        success, message = autoplay_youtube(autoplay_url)
        if success:
            return success, message
        try:
            os.startfile(autoplay_url)
            return True, f"Opening the top YouTube result for {query}."
        except OSError:
            pass
    return open_youtube_search(query)


def open_spotify_search(query: str) -> tuple[bool, str]:
    browser_url = f"https://open.spotify.com/search/{quote_plus(query)}"

    try:
        os.startfile(browser_url)
        return True, f"Opening Spotify web player for {query}."
    except OSError as exc:
        return False, f"I could not open Spotify for {query}: {exc}"


def open_top_spotify_result(query: str) -> tuple[bool, str]:
    url = find_first_search_result_url(
        f"site:open.spotify.com/track {query}",
        preferred_domains=("open.spotify.com",),
    )
    if url:
        autoplay_url = with_spotify_autoplay_hint(url)
        success, message = autoplay_spotify(autoplay_url)
        if success:
            return success, message
        try:
            os.startfile(autoplay_url)
            return True, f"Opening the top Spotify result for {query}."
        except OSError:
            pass
    return open_spotify_search(query)


def open_platform_search(platform: str, query: str) -> tuple[bool, str]:
    normalized = platform.strip().lower()
    if normalized in {"youtube", "yt"}:
        return open_top_youtube_result(query)
    if normalized == "spotify":
        return open_top_spotify_result(query)
    if normalized == "soundcloud":
        return open_direct_platform_search("https://soundcloud.com/search?q={query}", query, "SoundCloud")
    if normalized == "netflix":
        return open_direct_platform_search("https://www.netflix.com/search?q={query}", query, "Netflix")
    if normalized in {"prime video", "amazon prime"}:
        return open_direct_platform_search("https://www.primevideo.com/search/ref=atv_nb_sr?phrase={query}", query, "Prime Video")
    if normalized == "jiosaavn":
        return open_direct_platform_search("https://www.jiosaavn.com/search/{query}", query, "JioSaavn")
    if normalized == "gaana":
        return open_direct_platform_search("https://gaana.com/search/{query}", query, "Gaana")
    if normalized == "wynk":
        return open_direct_platform_search("https://wynk.in/music/search/{query}", query, "Wynk")
    return open_site_search(normalized, query, normalized.title())


def open_site_search(domain: str, query: str, label: str) -> tuple[bool, str]:
    lucky_url = (
        "https://www.google.com/search?"
        f"q={quote_plus(f'site:{domain} {query}')}&btnI=I"
    )
    try:
        os.startfile(lucky_url)
        return True, f"Opening the top {label} result for {query}."
    except OSError as exc:
        return False, f"I could not open {label} for {query}: {exc}"


def open_direct_platform_search(url_template: str, query: str, label: str) -> tuple[bool, str]:
    url = url_template.format(query=quote_plus(query))
    try:
        os.startfile(url)
        return True, f"Opening {label} for {query}."
    except OSError as exc:
        return False, f"I could not open {label} for {query}: {exc}"


def find_first_search_result_url(query: str, preferred_domains: tuple[str, ...]) -> str | None:
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    opener = build_opener(ProxyHandler({}))
    try:
        with disable_proxy_environment():
            response = opener.open(search_url, timeout=15)
            html = response.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

    for raw_url in re.findall(r'href="(.*?)"', html):
        cleaned = extract_result_target(raw_url)
        if not cleaned:
            continue
        hostname = urlparse(cleaned).netloc.lower()
        if any(domain in hostname for domain in preferred_domains):
            return cleaned
    return None


def extract_result_target(raw_url: str) -> str | None:
    if not raw_url:
        return None
    if raw_url.startswith("//"):
        raw_url = "https:" + raw_url
    if raw_url.startswith("https://duckduckgo.com/l/?"):
        parsed = urlparse(raw_url)
        encoded = parse_qs(parsed.query).get("uddg", [])
        if encoded:
            return unquote(encoded[0])
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        return raw_url
    return None


def with_youtube_autoplay(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query["autoplay"] = ["1"]
    new_query = "&".join(
        f"{key}={quote_plus(value)}"
        for key, values in query.items()
        for value in values
    )
    return parsed._replace(query=new_query).geturl()


def with_spotify_autoplay_hint(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query["autoplay"] = ["1"]
    query["nd"] = ["1"]
    new_query = "&".join(
        f"{key}={quote_plus(value)}"
        for key, values in query.items()
        for value in values
    )
    return parsed._replace(query=new_query).geturl()


@contextmanager
def disable_proxy_environment():
    saved_values = {key: os.environ.pop(key, None) for key in PROXY_ENV_KEYS}
    try:
        yield
    finally:
        for key, value in saved_values.items():
            if value is not None:
                os.environ[key] = value


def build_url(target: str) -> str:
    if target in DIRECT_URLS:
        return DIRECT_URLS[target]

    if target.startswith(("http://", "https://")):
        return target

    if "." in target and " " not in target:
        return f"https://{target}"

    return f"https://www.google.com/search?q={quote_plus(target)}&btnI=I"
