from datetime import datetime as dt
from dataclasses import dataclass
from typing import List, Optional, Union
import operator

import discord
from discord.abc import Snowflake
from discord.ext import commands, vbu

from cogs.utils import Event
from cogs.utils.types import GuildContext
from cogs.utils.types.context import GuildInteraction
from cogs.utils.values import MONTH_OPTIONS, get_day_suffix, send_schedule_list_message


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
                    required=False,
                ),
            ],
            guild_only=True,
        ),
    )
    async def calendar_show(
            self,
            ctx: Union[GuildContext, GuildInteraction],
            month: Optional[int] = None):
        """
        Show all of the events for a given month.
        """

        # Set up translation table
        tra = vbu.translation(ctx, "main")

        # If they didn't give a month, put out a list of months
        if month is None:
            tra = vbu.translation(ctx, "main")
            # TRANSLATORS: Text appearing in a message above select buttons.
            text = tra.gettext("Click any month to see the events.")
            return await send_schedule_list_message(
                ctx,
                message_text=text,
                custom_id_prefix="CALENDAR_SHOW_COMMAND",
            )

        # Work out what our context is
        interaction: discord.Interaction
        if isinstance(ctx, commands.Context):
            interaction = ctx.interaction
        else:
            interaction = ctx

        # Get the events for that month
        await interaction.response.defer()
        events: List[Event] = await Event.fetch_all_for_guild(
            discord.Object(interaction.guild_id),
            month=month,
        )

        # See if there are events in that month
        if not events:
            month_i8n = tra.gettext(MONTH_OPTIONS[month - 1].name)
            text = tra.gettext("There are no events in {month}.").format(month=month_i8n)
            return await interaction.followup.send(text)

        # Give them a list
        event_strings: List[str] = []
        events.sort(key=operator.attrgetter("timestamp"))
        for e in events:
            if len(e.name) > 50:
                text = f"\u2022 ({e.timestamp.day}{get_day_suffix(e.timestamp.day)}) {e.name[:50]}..."
            else:
                text = f"\u2022 ({e.timestamp.day}{get_day_suffix(e.timestamp.day)}) {e.name}"
            event_strings.append(text)
        await interaction.followup.send(
            "\n".join(event_strings),
            allowed_mentions=discord.AllowedMentions.none(),
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
        if not interaction.custom_id.startswith("CALENDAR_SHOW_COMMAND"):
            return

        # And run command
        await self.calendar_show(
            interaction,
            int(interaction.custom_id.split(" ")[-1]),
        )

    @calendar.command(
        name="refresh",
        application_command_meta=commands.ApplicationCommandMeta(),
    )
    async def calendar_refresh(
            self,
            ctx: GuildContext):
        """
        Publish a calendar update.
        """

        self.bot.dispatch("calendar_update", ctx.guild)
        await ctx.interaction.response.send_message("Published calendar update :)")

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
        # TRANSLATORS: Text appearing after an auto-updating calendar has been generated.
        text = vbu.translation(ctx, "main").gettext("Your guild calendar has been created.")
        await ctx.interaction.followup.send(text)
        self.bot.dispatch("calendar_update", ctx.guild)

    @vbu.Cog.listener()
    async def on_calendar_update(
            self,
            guild: discord.Guild) -> None:
        """
        Update a calendar for the guild. Fail silently if the guild has no calendar
        URL, or delete the URL from the guild if the message fails to update.
        """

        # Get data
        current_month: int = dt.utcnow().month
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
            events = await Event.fetch_all_for_guild(guild, month=current_month, db=db)

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
        month_name = MONTH_OPTIONS[current_month].name_localizations[
            guild.preferred_locale
            or discord.Locale.american_english
        ]
        calendar_prefix = f"__**{month_name}**__"
        try:
            await message.edit(
                content=f"{calendar_prefix}\n\n{calendar_content}",
                allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
            )
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
