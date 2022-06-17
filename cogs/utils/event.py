from __future__ import annotations

from typing import List, Optional, Union, TypedDict
from uuid import uuid4, UUID
from enum import Enum, auto
from datetime import datetime as dt, timedelta

from discord.abc import Snowflake
from discord.ext import commands, vbu

from .values import month_list


__all__ = (
    'RepeatTime',
    'Event',
)


class EventGroup(TypedDict):
    day: int
    events: List[Event]


class RepeatTime(Enum):
    none = auto()
    daily = auto()
    weekly = auto()
    monthly = auto()
    yearly = auto()

    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"


class Event:

    __slots__ = (
        '_id',
        'guild_id',
        'user_id',
        'name',
        'month',
        'day',
        'repeat',
    )

    def __init__(
            self,
            *,
            id: Optional[UUID] = None,
            guild_id: int,
            user_id: int,
            name: str,
            month: int,
            day: int,
            repeat: Union[RepeatTime, str]):
        self._id: Optional[UUID] = id
        self.guild_id: int = guild_id
        self.user_id: int = user_id
        self.name: str = name
        self.month: int = month
        self.day: int = day
        self.repeat: RepeatTime = repeat if isinstance(repeat, RepeatTime) else RepeatTime[repeat]

    def __repr__(self) -> str:
        values = ""
        for i in (
                "id",
                "guild_id",
                "user_id",
                "name",
                "month",
                "day",
                "repeat"):
            values += "{0}={1!r}, ".format(i, getattr(self, i))
        return f"{self.__class__.__name__}({values.strip(', ')})"

    @property
    def id(self) -> str:
        if self._id:
            return str(self._id)
        self._id = uuid4()
        return str(self._id)

    @classmethod
    async def fetch_by_id(
            cls,
            id: Union[str, UUID],
            *,
            db: Optional[vbu.Database] = None) -> Optional[Event]:
        """
        Get an event from the database.
        """

        # Get a database connection to use
        _db: vbu.Database
        if db is None:
            _db = await vbu.Database.get_connection()
        else:
            _db = db

        # Get the event
        rows = await _db.call(
            """SELECT * FROM guild_events WHERE id=$1""",
            id,
        )

        # Close the db if we need to
        if db is None:
            await _db.disconnect()

        # And return what we need to
        if rows:
            return cls(**rows[0])
        return None

    @classmethod
    async def fetch_by_name(
            cls,
            guild: Snowflake,
            name: str,
            *,
            db: Optional[vbu.Database] = None) -> Optional[Event]:
        """
        Get an event from the database given a guild ID and a name.

        Parameters
        ----------
        guild : Snowflake
            The guild you want to fetch the event from.
        name : str
            The name of the event (case insensitive).
        db : Optional[vbu.Database]
            An open database connection.

        Returns
        -------
        Optional[Event]
            The event, if one exists.
        """

        # Get a database connection to use
        _db: vbu.Database
        if db is None:
            _db = await vbu.Database.get_connection()
        else:
            _db = db

        # Get the event
        rows = await _db.call(
            """SELECT * FROM guild_events WHERE guild_id=$1 AND LOWER(name)=LOWER($2)""",
            guild.id, name,
        )

        # Close the db if we need to
        if db is None:
            await _db.disconnect()

        # And return what we need to
        if rows:
            return cls(**rows[0])
        return None

    @classmethod
    async def fetch_all_for_guild(
            cls,
            guild: Snowflake,
            *,
            name: Optional[str] = None,
            month: Optional[int] = None,
            db: Optional[vbu.Database] = None) -> List[Event]:
        """
        Get an event from the database given a guild ID and a name.


        Parameters
        ----------
        guild : Snowflake
            The guild that you want to get the events from.
        name : Optional[Optional[str]]
            A name (case insensitive) that you want to fuzzy match for.
        month : Optional[int]
            A month to match by.
        db : Optional[Optional[vbu.Database]]
            An open database connection.

        Returns
        -------
        List[Event]
            A list of events.
        """

        # Get a database connection to use
        _db: vbu.Database
        if db is None:
            _db = await vbu.Database.get_connection()
        else:
            _db = db

        # Get the event
        if name:
            rows = await _db.call(
                r"""SELECT * FROM guild_events WHERE guild_id=$1 AND
                LOWER(name) LIKE ('%' || LOWER($2) || '%')""",
                guild.id, name,
            )
        elif month:
            rows = await _db.call(
                r"""SELECT * FROM guild_events WHERE guild_id=$1 AND
                month=$2""",
                guild.id, month,
            )
        else:
            rows = await _db.call(
                """SELECT * FROM guild_events WHERE guild_id=$1""",
                guild.id,
            )

        # Close the db if we need to
        if db is None:
            await _db.disconnect()

        # And return what we need to
        return [cls(**r) for r in rows]

    @classmethod
    async def convert(cls, ctx: commands.Context, value: str) -> Event:
        """
        A Novus convert method.
        """

        try:
            event = await cls.fetch_by_id(UUID(value))
        except ValueError:
            assert ctx.guild
            event = await cls.fetch_by_name(ctx.guild, value)
        if event is None:
            text = vbu.translation(ctx, "main").gettext("There's no event with the name **{name}**.")
            raise commands.BadArgument(text.format(name=value))
        return event

    async def save(
            self,
            *,
            db: Optional[vbu.Database] = None) -> None:
        """
        Get an event from the database.
        """

        # Get a database connection to use
        _db: vbu.Database
        if db is None:
            _db = await vbu.Database.get_connection()
        else:
            _db = db

        # Get the event
        await _db.call(
            """INSERT INTO guild_events (id, guild_id, user_id, name,
            month, day, repeat) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET guild_id=excluded.guild_id,
            user_id=excluded.user_id, name=excluded.user_id, month=excluded.month,
            day=excluded.day, repeat=excluded.repeat""",
            self.id, self.guild_id, self.user_id, self.name, self.month, self.day,
            self.repeat.name,
        )

        # Close the db if we need to
        if db is None:
            await _db.disconnect()

    async def delete(
            self,
            *,
            db: Optional[vbu.Database] = None) -> None:
        """
        Get an event from the database.
        """

        # Get a database connection to use
        _db: vbu.Database
        if db is None:
            _db = await vbu.Database.get_connection()
        else:
            _db = db

        # Get the event
        await _db.call(
            """DELETE FROM guild_events WHERE id=$1""",
            self.id,
        )
        self._id = None

        # Close the db if we need to
        if db is None:
            await _db.disconnect()

    @staticmethod
    def format_events(
            events: List[Event],
            *,
            include_empty_days: bool = False) -> str:
        """
        Format a list of events into a nice string. This assumes
        that all events are in the same month, and makes no attempts to
        filter otherwise.

        Parameters
        ----------
        events : List[Event]
            A list of events to format.
        include_empty_days : Optional[bool]
            Whether or not to include empty days in the list of events.
        """

        # Sort the events
        events.sort(key=lambda e: (e.month, e.day, e.name,))

        # Group events by day
        grouped_events: List[EventGroup] = []
        current_day = dt(dt.utcnow().year, events[0].month, 1)
        starting_day = current_day
        while starting_day.month == current_day.month:
            grouped_events.append({
                "day": current_day.day,
                "events": list(),
            })
            current_day += timedelta(days=1)

        # Add each of the events into the event list
        for e in events:
            grouped_events[e.day - 1]['events'].append(e)

        # Make into a string
        output_lines: List[str] = []
        for group in grouped_events:

            # See if we want to include this day
            if not group['events'] and not include_empty_days:
                continue

            output_lines.append(f"**{group['day']}**")
            for event in group['events']:
                output_lines.append(f"\N{BULLET} {event.name}")

        # And return
        return "\n".join(output_lines)
