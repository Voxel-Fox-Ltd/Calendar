import asyncio
from uuid import uuid4
from datetime import datetime as dt

import discord
from discord.ext import commands, vbu

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
            day: int):
        """
        Add a new event to the server's calendar.
        """

        # Create an event object
        timestamp = dt(
            dt.utcnow().year,
            month,
            day,
        )
        if timestamp < dt.utcnow():
            timestamp = timestamp.replace(year=timestamp.year + 1)
        event = Event(
            guild_id=ctx.interaction.guild_id,
            user_id=ctx.interaction.user.id,
            name=name,
            timestamp=timestamp,
        )

        # Set up translation table
        tra = vbu.translation(ctx, "main")

        # Defer so we can check if the event exists
        await ctx.interaction.response.defer()
        current_event = await Event.fetch_by_name(ctx.guild, name)
        if current_event:
            text = tra.gettext("There's already an event with the name **{name}**.")
            return await ctx.interaction.followup.send(
                text.format(name),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        # Save the event
        await event.save()

        # And tell them it's done :)
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
    @commands.defer()
    async def event_delete(
            self,
            ctx: GuildContext,
            name: str):
        """
        Delete an event from the server's calendar.
        """

        # Get the event
        event: Event = await Event.convert(ctx, name)

        # Threaten to delete the event
        component_id = str(uuid4())
        components = discord.ui.MessageComponents.boolean_buttons(
            yes=("Yes", f"{component_id} YES"),
            no=("No", f"{component_id} NO"),
        )
        tra = vbu.translation(ctx, "main")
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
            text = tra.gettext("Alright, I won't delete that event.")
            return await interaction.response.edit_message(
                content=text,
                components=None,
            )

        # They agreed
        await interaction.response.defer_update()
        await event.delete()
        text = tra.gettext("Event deleted!")
        return await interaction.edit_original_message(
            content=text,
            components=None,
        )

    @event_delete.autocomplete
    async def event_name_autocomplete(
            self,
            ctx: GuildContext,
            interaction: GuildInteraction) -> None:
        """
        The autocomplete for guild names.
        """

        option: discord.ApplicationCommandInteractionDataOption
        try:
            option = interaction.options[0].options[0]  # type: ignore
        except Exception:
            return await interaction.response.send_autocomplete()
        events = await Event.fetch_all_for_guild(
            ctx.guild,
            name=option.value,
        )
        await interaction.response.send_autocomplete([
            discord.ApplicationCommandOptionChoice(name=e.name, value=e.id)
            for e in events
        ])


def setup(bot: vbu.Bot):
    x = EventManagementCommands(bot)
    bot.add_cog(x)