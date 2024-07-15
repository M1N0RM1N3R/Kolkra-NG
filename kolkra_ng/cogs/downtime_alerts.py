import logging
from asyncio import TimeoutError
from datetime import datetime

import humanize
from discord import Member, Status, Thread
from discord.ext import commands
from discord.utils import utcnow
from pydantic import BaseModel, Field

from kolkra_ng.bot import Kolkra
from kolkra_ng.embeds import OkEmbed, WarningEmbed
from kolkra_ng.webhooks import SupportsWebhooks

log = logging.getLogger(__name__)


class DowntimeAlertsConfig(BaseModel):
    bots: set[int] = Field(default_factory=set)
    ping_roles: set[int] = Field(default_factory=set)
    channel: int | None = None


class DowntimeAlertsCog(commands.Cog):
    def __init__(self, bot: Kolkra) -> None:
        super().__init__()
        self.bot = bot
        self.config = DowntimeAlertsConfig(**bot.config.cogs.get(self.__cog_name__, {}))
        self.__downtimes: dict[int, datetime] = {}

    async def cog_load(self) -> None:
        self.channel: SupportsWebhooks | Thread = (
            (
                self.bot.get_channel(self.config.channel)
                or await self.bot.fetch_channel(self.config.channel)
            )  # pyright: ignore [reportAttributeAccessIssue]
            if self.config.channel
            else self.bot.log_channel
        )
        if not isinstance(self.channel, SupportsWebhooks | Thread):
            log.warning("Configured alerts channel %s does not allow webhooks!")

    @commands.Cog.listener()
    async def on_presence_update(self, before: Member, after: Member) -> None:
        if after.id not in self.config.bots:
            return
        now = utcnow()
        try:
            await self.bot.wait_for(
                "presence_update",
                check=lambda b, a: before.id == a.id and before.status == a.status,
                timeout=5,
            )
        except TimeoutError:
            pass
        else:
            return
        if before.status != Status.offline and after.status == Status.offline:
            self.__downtimes[after.id] = now
            await self.bot.webhooks.send(
                self.channel,
                f"{after.mention} is down! | {''.join(f'<@&{i}>' for i in self.config.ping_roles)}",
                embed=WarningEmbed(
                    title="Monitored user offline",
                    description=f"{after.mention}'s status just changed to 'offline'.",
                    timestamp=now,
                ),
            )
        elif before.status == Status.offline and after.status != Status.offline:
            await self.bot.webhooks.send(
                self.channel,
                embed=OkEmbed(
                    title="Monitored user online",
                    description=f"{after.mention}'s status just changed to {after.status.name!r}.",
                    timestamp=now,
                ).add_field(
                    name="Total downtime",
                    value=(
                        humanize.precisedelta(now - dt)
                        if (dt := self.__downtimes.pop(after.id, None))
                        else "unknown"
                    ),
                ),
            )


async def setup(bot: Kolkra) -> None:
    await bot.add_cog(DowntimeAlertsCog(bot))
