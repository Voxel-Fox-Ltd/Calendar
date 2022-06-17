from typing import List, Tuple, Optional, Union
from datetime import datetime as dt, timedelta
import uuid

import discord
from discord.ext import commands, tasks, vbu
import pytz
import pytimeparse

from cogs.utils.types import GuildContext, ScheduledMessageDict
from cogs.utils.values import MONTH_OPTIONS, REPEAT_OPTIONS_WITH_NONE, TIMEZONE_OPTIONS


class MessageScheduler(vbu.Cog[vbu.Bot]):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sent_ids: List[Tuple[dt, uuid.UUID]] = list()
        self.message_schedule_send_loop.start()

    def cog_unload(self) -> None:
        self.message_schedule_send_loop.stop()
        return super().cog_unload()

    async def add_repeating_events(
            self,
            db: vbu.Database,
            filter_timestamp: dt,
            filtered_ids: list):
        """
        Add new events to the database that are set to repeat.
        """

        # Add daily
        await db.call(
            """
            INSERT INTO
                scheduled_messages
                (
                    id,
                    guild_id,
                    channel_id,
                    user_id,
                    text,
                    timestamp,
                    repeat
                )
            SELECT
                uuid_generate_v4(),
                guild_id,
                channel_id,
                user_id,
                text,
                timestamp + INTERVAL '1 day',
                repeat
            FROM
                scheduled_messages
            WHERE
                timestamp >= $1
            AND
                timestamp < $2
            AND
                repeat = 'daily'
            AND
                NOT (id = ANY($3::UUID[]))
            """,
            filter_timestamp, filter_timestamp + timedelta(minutes=1), [i[1] for i in filtered_ids],
        )

        # Add monthly
        await db.call(
            """
            INSERT INTO
                scheduled_messages
                (
                    id,
                    guild_id,
                    channel_id,
                    user_id,
                    text,
                    timestamp,
                    repeat
                )
            SELECT
                uuid_generate_v4(),
                guild_id,
                channel_id,
                user_id,
                text,
                timestamp + INTERVAL '1 month',
                repeat
            FROM
                scheduled_messages
            WHERE
                timestamp >= $1
            AND
                timestamp < $2
            AND
                repeat = 'monthly'
            AND
                NOT (id = ANY($3::UUID[]))
            """,
            filter_timestamp, filter_timestamp + timedelta(minutes=1), [i[1] for i in filtered_ids],
        )

        # Add yearly
        await db.call(
            """
            INSERT INTO
                scheduled_messages
                (
                    id,
                    guild_id,
                    channel_id,
                    user_id,
                    text,
                    timestamp,
                    repeat
                )
            SELECT
                uuid_generate_v4(),
                guild_id,
                channel_id,
                user_id,
                text,
                timestamp + INTERVAL '1 year',
                repeat
            FROM
                scheduled_messages
            WHERE
                timestamp >= $1
            AND
                timestamp < $2
            AND
                repeat = 'yearly'
            AND
                NOT (id = ANY($3::UUID[]))
            """,
            filter_timestamp, filter_timestamp + timedelta(minutes=1), [i[1] for i in filtered_ids],
        )

    @tasks.loop(seconds=10)
    async def message_schedule_send_loop(self):
        """
        Send the scheduled messages.
        """

        # Get our scheduled messages to be sent
        self.logger.info("Looking for scheduled messages")
        now = dt.utcnow().replace(second=0, microsecond=0)
        async with vbu.Database() as db:
            messages: List[ScheduledMessageDict] = await db.call(
                """
                SELECT
                    *
                FROM
                    scheduled_messages
                WHERE
                    timestamp >= $1
                AND
                    timestamp < $2
                AND
                    NOT (id = ANY($3::UUID[]))
                """,
                now, now + timedelta(minutes=1), [i[1] for i in self.sent_ids],
            )
            await self.add_repeating_events(db, now, self.sent_ids)

        # Send them
        for i in messages:
            channel = self.bot.get_partial_messageable(
                i['channel_id'],
                type=discord.ChannelType.text,
            )
            try:
                await channel.send(
                    i['text'],
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                self.logger.info("Sent message '%s' to %s" % (i['text'], channel.id))
            except discord.HTTPException:
                self.logger.info("Failed to send message '%s' to %s" % (i['text'], channel.id))

        # Cache the IDs so as to not resend
        for i in messages:
            new_item = (
                dt.utcnow(),
                i['id'],
            )
            self.sent_ids.append(new_item)

        # And delete old IDs
        self.sent_ids = [
            i
            for i in self.sent_ids
            if i[0] > dt.utcnow() - timedelta(minutes=2)
        ]

    @message_schedule_send_loop.before_loop
    async def before_message_schedule_send_loop(self):
        await self.bot.wait_until_ready()

    @commands.group(
        application_command_meta=commands.ApplicationCommandMeta(
            guild_only=True,
            permissions=discord.Permissions(manage_guild=True),
        ),
    )
    async def schedule(self, _):
        ...

    @schedule.group(
        name="add",
        application_command_meta=commands.ApplicationCommandMeta(),
    )
    async def schedule_add(self, _):
        ...

    @schedule_add.command(
        name="in",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="message",
                    description="The message text that you want to schedule.",
                    type=discord.ApplicationCommandOptionType.string,
                ),
                discord.ApplicationCommandOption(
                    name="future",
                    description="How far in the future you want the message to be sent (eg \"1 hour 5 minutes\").",
                    type=discord.ApplicationCommandOptionType.string,
                ),
                discord.ApplicationCommandOption(
                    name="channel",
                    description="The channel you want to send the message in.",
                    type=discord.ApplicationCommandOptionType.channel,
                    channel_types=[
                        discord.ChannelType.text,
                    ],
                ),
            ],
        ),
    )
    async def schedule_add_in(
            self,
            ctx: GuildContext,
            message: str,
            future: str,
            channel: discord.TextChannel):
        """
        Schedule a message to be sent in a given channel at a point in the future.
        """

        # Make sure it's a valid time
        future_seconds = pytimeparse.parse(future)
        if future_seconds is None or future_seconds < 0:
            return await ctx.interaction.response.send_message("Your given time is invalid.")

        # Make an actual timestamp
        send_time = dt.utcnow() + timedelta(seconds=future_seconds)

        # And save
        await self.save_scheduled_message(ctx, message, send_time, channel)

    @schedule_add.command(
        name="at",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="message",
                    description="The message text that you want to schedule.",
                    type=discord.ApplicationCommandOptionType.string,
                ),
                discord.ApplicationCommandOption(
                    name="month",
                    description="The month that you want the message to be sent.",
                    type=discord.ApplicationCommandOptionType.integer,
                    choices=list(MONTH_OPTIONS),
                ),
                discord.ApplicationCommandOption(
                    name="day",
                    description="The day in the month that you want the message to be sent.",
                    type=discord.ApplicationCommandOptionType.integer,
                    min_value=1,
                    max_value=31,
                ),
                discord.ApplicationCommandOption(
                    name="hour",
                    description="The hour that you want the message to be sent.",
                    type=discord.ApplicationCommandOptionType.integer,
                    min_value=0,
                    max_value=24,
                ),
                discord.ApplicationCommandOption(
                    name="minute",
                    description="The minute that you want the message to be sent.",
                    type=discord.ApplicationCommandOptionType.integer,
                    min_value=0,
                    max_value=59,
                ),
                discord.ApplicationCommandOption(
                    name="channel",
                    description="The channel you want to send the message in. Defaults to here.",
                    type=discord.ApplicationCommandOptionType.channel,
                    channel_types=[
                        discord.ChannelType.text,
                    ],
                ),
                discord.ApplicationCommandOption(
                    name="timezone",
                    description="The timezone that you're giving a time in. Defaults to UTC.",
                    type=discord.ApplicationCommandOptionType.string,
                    choices=list(TIMEZONE_OPTIONS),
                    required=False,
                ),
            ],
        ),
    )
    async def schedule_add_at(
            self,
            ctx: GuildContext,
            message: str,
            month: int,
            day: int,
            hour: int,
            minute: int,
            channel: discord.TextChannel,
            timezone: str = "UTC"):
        """
        Schedule a message to be sent in a given channel at a specific time.
        """

        # Build a time
        now = dt.utcnow().astimezone(pytz.timezone(timezone))
        send_time = dt(
            year=now.year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            tzinfo=pytz.timezone(timezone),
        )
        if send_time < now:
            send_time = send_time.replace(year=send_time.year + 1)

        # And save
        await self.save_scheduled_message(ctx, message, send_time, channel)

    async def save_scheduled_message(
            self,
            ctx: GuildContext,
            message: str,
            send_time: dt,
            channel: discord.TextChannel):
        ...

        # Save it to db
        await ctx.interaction.response.defer()
        async with vbu.Database() as db:
            created_rows: List[ScheduledMessageDict] = await db.call(
                """
                INSERT INTO
                    scheduled_messages
                    (
                        id,
                        guild_id,
                        channel_id,
                        user_id,
                        text,
                        timestamp,
                        repeat
                    )
                VALUES
                    (
                        uuid_generate_v4(),  -- id
                        $1,  -- guild_id
                        $2,  -- channel_id
                        $3,  -- user_id
                        $4,  -- text
                        $5,  -- timestamp
                        NULL  -- repeat
                    )
                RETURNING
                    id
                """,
                ctx.guild.id, channel.id, ctx.author.id, message,
                discord.utils.naive_dt(send_time),
            )
        created = created_rows[0]

        # Tell the user it's done
        future = discord.utils.format_dt(send_time, style="R")
        response = (
            f"Scheduled your message to be sent into {channel.mention} "
            f"{future} with ID `{created['id']!s}` :)"
        )
        await ctx.interaction.followup.send(response)

    @schedule.command(
        name="repeat",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="id",
                    description="The message that you want to set to repeat.",
                    type=discord.ApplicationCommandOptionType.string,
                    autocomplete=True,
                ),
                discord.ApplicationCommandOption(
                    name="repeat",
                    description="How often the event should repeat.",
                    type=discord.ApplicationCommandOptionType.string,
                    choices=list(REPEAT_OPTIONS_WITH_NONE),
                ),
            ],
        ),
    )
    async def schedule_repeat(
            self,
            ctx: GuildContext,
            id: str,
            repeat: str):
        """
        Set an event to repeat.
        """

        # See if the message is a UUID
        message_is_id = True
        try:
            uuid.UUID(id)
        except ValueError:
            message_is_id = False

        # Only edit if we have an ID
        if not message_is_id:
            return await ctx.interaction.response.send_message(
                "I can only edit scheduled messages by their ID."
            )

        # Alright, time to edit
        await ctx.interaction.response.defer()
        async with vbu.Database() as db:
            await db.call(
                """
                UPDATE
                    scheduled_messages
                SET
                    repeat=$2
                WHERE
                    id=$1
                """,
                id, repeat if repeat != "none" else None,
            )

        # And done
        return await ctx.interaction.followup.send("Event updated :)")

    @schedule.command(
        name="delete",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="id",
                    description="The message that you want to delete.",
                    type=discord.ApplicationCommandOptionType.string,
                    autocomplete=True,
                ),
            ],
            guild_only=True,
        ),
    )
    async def schedule_delete(
            self,
            ctx: GuildContext,
            id: Optional[str]):
        """
        Delete a scheduled message.
        """

        # See if the message is a UUID
        message_is_id = True
        try:
            uuid.UUID(id)
        except ValueError:
            message_is_id = False

        # Only delete if we have an ID
        if not message_is_id:
            return await ctx.interaction.response.send_message(
                "I can only delete scheduled messages by their ID."
            )

        # Delete from database
        await ctx.interaction.response.defer()
        async with vbu.Database() as db:
            await db.call("""
                DELETE FROM
                    scheduled_messages
                WHERE
                    id=$1
                AND
                    guild_id=$2
                RETURNING
                    *
                """,
                id, ctx.guild.id,
            )

        # And done
        return await ctx.interaction.followup.send("Deleted scheduled message :)")

    @schedule_delete.autocomplete
    @schedule_repeat.autocomplete
    async def schedule_delete_message_autocomplete(
            self,
            ctx: GuildContext,
            interaction: discord.Interaction):
        """
        Return the scheduled messages.
        """

        # Get all the data
        async with vbu.Database() as db:
            messages: List[ScheduledMessageDict] = await db.call(
                """
                SELECT
                    *
                FROM
                    scheduled_messages
                WHERE
                    guild_id=$1
                ORDER BY
                    timestamp DESC
                """,
                ctx.guild.id,
            )

        # Format into a nice string
        send_messages: List[discord.ApplicationCommandOptionChoice] = []
        for i in messages:
            channel: Optional[discord.TextChannel]
            channel = self.bot.get_channel(i['channel_id'])  # type: ignore - will only be a text channel
            name = f"#{channel.name if channel else i['channel_id']}: {i['text']}"
            if len(name) > 100:
                name = name[:-97] + "..."
            send_messages.append(discord.ApplicationCommandOptionChoice(
                name=name,
                value=str(i['id'])
            ))

        # And send
        return await interaction.response.send_autocomplete(send_messages)

    @schedule.command(
        name="list",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="month",
                    description="The month that you want to look at.",
                    type=discord.ApplicationCommandOptionType.integer,
                    choices=list(MONTH_OPTIONS),
                    required=False,
                ),
            ],
        ),
    )
    async def schedule_list(
            self,
            ctx: Union[GuildContext, discord.Interaction],
            month: Optional[int] = None):
        """
        Check a list of scheduled messages.
        """

        # See if a month was specified
        if month is None:
            return await self.send_schedule_list_message(ctx)

        # Get times
        now = dt.utcnow()
        now_minus_one_month = now.replace(
            year=now.year if now.month > 1 else now.year - 1,
            month=now.month - 1 if now.month > 1 else 12,
        )
        if not month:
            month = now.month
        start = dt(
            now.year,
            month,
            1,
        )
        if start < now_minus_one_month:
            start = start.replace(year=start.year + 1)
        end = dt(
            now.year if month < 12 else now.year + 1,
            month + 1 if month < 12 else 1,
            1,
        )
        if start > end:
            end = end.replace(year=end.year + 1)

        # Work out what our context is
        interaction: discord.Interaction
        if isinstance(ctx, commands.Context):
            interaction = ctx.interaction
        else:
            interaction = ctx

        # Get the list of events
        await interaction.response.defer()
        async with vbu.Database() as db:
            messages: List[ScheduledMessageDict] = await db.call(
                """
                SELECT
                    *
                FROM
                    scheduled_messages
                WHERE
                    guild_id=$1
                AND
                    timestamp >= $2
                AND
                    timestamp < $3
                """,
                interaction.guild_id, start, end,
            )

        # And respond
        if not messages:
            return await interaction.followup.send(
                f"You have no scheduled messages for {MONTH_OPTIONS[month - 1].name} {start.year}.",
            )
        message_strings: List[str] = list()
        for i in messages:
            timestamp = discord.utils.format_dt(i['timestamp'].replace(tzinfo=pytz.utc))
            text = f"\N{BULLET} <#{i['channel_id']}> at {timestamp} (`{i['id']}`): {i['text'][:50]}"
            if i['timestamp'] < dt.utcnow():
                text = f"~~{text}~~"
            message_strings.append(text)
        return await interaction.followup.send(
            "\n".join(message_strings),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def send_schedule_list_message(self, ctx: Union[GuildContext, discord.Interaction]):
        """
        Send a list of buttons that the user can click to look at the schedule.
        """

        # Work out what our interaction is
        interaction: discord.Interaction
        if isinstance(ctx, commands.Context):
            interaction = ctx.interaction
        else:
            interaction = ctx

        # Send buttons
        return await interaction.response.send_message(
            "Click any month to see the scheduled messages.",
            components=discord.ui.MessageComponents.add_buttons_with_rows(
                *[
                    discord.ui.Button(label=i.name, custom_id=f"SCHEDULE_LIST_COMMAND {i.value}")
                    for i in MONTH_OPTIONS
                ]
            )
        )

    @vbu.Cog.listener("on_component_interaction")
    async def schedule_list_command_button(
            self,
            interaction: discord.Interaction):
        """
        Waits for schedule list commands' buttons being pressed, and
        runs the command accordingly.
        """

        # Make sure the button is correct
        if not interaction.custom_id.startswith("SCHEDULE_LIST_COMMAND"):
            return

        # And run command
        await self.schedule_list(
            interaction,
            int(interaction.custom_id.split(" ")[-1]),
        )

def setup(bot: vbu.Bot):
    x = MessageScheduler(bot)
    bot.add_cog(x)
