from typing import TYPE_CHECKING, List, Tuple
from datetime import datetime as dt, timedelta

import discord
from discord.ext import commands, tasks, vbu
import pytz

from cogs.utils.types import GuildContext, ScheduledMessageDict

if TYPE_CHECKING:
    import uuid


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
        now = dt.utcnow().replace(second=0, microsecond=0)
        async with vbu.Database() as db:
            messages: List[ScheduledMessageDict] = await db.call(
                """
                SELECT
                    *
                FROM
                    scheduled_messages
                WHERE
                    timestamp > $1
                AND
                    timestamp < $2
                AND
                    NOT (id=ANY($3))
                """,
                now, now + timedelta(minutes=1), [i[1] for i in self.sent_ids],
            )

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
            except discord.HTTPException:
                pass

        # Cache the IDs so as to not resend
        for i in messages:
            new_item = (
                dt.utcnow(),
                i['id'],
            )
            self.sent_ids.append(new_item)

        # And delete old IDs
        self.sent_ids = [
            i
            for i in self.sent_ids
            if i[0] < dt.utcnow() - timedelta(minutes=10)
        ]

    @commands.group(
        application_command_meta=commands.ApplicationCommandMeta(),
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

        await ctx.send("Not yet implemented.")

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
                    choices=[
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
                    ],
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
            year=now.year if month > now.month else now.year + 1,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            tzinfo=pytz.timezone("EST"),
        )

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
                        generate_uuid_v4(),  -- id
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
                send_time,
            )
        created = created_rows[0]

        # Tell the user it's done
        future = discord.utils.format_dt(send_time, style="R")
        response = (
            f"Scheduled your message to be sent into {channel.mention} "
            f"{future} with ID `{created['id']!s}` :)"
        )
        await ctx.interaction.followup.send(response)


def setup(bot: vbu.Bot):
    x = MessageScheduler(bot)
    bot.add_cog(x)
