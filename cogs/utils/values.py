from __future__ import annotations

from typing import TYPE_CHECKING, Tuple, Union

import discord
from discord.ext import commands, vbu

if TYPE_CHECKING:
    from .types import GuildContext


__all__ = (
    'MONTH_OPTIONS',
    'TIMEZONE_OPTIONS',
    'get_timezone_command_option',
    'send_schedule_list_message',
    'REPEAT_OPTIONS',
    'REPEAT_OPTIONS_WITH_NONE',
)


MONTH_OPTIONS: Tuple[discord.ApplicationCommandOptionChoice, ...] = (
    discord.ApplicationCommandOptionChoice(
        name="January",
        name_localizations={
            i: vbu.translation(i, "main").gettext("January")
            for i in discord.Locale
        },
        value=1
    ),
    discord.ApplicationCommandOptionChoice(
        name="February",
        name_localizations={
            i: vbu.translation(i, "main").gettext("February")
            for i in discord.Locale
        },
        value=2
    ),
    discord.ApplicationCommandOptionChoice(
        name="March",
        name_localizations={
            i: vbu.translation(i, "main").gettext("March")
            for i in discord.Locale
        },
        value=3
    ),
    discord.ApplicationCommandOptionChoice(
        name="April",
        name_localizations={
            i: vbu.translation(i, "main").gettext("April")
            for i in discord.Locale
        },
        value=4
    ),
    discord.ApplicationCommandOptionChoice(
        name="May",
        name_localizations={
            i: vbu.translation(i, "main").gettext("May")
            for i in discord.Locale
        },
        value=5
    ),
    discord.ApplicationCommandOptionChoice(
        name="June",
        name_localizations={
            i: vbu.translation(i, "main").gettext("June")
            for i in discord.Locale
        },
        value=6
    ),
    discord.ApplicationCommandOptionChoice(
        name="July",
        name_localizations={
            i: vbu.translation(i, "main").gettext("July")
            for i in discord.Locale
        },
        value=7
    ),
    discord.ApplicationCommandOptionChoice(
        name="August",
        name_localizations={
            i: vbu.translation(i, "main").gettext("August")
            for i in discord.Locale
        },
        value=8
    ),
    discord.ApplicationCommandOptionChoice(
        name="September",
        name_localizations={
            i: vbu.translation(i, "main").gettext("September")
            for i in discord.Locale
        },
        value=9
    ),
    discord.ApplicationCommandOptionChoice(
        name="October",
        name_localizations={
            i: vbu.translation(i, "main").gettext("October")
            for i in discord.Locale
        },
        value=10,
    ),
    discord.ApplicationCommandOptionChoice(
        name="November",
        name_localizations={
            i: vbu.translation(i, "main").gettext("November")
            for i in discord.Locale
        },
        value=11,
    ),
    discord.ApplicationCommandOptionChoice(
        name="December",
        name_localizations={
            i: vbu.translation(i, "main").gettext("December")
            for i in discord.Locale
        },
        value=12,
    ),
)

async def send_schedule_list_message(
        ctx: Union[GuildContext, discord.Interaction],
        *,
        message_text: str,
        custom_id_prefix: str):
    """
    Send a list of buttons that the user can click to look at the schedule.
    """

    # Set up a translation table
    tra = vbu.translation(ctx, "main")

    # Work out what our interaction is
    interaction: discord.Interaction
    if isinstance(ctx, commands.Context):
        interaction = ctx.interaction
    else:
        interaction = ctx

    # Send buttons
    return await interaction.response.send_message(
        message_text,
        components=discord.ui.MessageComponents.add_buttons_with_rows(
            *[
                discord.ui.Button(
                    label=tra.gettext(i.name),
                    custom_id=f"{custom_id_prefix} {i.value}",
                )
                for i in MONTH_OPTIONS
            ]
        )
    )


TIMEZONE_OPTIONS: Tuple[discord.ApplicationCommandOptionChoice, ...] = (
    discord.ApplicationCommandOptionChoice(name="UTC"),
    discord.ApplicationCommandOptionChoice(name="GMT"),
    discord.ApplicationCommandOptionChoice(name="EST"),
    discord.ApplicationCommandOptionChoice(name="CST"),
    discord.ApplicationCommandOptionChoice(name="MST"),
    discord.ApplicationCommandOptionChoice(name="PST"),
)


def get_timezone_command_option(**kwargs) -> discord.ApplicationCommandOption:
    kwargs.setdefault("name", "timezone")
    kwargs.setdefault("description", "The timezone that you're giving a time in. Defaults to UTC.")
    kwargs.setdefault("required", False)
    return discord.ApplicationCommandOption(
        **kwargs,
        type=discord.ApplicationCommandOptionType.string,
        choices=list(TIMEZONE_OPTIONS),
    )


REPEAT_OPTIONS: Tuple[discord.ApplicationCommandOptionChoice, ...] = (
    discord.ApplicationCommandOptionChoice(
        name="Daily",
        name_localizations={
            # TRANSLATORS: When describing how often an event occurs.
            i: vbu.translation(i, "main").gettext("Daily")
            for i in discord.Locale
        },
        value="daily",
    ),
    discord.ApplicationCommandOptionChoice(
        name="Monthly",
        name_localizations={
            # TRANSLATORS: When describing how often an event occurs.
            i: vbu.translation(i, "main").gettext("Monthly")
            for i in discord.Locale
        },
        value="monthly",
    ),
    discord.ApplicationCommandOptionChoice(
        name="Yearly",
        name_localizations={
            # TRANSLATORS: When describing how often an event occurs.
            i: vbu.translation(i, "main").gettext("Yearly")
            for i in discord.Locale
        },
        value="yearly",
    ),
)


REPEAT_OPTIONS_WITH_NONE: Tuple[discord.ApplicationCommandOptionChoice, ...] = (
    discord.ApplicationCommandOptionChoice(
        name="None",
        name_localizations={
            # TRANSLATORS: When describing how often an event occurs.
            i: vbu.translation(i, "main").gettext("None")
            for i in discord.Locale
        },
        value="none",
    ),
    *REPEAT_OPTIONS,
)


MONTH_DAYS: Tuple[int, ...] = (
    31,
    29,
    31,
    30,
    31,
    31,
    30,
    31,
    30,
    31,
    30,
    31,
)
