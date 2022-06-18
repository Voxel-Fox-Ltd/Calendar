from typing import Tuple

import discord


__all__ = (
    'MONTH_OPTIONS',
    'TIMEZONE_OPTIONS',
    'get_timezone_command_option',
    'REPEAT_OPTIONS',
    'REPEAT_OPTIONS_WITH_NONE',
)


MONTH_OPTIONS: Tuple[discord.ApplicationCommandOptionChoice, ...] = (
    discord.ApplicationCommandOptionChoice(name="January", value=1),
    discord.ApplicationCommandOptionChoice(name="February", value=2),
    discord.ApplicationCommandOptionChoice(name="March", value=3),
    discord.ApplicationCommandOptionChoice(name="April", value=4),
    discord.ApplicationCommandOptionChoice(name="May", value=5),
    discord.ApplicationCommandOptionChoice(name="June", value=6),
    discord.ApplicationCommandOptionChoice(name="July", value=7),
    discord.ApplicationCommandOptionChoice(name="August", value=8),
    discord.ApplicationCommandOptionChoice(name="September", value=9),
    discord.ApplicationCommandOptionChoice(name="October", value=10),
    discord.ApplicationCommandOptionChoice(name="November", value=11),
    discord.ApplicationCommandOptionChoice(name="December", value=12),
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
    discord.ApplicationCommandOptionChoice(name="Daily", value="daily"),
    discord.ApplicationCommandOptionChoice(name="Monthly", value="monthly"),
    discord.ApplicationCommandOptionChoice(name="Yearly", value="yearly"),
)


REPEAT_OPTIONS_WITH_NONE: Tuple[discord.ApplicationCommandOptionChoice, ...] = (
    discord.ApplicationCommandOptionChoice(name="None", value="none"),
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
