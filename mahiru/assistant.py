from __future__ import annotations

import datetime

from features.pc_control import handle_action_request

from .brain import get_mahiru_response
from .companion import companion
from .response_types import MahiruReply, build_plain_reply


EXIT_PHRASES = {
    'bye',
    'goodbye',
    'good night',
    'exit',
    'sleep',
    'go to sleep',
    'you can sleep now',
    'close yourself',
    'close mahiru',
    'you can rest now',
}


def process_user_message(command: str) -> tuple[bool, MahiruReply]:
    lowered = command.lower().strip()
    if not lowered:
        return True, build_plain_reply('')

    welcome_back_line = companion.begin_user_turn(command)

    handled_locally, local_message = companion.handle_local_request(command)
    if handled_locally:
        return True, build_plain_reply(
            local_message or "I'm keeping that in mind for you.",
            expression='caring',
            mood='caring',
            motion='happy_bounce',
            status_text='Companion support',
        )

    action_result = handle_action_request(command)
    if action_result.handled:
        return True, build_plain_reply(
            action_result.message or 'I handled that for you.',
            expression='caring',
            mood='caring',
            motion='happy_bounce',
            status_text='Handled for you',
        )

    if lowered in EXIT_PHRASES:
        return False, build_plain_reply(
            "Take care of yourself, Aakash. I'll be right here waiting for you next time.",
            expression='caring',
            mood='caring',
            motion='idle',
            status_text='Saying goodbye',
        )

    if 'time' in lowered:
        now = datetime.datetime.now().strftime('%I:%M %p')
        return True, build_plain_reply(
            f"It's {now} right now. Please remember to rest when you need to.",
            expression='caring',
            mood='caring',
            motion='speaking',
            status_text='Sharing time',
        )

    reply = get_mahiru_response(command, companion_context=companion.build_context_for_brain())
    if welcome_back_line:
        reply.text = f'{welcome_back_line} {reply.text}'.strip()
        reply.expression = 'happy'
        reply.mood = 'happy'
        reply.motion = 'happy_bounce'
        reply.status_text = 'Welcoming you back'
    return True, reply
