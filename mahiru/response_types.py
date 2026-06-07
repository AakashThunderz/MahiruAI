from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MahiruReply:
    text: str
    expression: str = 'neutral'
    mood: str = 'neutral'
    motion: str = 'idle'
    status_text: str | None = None


def build_plain_reply(text: str, *, expression: str = 'neutral', mood: str = 'neutral', motion: str = 'idle', status_text: str | None = None) -> MahiruReply:
    return MahiruReply(
        text=text,
        expression=expression,
        mood=mood,
        motion=motion,
        status_text=status_text,
        model="openai/gpt-oss-20b"                 

 userinput = input("Prompt: ")
    )




   