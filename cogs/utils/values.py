from typing import Tuple

import discord


__all__ = (
    'MONTH_OPTIONS',
    'TIMEZONE_OPTIONS',
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
