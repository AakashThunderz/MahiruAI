import json
import re

from .online_providers import request_online_response
from .response_types import MahiruReply, build_plain_reply

ALLOWED_EXPRESSIONS = {
    'neutral', 'happy', 'caring', 'shy', 'playful', 'concerned', 'thinking', 'surprised', 'sleepy'
}
ALLOWED_MOTIONS = {
    'idle', 'listening', 'thinking', 'speaking', 'tap_body', 'flick', 'flick_down', 'happy_bounce'
}


def get_mahiru_response(user_message: str, *, companion_context: str = '') -> MahiruReply:
    """Ask the language model for Mahiru's structured reply."""
    try:
        raw_content = request_online_response(user_message, companion_context=companion_context)
        return parse_mahiru_response(raw_content)
    except Exception as exc:
        print('Brain error:', exc)
        return build_plain_reply(
            "I'm sorry, Aakash. Something went a little wrong. Could you tell me that again?",
            expression='concerned',
            mood='concerned',
            motion='thinking',
            status_text='Recovering reply',
        )


def parse_mahiru_response(raw_content: str) -> MahiruReply:
    payload = try_parse_json_object(raw_content)
    if payload is None:
        return build_plain_reply(
            sanitize_spoken_text(raw_content),
            expression='neutral',
            mood='neutral',
            motion='speaking',
            status_text='Soft reply',
        )

    text = sanitize_spoken_text(str(payload.get('text', '')).strip())
    expression = normalize_expression(str(payload.get('expression', 'neutral')).strip())
    mood = normalize_expression(str(payload.get('mood', expression)).strip())
    motion = normalize_motion(str(payload.get('motion', 'speaking')).strip())
    status_text = str(payload.get('status_text', '')).strip() or default_status_text_for_expression(expression)

    if not text:
        text = "I'm here with you, Aakash."

    return MahiruReply(
        text=text,
        expression=expression,
        mood=mood,
        motion=motion,
        status_text=status_text,
    )


def try_parse_json_object(raw_content: str) -> dict | None:
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def sanitize_spoken_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text.strip())


def normalize_expression(value: str) -> str:
    cleaned = value.lower().replace(' ', '_')
    return cleaned if cleaned in ALLOWED_EXPRESSIONS else 'neutral'


def normalize_motion(value: str) -> str:
    cleaned = value.lower().replace(' ', '_')
    return cleaned if cleaned in ALLOWED_MOTIONS else 'speaking'


def default_status_text_for_expression(expression: str) -> str:
    mapping = {
        'happy': 'Feeling happy',
        'caring': 'Being gentle',
        'shy': 'Feeling shy',
        'playful': 'Feeling playful',
        'concerned': 'Feeling concerned',
        'thinking': 'Thinking softly',
        'surprised': 'A little surprised',
        'sleepy': 'Feeling sleepy',
        'neutral': 'Soft reply',
    }
    return mapping.get(expression, 'Soft reply')
