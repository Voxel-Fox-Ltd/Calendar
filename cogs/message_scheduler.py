from typing import List, Tuple, Optional
from datetime import datetime as dt, timedelta
import uuid

import discord
from discord.ext import commands, tasks, vbu
import pytz
import pytimeparse

from cogs.utils import MONTH_OPTIONS
from cogs.utils.types import GuildContext, ScheduledMessageDict


class MessageScheduler(vbu.Cog[vbu.Bot]):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sent_ids: List[Tuple[dt, uuid.UUID]] = list()
        self.message_schedule_send_loop.start()

    def cog_unload(self) -> None:
        self.message_schedule_send_loop.stop()
        return super().cog_unload()

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
                    NOT (id=ANY($3::UUID[]))
                """,
                now, now + timedelta(minutes=1), [i[1] for i in self.sent_ids],
            )
        self.logger.info(messages)

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
        self.logger.info("Sent message cache: %s" % self.sent_ids)

        # And delete old IDs
        self.sent_ids = [
            i
            for i in self.sent_ids
            if i[0] > dt.utcnow() - timedelta(minutes=2)
        ]
        self.logger.info("Now filtered message cache: %s" % self.sent_ids)

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
                    description="The channel you want to send the message in.",
                    type=discord.ApplicationCommandOptionType.channel,
                    channel_types=[
                        discord.ChannelType.text,
                    ],
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
            channel: discord.TextChannel):
        """
        Schedule a message to be sent in a given channel at a specific time.
        """

        # Build a time
        now = dt.utcnow().astimezone(pytz.timezone("EST"))
        send_time = dt(
            year=now.year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            tzinfo=pytz.timezone("EST"),
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
        name="delete",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="message",
                    description="The message that you want to delete.",
                    type=discord.ApplicationCommandOptionType.string,
                    autocomplete=True,
                    required=False,
                ),
            ],
            guild_only=True,
        ),
    )
    async def schedule_delete(
            self,
            ctx: GuildContext,
            message: Optional[str]):
        """
        Delete a scheduled message.
        """

        self.logger.info(message)

        # See if the message is a UUID
        message_is_id = True
        try:
            uuid.UUID(message)
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
                message, ctx.guild.id,
            )

        # And done
        return await ctx.interaction.followup.send("Deleted message :)")

    @schedule_delete.autocomplete
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
                ),
            ],
        ),
    )
    async def schedule_list(
            self,
            ctx: GuildContext,
            month: Optional[int]):
        """
        Check a list of scheduled messages.
        """

        # Get times
        now = dt.utcnow()
        if not month:
            month = now.month
        start = dt(
            now.year,
            month,
            1,
        )
        end = dt(
            now.year if month < 12 else now.year + 1,
            month + 1 if month < 12 else 1,
            1,
        )

        # Get the list of events
        await ctx.interaction.response.defer()
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
                ctx.guild.id, start, end,
            )

        # And respond
        if not messages:
            return await ctx.interaction.followup.send(
                "You have no scheduled messages for that month.",
            )
        message_strings: List[str] = [
            f"\N{BULLET} <#{i['channel_id']}>: {i['text'][:50]}"
            for i in messages
        ]
        return await ctx.interaction.followup.send("\n".join(message_strings))

def setup(bot: vbu.Bot):
    x = MessageScheduler(bot)
    bot.add_cog(x)
