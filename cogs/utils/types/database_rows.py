from typing import TypedDict
import uuid
from datetime import datetime as dt


__all__ = (
    "ScheduledMessageDict",
)


class ScheduledMessageDict(TypedDict):
    id: uuid.UUID
    guild_id: int
    channel_id: int
    user_id: int
    text: str
    timestamp: dt
    repeat: str
