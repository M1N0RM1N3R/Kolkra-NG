from datetime import datetime, timedelta
from typing import TypeAlias

from discord import (
    Color,
    DMChannel,
    Embed,
    GroupChannel,
    Message,
    PartialMessageable,
    StageChannel,
    TextChannel,
    Thread,
    VoiceChannel,
)
from discord.ext import commands
from discord.utils import format_dt
from pydantic import BaseModel, Field

from kolkra_ng.bot import Kolkra
from kolkra_ng.embeds import icons8

MessageableChannel: TypeAlias = (
    TextChannel
    | VoiceChannel
    | StageChannel
    | Thread
    | DMChannel
    | PartialMessageable
    | GroupChannel
)  # Yoinked from discord.abc beacuse it's in a `if TYPE_CHECKING` block for some reason.


class BumpReminderConfig(BaseModel):
    ping_roles: list[int] = Field(default_factory=list)


DISBOARD_BOT_ID = 302050872383242240


class BumpReminderCog(commands.Cog):
    def __init__(self, bot: Kolkra) -> None:
        super().__init__()
        self.bot = bot
        self.config = BumpReminderConfig(**bot.config.cogs.get(self.__cog_name__, {}))

    async def send_reminder(self, channel: MessageableChannel) -> None:
        await channel.send(
            "".join([f"<@&{role}>" for role in self.config.ping_roles]) or None,
            embed=Embed(
                title="Time to bump!",
                description="Bump our server by typing `/bump`!",
                color=Color.yellow(),
            ).set_thumbnail(url=icons8("alarm")),
        )

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        if not (
            message.author.id == DISBOARD_BOT_ID
            and message.embeds[0].image.url
            == "https://disboard.org/images/bot-command-image-bump.png"
        ):
            return
        next_bump = datetime.now() + timedelta(hours=2)
        self.task = self.bot.schedule(self.send_reminder, next_bump, message.channel)
        await message.channel.send(
            embed=Embed(
                title="Thanks for the bump!",
                description="I'll remind you when the server can be bumped again.",
            )
            .set_thumbnail(url=icons8("reminder"))
            .add_field(
                name="Next bump",
                value=format_dt(next_bump, "R"),
            )
        )


async def setup(bot: Kolkra) -> None:
    await bot.add_cog(BumpReminderCog(bot))
