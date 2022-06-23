import asyncio
from uuid import uuid4
from datetime import datetime as dt

import discord
from discord.ext import commands, vbu
import pytz

from cogs.utils import Event
from cogs.utils.types import GuildContext, GuildInteraction
from cogs.utils.values import MONTH_OPTIONS


class EventManagementCommands(vbu.Cog[vbu.Bot]):

    @commands.group(
        application_command_meta=commands.ApplicationCommandMeta(
            permissions=discord.Permissions(manage_guild=True),
            guild_only=True,
        ),
    )
    async def event(self, _):
        ...

    @event.command(
        name="add",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="name",
                    type=discord.ApplicationCommandOptionType.string,
                    description="The name of the event you want to add."
                ),
                discord.ApplicationCommandOption(
                    name="month",
                    type=discord.ApplicationCommandOptionType.integer,
                    description="The month to add the event for.",
                    choices=list(MONTH_OPTIONS),
                ),
                discord.ApplicationCommandOption(
                    name="day",
                    type=discord.ApplicationCommandOptionType.integer,
                    description="The day to add the event on.",
                    min_value=1,
                    max_value=31,
                ),
            ],
        ),
    )
    async def event_add(
            self,
            ctx: GuildContext,
            name: str,
            month: int,
            day: int,
            timezone: str = "UTC"):
        """
        Add a new event to the server's calendar.
        """

        # Set up translation table
        tra = vbu.translation(ctx, "main")

        # Create an event object
        try:
            timestamp = dt(
                dt.utcnow().year,
                month,
                day,
                tzinfo=pytz.timezone(timezone),
            )
        except ValueError:
            return await ctx.interaction.response.send_message(
                tra.gettext("Day is out of range for this month."),
                ephemeral=True,
            )
        if timestamp < discord.utils.utcnow():
            timestamp = timestamp.replace(year=timestamp.year + 1)
        event = Event(
            guild_id=ctx.interaction.guild_id,
            user_id=ctx.interaction.user.id,
            name=name,
            timestamp=timestamp,
        )

        # Defer so we can check if the event exists
        await ctx.interaction.response.defer()
        current_event = await Event.fetch_by_name(ctx.guild, name)
        if current_event:
            # TRANSLATORS: An error message when trying to make a duplicate event.
            text = tra.gettext("There's already an event with the name **{name}**.")
            return await ctx.interaction.followup.send(
                text.format(name),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        # Save the event
        await event.save()

        # And tell them it's done :)
        # TRANSLATORS: A message appearing after an event is created.
        text = tra.gettext("Event saved!")
        await ctx.interaction.followup.send(text)
        self.bot.dispatch("calendar_update", ctx.guild)

    @event.command(
        name="delete",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="name",
                    type=discord.ApplicationCommandOptionType.string,
                    description="The name of the event.",
                    autocomplete=True,
                ),
            ],
            guild_only=True,
        ),
    )
    async def event_delete(
            self,
            ctx: GuildContext,
            name: str):
        """
        Delete an event from the server's calendar.
        """

        # Get the event
        await ctx.interaction.response.defer()
        event: Event = await Event.convert(ctx, name)

        # Threaten to delete the event
        component_id = str(uuid4())
        components = discord.ui.MessageComponents.boolean_buttons(
            yes=("Yes", f"{component_id} YES"),
            no=("No", f"{component_id} NO"),
        )
        tra = vbu.translation(ctx, "main")
        # TRANSLATORS: An "are you sure" message for deleting an event.
        text = tra.gettext("Are you sure you want to delete the event **{name}**.")
        await ctx.interaction.followup.send(
            text.format(name=event.name),
            allowed_mentions=discord.AllowedMentions.none(),
            components=components,
        )

        # Wait for them to agree
        try:
            interaction: discord.Interaction = await self.bot.wait_for(
                "component_interaction",
                check=lambda i: i.custom_id.startswith(component_id),
                timeout=60,
            )
        except asyncio.TimeoutError:
            try:
                # TRANSLATORS: An error message for when a button is not pressed
                # within a given amount of time.
                text = tra.gettext("Timed out waiting for a response.")
                await ctx.interaction.edit_original_message(
                    content=text,
                    components=None,
                )
            except:
                pass
            return

        # See if they said no
        if interaction.custom_id.endswith("NO"):
            # TRANSLATORS: When a user decides to not delete an event
            # after having been given an "are you sure" message.
            text = tra.gettext("Alright, I won't delete that event.")
            return await interaction.response.edit_message(
                content=text,
                components=None,
            )

        # They agreed
        await interaction.response.defer_update()
        await event.delete()
        # TRANSLATORS: A message appearing when a user decides
        # to delete an event.
        text = tra.gettext("Event deleted!")
        await interaction.edit_original_message(
            content=text,
            components=None,
        )
        self.bot.dispatch("calendar_update", ctx.guild)

    @event_delete.autocomplete
    async def event_name_autocomplete(
            self,
            ctx: GuildContext,
            interaction: GuildInteraction) -> None:
        """
        The autocomplete for guild names.
        """

        # Get the name option
        options = interaction.options
        while options and options[0].type == discord.ApplicationCommandOptionType.subcommand:
            options = options[0].options

        # Get all of the events
        events = await Event.fetch_all_for_guild(
            ctx.guild,
            name=option[0].value,
        )

        # Send autocomplete
        await interaction.response.send_autocomplete([
            discord.ApplicationCommandOptionChoice(name=e.name, value=e.id)
            for e in events
        ])


def setup(bot: vbu.Bot):
    x = EventManagementCommands(bot)
    bot.add_cog(x)
