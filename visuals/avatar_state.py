from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AvatarState:
    mode: str = 'idle'
    mood: str = 'neutral'
    expression: str = 'neutral'
    status_text: str = 'Idle and ready'
    emoji: str = '(*^_^*)'
    is_mic_enabled: bool = False
    is_renderer_ready: bool = False


EMOJI_BY_EXPRESSION = {
    'neutral': '(*^_^*)',
    'happy': '(^_^)/',
    'caring': '(^-^*)',
    'shy': '(>_<*)',
    'playful': '(*^o^*)',
    'concerned': '(;_;)',
    'thinking': '(._. )',
    'surprised': '(o_O)!',
    'sleepy': '(-_-) zZ',
}

EMOJI_BY_MODE = {
    'listening': '(o_o )',
    'thinking': '(._. )',
    'speaking': '(^_^)/',
    'busy': '(>_<)',
    'dozing': '(-_-) zZ',
    'error': '(;_;)',
}


def build_avatar_state(
    mode: str,
    *,
    mood: str = 'neutral',
    expression: str = 'neutral',
    status_text: str | None = None,
    is_mic_enabled: bool = False,
    is_renderer_ready: bool = False,
) -> AvatarState:
    return AvatarState(
        mode=mode,
        mood=mood,
        expression=expression,
        status_text=status_text or default_status_text(mode, mood),
        emoji=EMOJI_BY_MODE.get(mode, EMOJI_BY_EXPRESSION.get(expression, EMOJI_BY_EXPRESSION['neutral'])),
        is_mic_enabled=is_mic_enabled,
        is_renderer_ready=is_renderer_ready,
    )


def default_status_text(mode: str, mood: str) -> str:
    if mode == 'listening':
        return 'Listening to you'
    if mode == 'thinking':
        return 'Thinking about a reply'
    if mode == 'speaking':
        return 'Speaking right now'
    if mode == 'busy':
        return 'Handling something for you'
    if mode == 'dozing':
        return 'Dozing softly until you need me'
    if mode == 'error':
        return 'Something went wrong'
    return f'Idle and ready | mood: {mood}'
