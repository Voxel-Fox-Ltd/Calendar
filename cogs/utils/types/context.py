import discord
from discord.ext import vbu


__all__ = (
    'GuildInteraction',
    'GuildContext',
)


class GuildInteraction(discord.Interaction):
    guild: discord.Guild
    guild_id: int
    user: discord.Member


class GuildContext(vbu.Context):
    interaction: GuildInteraction
