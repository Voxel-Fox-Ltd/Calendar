from __future__ import annotations

from typing import List, Optional, Union, TypedDict
from uuid import uuid4, UUID
from datetime import datetime as dt, timedelta

import discord
from discord.abc import Snowflake
from discord.ext import commands, vbu
import pytz

from .repeat_time import RepeatTime
from .values import DAY_OPTIONS, MONTH_OPTIONS, get_day_suffix


__all__ = (
    'Event',
)


class EventGroup(TypedDict):
    day: int
    events: List[Event]
    weekday: int


class Event:
    """
    A class representing an event.

    Attributes
    ----------
    id : str
        The ID of the event.
    guild_id : int
        The ID of the guild associated with the event.
    user_id : int
        The ID of the user who added the event.
    name : str
        The name of the event.
    timestamp : datetime.datetime
        The time that the event starts. This time will
        always have a timezone attached to it.
    repeat : Optional[RepeatTime]
        How often the event repeats.
    """

    __slots__ = (
        '_id',
        'guild_id',
        'user_id',
        'name',
        '_timestamp',
        'repeat',
    )

    def __init__(
            self,
            *,
            id: Optional[Union[UUID, str]] = None,
            guild_id: int,
            user_id: int,
            name: str,
            timestamp: dt,
            repeat: Optional[Union[RepeatTime, str]] = None):
        """
        Parameters
        ----------
        id : Optional[Optional[Union[UUID, str]]]
            The ID of the event. If not given, one will be generated
            when `.id` is called.
        guild_id : int
            The ID of the guild associated with the event.
        user_id : int
            The ID of the user who added the event.
        name : str
            The name of the event.
        timestamp : dt
            The time that the event starts. This time may or may not
            have a timezone attached to it.
        repeat : Optional[Union[RepeatTime, str]]
            How often the event repeats. If a string is given,
            it will be cast into a `RepeatTime`.

        Raises
        ------
        ValueError
            If the given event ID is not a UUID.
        """

        if id is None:
            self._id = None
        else:
            try:
                self._id: Optional[UUID] = id if isinstance(id, UUID) else UUID(id)
            except ValueError as e:
                raise ValueError("Failed to convert given event ID to a UUID") from e
        self.guild_id: int = guild_id
        self.user_id: int = user_id
        self.name: str = name
        self._timestamp: dt = timestamp
        self.repeat: Optional[RepeatTime]
        if repeat is None:
            self.repeat = None
        elif isinstance(repeat, RepeatTime):
            self.repeat = repeat
        else:
            self.repeat = RepeatTime[repeat]

    def __repr__(self) -> str:
        values = []
        for i in (
                "id",
                "guild_id",
                "user_id",
                "name",
                "timestamp",
                "repeat"):
            values.append("{0}={1!r}".format(i, getattr(self, i)))
        return f"{self.__class__.__name__}({', '.join(values)})"

    @property
    def id(self) -> str:
        if self._id:
            return str(self._id)
        self._id = uuid4()
        return str(self._id)

    @property
    def timestamp(self) -> dt:
        if self._timestamp.tzinfo:
            return self._timestamp
        self._timestamp = self._timestamp.replace(tzinfo=pytz.utc)
        return self._timestamp

    @classmethod
    async def fetch_by_id(
            cls,
            id: Union[str, UUID],
            *,
            db: Optional[vbu.Database] = None) -> Optional[Event]:
        """
        Get an event from the database.

        Parameters
        ----------
        id : Union[str, UUID]
            The event ID to fetch.
        db : Optional[Optional[vbu.Database]]
            A database instance. Will open a new instance
            if none is given.

        Returns
        -------
        Optional[Event]
            The event with that ID, if there is one.
        """

        # Get a database connection to use
        _db: vbu.Database
        if db is None:
            _db = await vbu.Database.get_connection()
        else:
            _db = db

        # Get the event
        rows = await _db.call(
            """
            SELECT
                *
            FROM
                guild_events
            WHERE
                id = $1
            """,
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
        db : Optional[Optional[vbu.Database]]
            A database instance. Will open a new instance
            if none is given.

        Returns
        -------
        Optional[Event]
            The event with that name, if there is one.
        """

        # Get a database connection to use
        _db: vbu.Database
        if db is None:
            _db = await vbu.Database.get_connection()
        else:
            _db = db

        # Get the event
        rows = await _db.call(
            """
            SELECT
                *
            FROM
                guild_events
            WHERE
                guild_id = $1
            AND
                LOWER(name) = LOWER($2)
            """,
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
        month : Optional[Optional[int]]
            A month to match by.
        db : Optional[Optional[vbu.Database]]
            A database instance. Will open a new instance
            if none is given.

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
                """
                SELECT
                    *
                FROM
                    guild_events
                WHERE
                    guild_id = $1
                AND
                    LOWER(name) LIKE '%' || LOWER($2) || '%'
                """,
                guild.id, name,
            )
        elif month:
            rows = await _db.call(
                """
                SELECT
                    *
                FROM
                    guild_events
                WHERE
                    guild_id = $1
                AND
                    EXTRACT(MONTH FROM guild_events.timestamp) = $2
                """,
                guild.id, month,
            )
        else:
            rows = await _db.call(
                """
                SELECT
                    *
                FROM
                    guild_events
                WHERE
                    guild_id = $1
                """,
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
            tra = vbu.translation(ctx, "main")
            # TRANSLATORS: Text appearing in an error message.
            text = tra.gettext("There's no event with the name/ID **{name}**.")
            raise commands.BadArgument(text.format(name=value))
        return event

    async def save(
            self,
            *,
            db: Optional[vbu.Database] = None) -> None:
        """
        Save this event into the database.

        Parameters
        ----------
        db : Optional[Optional[vbu.Database]]
            A database instance. Will open a new instance
            if none is given.
        """

        # Get a database connection to use
        _db: vbu.Database
        if db is None:
            _db = await vbu.Database.get_connection()
        else:
            _db = db

        # Get the event
        await _db.call(
            """
            INSERT INTO
                guild_events
                (
                    id,
                    guild_id,
                    user_id,
                    name,
                    timestamp,
                    repeat
                )
            VALUES
                (
                    $1,  -- id
                    $2,  -- guild_id
                    $3,  -- user_id
                    $4,  -- name
                    $5,  -- timestamp
                    $6  -- repeat
                )
            ON CONFLICT
                (id)
            DO UPDATE
            SET
                guild_id = excluded.guild_id,
                user_id = excluded.user_id,
                name = excluded.user_id,
                timestamp = excluded.timestamp,
                repeat = excluded.repeat
            """,
            self.id, self.guild_id, self.user_id,
            self.name, discord.utils.naive_dt(self.timestamp),
            self.repeat.name if self.repeat else None,
        )

        # Close the db if we need to
        if db is None:
            await _db.disconnect()

    async def delete(
            self,
            *,
            db: Optional[vbu.Database] = None) -> None:
        """
        Delete this instance of the event. Only works if this
        instance has an ID assigned.

        Parameters
        ----------
        db : Optional[Optional[vbu.Database]]
            A database instance. Will open a new instance
            if none is given.
        """

        # Get a database connection to use
        _db: vbu.Database
        if db is None:
            _db = await vbu.Database.get_connection()
        else:
            _db = db

        # Get the event
        await _db.call(
            """
            DELETE FROM
                guild_events
            WHERE
                id = $1
            """,
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
        events.sort(key=lambda e: (e.timestamp, e.name,))

        # Group events by day
        grouped_events: List[EventGroup] = []
        try:
            current_day = dt(dt.utcnow().year, events[0].timestamp.month, 1)
        except IndexError:
            current_day = dt.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        starting_day = current_day
        while starting_day.month == current_day.month:
            grouped_events.append({
                "day": current_day.day,
                "weekday": current_day.weekday(),
                "events": list(),
            })
            current_day += timedelta(days=1)

        # Add each of the events into the event list
        for e in events:
            grouped_events[e.timestamp.day - 1]['events'].append(e)

        # Make into a string
        output_lines: List[str] = [
            f"**Events for {MONTH_OPTIONS[starting_day.month - 1].name}**",
        ]
        for group in grouped_events:

            # See if we want to include this day
            if not group['events'] and not include_empty_days:
                continue

            output_lines.append(
                (
                    f"**{DAY_OPTIONS[group['weekday']].name} "
                    f"{group['day']}{get_day_suffix(group['day'])}**"
                )
            )
            for event in group['events']:
                output_lines.append(f"\u2022 {event.name}")

        # And return
        return "\n".join(output_lines)
