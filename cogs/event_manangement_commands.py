import asyncio
from uuid import uuid4

import discord
from discord.ext import commands, vbu

from cogs import utils


class EventManagementCommands(vbu.Cog[vbu.Bot]):

    @commands.group(
        application_command_meta=commands.ApplicationCommandMeta(
            permissions=discord.Permissions(manage_guild=True),
            guild_only=True,
        ),
    )
    async def event(self, _: utils.types.GuildContext):
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
                    type=discord.ApplicationCommandOptionType.string,
                    description="The month to add the event at.",
                    choices=[
                        discord.ApplicationCommandOptionChoice(name=i)
                        for i in utils.month_list
                    ],
                ),
                discord.ApplicationCommandOption(
                    name="day",
                    type=discord.ApplicationCommandOptionType.integer,
                    description="The day to add the event on.",
                    min_value=1,
                    max_value=31,
                ),
            ],
            guild_only=True,
        ),
    )
    async def event_add(self, ctx: utils.types.GuildContext, name: str, month: str, day: int):
        """
        Add a new event to the server's calendar.
        """

        # Create an event object
        month_number = utils.month_list.index(month) + 1
        event = utils.Event(
            guild_id=ctx.interaction.guild_id,
            user_id=ctx.interaction.user.id,
            name=name,
            month=month_number,
            day=day,
            repeat=utils.RepeatTime.none,
        )

        # Defer so we can check if the event exists
        await ctx.interaction.response.defer()
        current_event = await utils.Event.fetch_by_name(ctx.guild, name)
        if current_event:
            text = vbu.translation(ctx, "main").gettext("There's already an event with the name **{name}**.")
            return await ctx.interaction.followup.send(
                text.format(name),
            )

        # Save the event
        await event.save()

        # And tell them it's done :)
        text = vbu.translation(ctx, "main").gettext("Event saved!")
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
    async def event_delete(self, ctx: utils.types.GuildContext, name: str):
        """
        Delete an event from the server's calendar.
        """

        # Get the event
        event: utils.Event = await utils.Event.convert(ctx, name)

        # Threaten to delete the event
        component_id = str(uuid4())
        components = discord.ui.MessageComponents.boolean_buttons(
            yes=("Yes", f"{component_id} YES"),
            no=("No", f"{component_id} NO"),
        )
        text = vbu.translation(ctx, "main").gettext("Are you sure you want to delete the event **{name}**.")
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
                text = vbu.translation(ctx, "main").gettext("Timed out waiting for a response.")
                await ctx.interaction.edit_original_message(
                    content=text,
                    components=None,
                )
            except:
                pass
            return

        # See if they said no
        if interaction.custom_id.endswith("NO"):
            text = vbu.translation(interaction, "main").gettext("Alright, I won't delete that event.")
            return await interaction.response.edit_message(
                content=text,
                components=None,
            )

        # They agreed
        await interaction.response.defer_update()
        await event.delete()
        text = vbu.translation(interaction, "main").gettext("Event deleted!")
        return await interaction.edit_original_message(
            content=text,
            components=None,
        )

    @event_delete.autocomplete
    async def event_name_autocomplete(
            self,
            ctx: utils.types.GuildContext,
            interaction: utils.types.GuildInteraction) -> None:
        """
        The autocomplete for guild names.
        """

        option: discord.ApplicationCommandInteractionDataOption
        try:
            option = interaction.options[0].options[0]  # type: ignore
        except Exception:
            return await interaction.response.send_autocomplete()
        events = await utils.Event.fetch_all_for_guild(
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
