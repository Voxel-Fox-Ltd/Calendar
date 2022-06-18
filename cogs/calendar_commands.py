from datetime import datetime as dt
from dataclasses import dataclass
from typing import List, Union
import operator

import discord
from discord.abc import Snowflake
from discord.ext import commands, vbu

from cogs.utils import Event
from cogs.utils.types import GuildContext
from cogs.utils.values import MONTH_OPTIONS


@dataclass
class FakeContext:
    """
    Context object used in the partial message converter.
    """

    guild: Union[discord.Guild, Snowflake]
    bot: vbu.Bot


class CalendarCommands(vbu.Cog[vbu.Bot]):

    @commands.group(
        application_command_meta=commands.ApplicationCommandMeta(
            guild_only=True,
        ),
    )
    async def calendar(self, _):
        ...

    @calendar.command(
        name="show",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="month",
                    type=discord.ApplicationCommandOptionType.integer,
                    description="The month that you want to look at.",
                    choices=list(MONTH_OPTIONS),
                ),
            ],
            guild_only=True,
        ),
    )
    @commands.defer()
    async def calendar_show(
            self,
            ctx: GuildContext,
            month: int):
        """
        Show all of the events for a given month.
        """

        # Set up translation table
        tra = vbu.translation(ctx, "main")

        # Get the events for that month
        events: List[Event] = await Event.fetch_all_for_guild(ctx.guild, month=month)

        # See if there are events in that month
        if not events:
            month_i8n = tra.gettext(MONTH_OPTIONS[month - 1].name)
            text = tra.gettext("There are no events in {month}.").format(month=month_i8n)
            return await ctx.interaction.followup.send(text)

        # Give them a list
        event_strings: List[str] = []
        th_func = lambda d: (
            "st" if str(d)[-1] == "1" else
            "nd" if str(d)[-1] == "2" else
            "rd" if str(d)[-1] == "3" else
            "th"
        )
        events.sort(key=operator.attrgetter("day"))
        for e in events:
            if len(e.name) > 50:
                event_strings.append(f"\N{BULLET} ({e.timestamp.day}{th_func(e.timestamp.day)}) {e.name[:50]}...")
            else:
                event_strings.append(f"\N{BULLET} ({e.timestamp.day}{th_func(e.timestamp.day)}) {e.name}")
        await ctx.interaction.followup.send(
            "\n".join(event_strings),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @calendar.command(
        name="create",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="channel",
                    type=discord.ApplicationCommandOptionType.channel,
                    description="The channel that you want the calendar to be made in.",
                    channel_types=[
                        discord.ChannelType.text,
                    ],
                ),
            ],
        ),
    )
    @commands.defer()
    async def calendar_create(
            self,
            ctx: GuildContext,
            channel: discord.TextChannel):
        """
        Add a calendar for the guild.
        """

        # See if they have a channel set up already
        has_calendar: bool = False
        async with vbu.Database() as db:
            rows = await db.call(
                """
                SELECT
                    *
                FROM
                    guild_settings
                WHERE
                    guild_id = $1
                """,
                ctx.guild.id,
            )
            if rows and rows[0]['calendar_message_url']:
                has_calendar = True
        if has_calendar:
            ...  # todo ask if they want to replace

        # Send the current calendar
        calendar_message = await channel.send("...")

        # Save message
        async with vbu.Database() as db:
            await db.call(
                """
                INSERT INTO
                    guild_settings
                    (
                        guild_id,
                        calendar_message_url
                    )
                VALUES
                    (
                        $1,  -- guild_id
                        $2  -- calendar_message_url
                    )
                ON CONFLICT
                    (guild_id)
                DO UPDATE SET
                    calendar_message_url = excluded.calendar_message_url
                """,
                ctx.guild.id, calendar_message.jump_url,
            )

        # And tell them it's done
        text = vbu.translation(ctx, "main").gettext("Your guild calendar has been created.")
        await ctx.interaction.followup.send(text)
        self.bot.dispatch("calendar_update", ctx.guild)

    @vbu.Cog.listener()
    async def on_calendar_update(
            self,
            guild: Snowflake) -> None:
        """
        Update a calendar for the guild. Fail silently if the guild has no calendar
        URL, or delete the URL from the guild if the message fails to update.
        """

        # Get data
        async with vbu.Database() as db:

            # Get message URL
            rows = await db.call(
                """
                SELECT
                    calendar_message_url
                FROM
                    guild_settings
                WHERE
                    guild_id = $1
                """,
                guild.id,
            )

            # Filter nulls
            if not rows:
                return
            calendar_message_url = rows[0]['calendar_message_url']
            if calendar_message_url is None:
                return

            # Get the events
            events = await Event.fetch_all_for_guild(guild, month=dt.utcnow().month, db=db)

        # Get message
        ctx = FakeContext(bot=self.bot, guild=guild)
        message: discord.PartialMessage
        try:
            _, message_id, channel_id = commands.PartialMessageConverter._get_id_matches(
                ctx,
                calendar_message_url,
            )
            assert channel_id
            channel = self.bot.get_partial_messageable(
                channel_id,
                type=discord.ChannelType.text,
            )
            message = channel.get_partial_message(message_id)
        except Exception:
            return

        # Try and edit the message
        calendar_content = Event.format_events(events, include_empty_days=True)
        try:
            await message.edit(content=calendar_content)
        except discord.HTTPException:
            async with vbu.Database() as db:
                await db.call(
                    """
                    UPDATE
                        guild_settings
                    SET
                        calendar_message_url = NULL
                    WHERE
                        guild_id = $1
                    """,
                    guild.id,
                )

        # And done
        return


def setup(bot: vbu.Bot):
    x = CalendarCommands(bot)
    bot.add_cog(x)
