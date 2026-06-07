from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


COMPANION_STATE_PATH = Path(__file__).resolve().parent.parent / '.cache' / 'companion_state.json'
WELCOME_BACK_AFTER_MINUTES = 12
DOZING_AFTER_MINUTES = 6


@dataclass(slots=True)
class Reminder:
    text: str
    due_at: str
    created_at: str
    delivered: bool = False


@dataclass(slots=True)
class CompanionState:
    favorites: dict[str, str] = field(default_factory=dict)
    likes: list[str] = field(default_factory=list)
    dislikes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    reminders: list[Reminder] = field(default_factory=list)
    last_seen_at: str | None = None
    last_daily_greeting: str | None = None


class MahiruCompanion:
    def __init__(self, state_path: Path = COMPANION_STATE_PATH):
        self.state_path = state_path
        self.state = self._load_state()
        self.last_interaction_at = self._parse_datetime(self.state.last_seen_at) or datetime.now()

    def _load_state(self) -> CompanionState:
        if not self.state_path.exists():
            return CompanionState()

        try:
            payload = json.loads(self.state_path.read_text(encoding='utf-8'))
        except Exception:
            return CompanionState()

        reminders = [
            Reminder(
                text=str(entry.get('text', '')).strip(),
                due_at=str(entry.get('due_at', '')),
                created_at=str(entry.get('created_at', '')),
                delivered=bool(entry.get('delivered', False)),
            )
            for entry in payload.get('reminders', [])
            if str(entry.get('text', '')).strip()
        ]

        return CompanionState(
            favorites={str(key): str(value) for key, value in payload.get('favorites', {}).items()},
            likes=[str(item) for item in payload.get('likes', []) if str(item).strip()],
            dislikes=[str(item) for item in payload.get('dislikes', []) if str(item).strip()],
            notes=[str(item) for item in payload.get('notes', []) if str(item).strip()],
            reminders=reminders,
            last_seen_at=payload.get('last_seen_at'),
            last_daily_greeting=payload.get('last_daily_greeting'),
        )

    def save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self.state)
        self.state_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')

    def begin_user_turn(self, user_message: str) -> str | None:
        now = datetime.now()
        elapsed = now - self.last_interaction_at
        self.last_interaction_at = now
        self.state.last_seen_at = now.isoformat()
        self.capture_memories(user_message)
        self.save()

        if elapsed >= timedelta(minutes=WELCOME_BACK_AFTER_MINUTES):
            return self.build_welcome_back_line(now)
        return None

    def capture_memories(self, user_message: str):
        lowered = user_message.lower().strip()

        favorite_match = re.search(r'\bmy favorite\s+([a-zA-Z0-9 _-]{2,30})\s+is\s+(.+)', user_message, re.IGNORECASE)
        if favorite_match:
            category = favorite_match.group(1).strip().lower().replace(' ', '_')
            value = self._normalize_fact_value(favorite_match.group(2))
            if value:
                self.state.favorites[category] = value

        for pattern, bucket_name in (
            (r'\bi (?:really )?(?:like|love)\s+(.+)', 'likes'),
            (r'\bi (?:really )?(?:dislike|hate)\s+(.+)', 'dislikes'),
        ):
            match = re.search(pattern, user_message, re.IGNORECASE)
            if not match:
                continue
            value = self._normalize_fact_value(match.group(1))
            if not value:
                continue
            bucket = getattr(self.state, bucket_name)
            if value.lower() not in {entry.lower() for entry in bucket}:
                bucket.append(value)
                del bucket[8:]

        if any(phrase in lowered for phrase in ('remember this', 'keep this in mind')):
            note_value = self._normalize_fact_value(user_message)
            if note_value and note_value.lower() not in {entry.lower() for entry in self.state.notes}:
                self.state.notes.append(note_value)
                del self.state.notes[8:]

    def build_context_for_brain(self) -> str:
        lines: list[str] = []
        if self.state.favorites:
            favorite_parts = [f"{key.replace('_', ' ')}: {value}" for key, value in sorted(self.state.favorites.items())]
            lines.append('Known favorites -> ' + '; '.join(favorite_parts[:6]))
        if self.state.likes:
            lines.append('Things Aakash likes -> ' + '; '.join(self.state.likes[:5]))
        if self.state.dislikes:
            lines.append('Things Aakash dislikes -> ' + '; '.join(self.state.dislikes[:5]))
        if self.state.notes:
            lines.append('Important notes -> ' + '; '.join(self.state.notes[:4]))
        return '\n'.join(lines)

    def handle_local_request(self, user_message: str) -> tuple[bool, str | None]:
        lowered = user_message.lower().strip()

        if lowered in {'what do you remember about me', 'what do you remember', 'tell me what you remember about me'}:
            return True, self.build_memory_summary()

        if lowered in {'show my reminders', 'show reminders', 'what are my reminders', 'list reminders'}:
            return True, self.build_reminder_summary()

        if lowered in {'clear reminders', 'delete reminders'}:
            self.state.reminders.clear()
            self.save()
            return True, "I cleared your reminders. We can set new ones whenever you want."

        reminder_message = self.try_create_reminder(user_message)
        if reminder_message:
            return True, reminder_message

        return False, None

    def try_create_reminder(self, user_message: str) -> str | None:
        patterns = [
            r'remind me to\s+(.+?)\s+in\s+(\d+)\s+(minute|minutes|hour|hours)',
            r'remind me about\s+(.+?)\s+in\s+(\d+)\s+(minute|minutes|hour|hours)',
            r'remind me in\s+(\d+)\s+(minute|minutes|hour|hours)\s+to\s+(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, user_message, re.IGNORECASE)
            if not match:
                continue

            if pattern.startswith('remind me in'):
                amount = int(match.group(1))
                unit = match.group(2).lower()
                reminder_text = self._normalize_fact_value(match.group(3))
            else:
                reminder_text = self._normalize_fact_value(match.group(1))
                amount = int(match.group(2))
                unit = match.group(3).lower()

            if not reminder_text:
                return None

            delta = timedelta(hours=amount) if unit.startswith('hour') else timedelta(minutes=amount)
            due_at = datetime.now() + delta
            self.state.reminders.append(
                Reminder(
                    text=reminder_text,
                    due_at=due_at.isoformat(),
                    created_at=datetime.now().isoformat(),
                )
            )
            self.state.reminders.sort(key=lambda item: item.due_at)
            self.save()
            return f"Okay. I'll remind you to {reminder_text} at {due_at.strftime('%I:%M %p')}."

        return None

    def consume_due_reminders(self) -> list[str]:
        now = datetime.now()
        due_messages: list[str] = []

        for reminder in self.state.reminders:
            if reminder.delivered:
                continue
            due_at = self._parse_datetime(reminder.due_at)
            if due_at is None or due_at > now:
                continue
            reminder.delivered = True
            due_messages.append(f"Reminder: {reminder.text}. I did not want you to forget.")

        if due_messages:
            self.save()
        return due_messages

    def get_presence_state(self) -> tuple[str, str, str]:
        elapsed = datetime.now() - self.last_interaction_at
        if elapsed >= timedelta(minutes=DOZING_AFTER_MINUTES):
            return 'dozing', 'sleepy', 'Dozing softly until you need me'
        return 'idle', 'neutral', 'Idle and ready'

    def build_startup_greeting(self) -> str:
        now = datetime.now()
        today = now.date().isoformat()
        time_greeting = self._time_based_greeting(now)

        favorite_game = self.state.favorites.get('game')
        if self.state.last_daily_greeting != today:
            self.state.last_daily_greeting = today
            self.state.last_seen_at = now.isoformat()
            self.last_interaction_at = now
            self.save()
            if favorite_game:
                return f"{time_greeting}, Aakash. I still remember that your favorite game is {favorite_game}."
            return f"{time_greeting}, Aakash. I'm here and ready to spend time with you."

        return f"Welcome back, Aakash. I'm right here with you."

    def build_memory_summary(self) -> str:
        parts: list[str] = []
        if self.state.favorites:
            favorites = ', '.join(f"{key.replace('_', ' ')}: {value}" for key, value in sorted(self.state.favorites.items()))
            parts.append(f"I remember these favorites: {favorites}.")
        if self.state.likes:
            parts.append('You seem to like ' + ', '.join(self.state.likes[:5]) + '.')
        if self.state.dislikes:
            parts.append('You do not seem to enjoy ' + ', '.join(self.state.dislikes[:5]) + '.')
        if self.state.notes:
            parts.append('I kept these notes in mind: ' + '; '.join(self.state.notes[:4]) + '.')
        if not parts:
            return "I have not learned much yet, but I'm ready to remember the things that matter to you."
        return ' '.join(parts)

    def build_reminder_summary(self) -> str:
        active = [entry for entry in self.state.reminders if not entry.delivered]
        if not active:
            return "You do not have any active reminders right now."

        lines = []
        for reminder in active[:6]:
            due_at = self._parse_datetime(reminder.due_at)
            when = due_at.strftime('%I:%M %p') if due_at else 'an unknown time'
            lines.append(f"{reminder.text} at {when}")
        return 'These reminders are waiting: ' + '; '.join(lines) + '.'

    def build_welcome_back_line(self, now: datetime) -> str:
        return f"Welcome back, Aakash. {self._time_based_greeting(now)}."

    def _time_based_greeting(self, now: datetime) -> str:
        hour = now.hour
        if 5 <= hour < 12:
            return 'Good morning'
        if 12 <= hour < 17:
            return 'Good afternoon'
        if 17 <= hour < 22:
            return 'Good evening'
        return 'It is getting late'

    def _normalize_fact_value(self, value: str) -> str:
        cleaned = re.sub(r'\s+', ' ', value).strip(" .!?,")
        return cleaned[:120]

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None


companion = MahiruCompanion()
