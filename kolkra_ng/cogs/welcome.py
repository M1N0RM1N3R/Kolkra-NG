import logging
import random

from discord import Member, Thread
from discord.ext import commands
from discord.utils import escape_markdown
from pydantic import BaseModel, HttpUrl

from kolkra_ng.bot import Kolkra
from kolkra_ng.webhooks import SupportsWebhooks

log = logging.getLogger(__name__)


class EventConfig(BaseModel):
    icon: HttpUrl
    messages: list[str]


class WelcomeConfig(BaseModel):
    channel: int
    on_join: EventConfig = EventConfig(
        icon=HttpUrl(  # pyright: ignore [reportCallIssue]
            "https://cdn.discordapp.com/attachments/1066917293935841340/1079624383410216970/Picsart_22-10-18_17-30-36-248.png"  # Please, Musi, don't delete that GDM message
        ),
        messages=[
            "<a:Booyah:847300266566746153> {user} joined **{guild}**!\n"
            "<:splatfest:1024053687217295460> <:splatlove:1057108266062196827>"
        ],
    )
    on_leave: EventConfig = EventConfig(
        icon=HttpUrl(  # pyright: ignore [reportCallIssue]
            "https://cdn.discordapp.com/attachments/1066917293935841340/1079624383804493864/Picsart_22-10-18_21-30-54-748.png"  # No really, don't delete it
        ),
        messages=[
            "<a:Ouch:847300319071043604> {user} just left **{guild}**...\n"
            "<a:1member:803768545816084480> <:splatbroke:1057109111097004103>"
        ],
    )


class WelcomeCog(commands.Cog):
    channel: SupportsWebhooks

    def __init__(self, bot: Kolkra) -> None:
        super().__init__()
        self.bot = bot
        self.config = WelcomeConfig(**bot.config.cogs.get(self.__cog_name__, {}))

    async def cog_load(self) -> None:
        self.channel = await self.bot.fetch_channel(
            self.config.channel
        )  # pyright: ignore [reportAttributeAccessIssue]
        if not isinstance(self.channel, SupportsWebhooks | Thread):
            log.warn("Configured channel %s does not support webhooks!", self.channel)

    @commands.Cog.listener()
    async def on_member_join(self, member: Member) -> None:
        await self.bot.webhooks.send(
            self.channel,
            random.choice(self.config.on_join.messages).format(
                user=member.mention, guild=member.guild.name
            ),
            avatar_url=self.config.on_join.icon,
            username="`",
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: Member) -> None:
        await self.bot.webhooks.send(
            self.channel,
            random.choice(self.config.on_leave.messages).format(
                user=escape_markdown(member.name), guild=member.guild.name
            ),
            avatar_url=self.config.on_leave.icon,
            username="`",
        )


async def setup(bot: Kolkra) -> None:
    await bot.add_cog(WelcomeCog(bot))
