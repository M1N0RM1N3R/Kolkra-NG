import asyncio
import logging
from datetime import datetime, timedelta

import humanize
from discord import Embed, Member, Message, Role
from discord.app_commands import NoPrivateMessage
from discord.ext import commands
from discord.utils import format_dt
from pydantic import BaseModel, Field

from kolkra_ng.bot import Kolkra, KolkraContext
from kolkra_ng.checks import is_staff_level
from kolkra_ng.embeds import InfoEmbed, OkEmbed, QuestionEmbed, WaitEmbed
from kolkra_ng.enums.staff_level import StaffLevel
from kolkra_ng.utils import audit_log_reason_template
from kolkra_ng.views.confirm import Confirm
from kolkra_ng.views.pager import Pager, group_embeds

log = logging.getLogger(__name__)


class RateLimit(BaseModel):
    rate: int = 1
    per: timedelta


class PingRateLimitConfig(BaseModel):
    rate_limits: dict[int, RateLimit] = Field(default_factory=dict)


class PingRateLimitsCog(commands.Cog):
    def __init__(self, bot: Kolkra) -> None:
        super().__init__()
        self.bot = bot
        self.config = PingRateLimitConfig(**bot.config.cogs.get(self.__cog_name__, {}))
        self.limits: dict[int, commands.Cooldown] = {
            role: commands.Cooldown(rate=limit.rate, per=limit.per.total_seconds())
            for role, limit in self.config.rate_limits.items()
        }
        self.reset_tasks: dict[int, asyncio.Task[None]] = {}

    async def __delayed_reset(self, role: Role, wait: float) -> None:
        await asyncio.sleep(wait)
        await role.edit(mentionable=True, reason="Ping rate limit reset")

    async def why_isnt_my_ping_working(self, message: Message) -> None:
        if not message.guild:
            return
        bad_pings = False
        embed = WaitEmbed(
            title="Role(s) on cooldown",
            description="One or more roles you tried to ping is currently on cooldown.",
        )
        for role, limit in [
            (message.guild.get_role(k), v)
            for k, v in self.limits.items()
            if v.get_tokens() == 0
        ]:
            if not role:
                continue
            if "@" + role.name in message.content or role.mention in message.content:
                bad_pings = True
                retry_timestamp = format_dt(
                    datetime.now() + timedelta(seconds=limit.get_retry_after()),
                    "R",
                )
                embed.add_field(
                    name=role.name,
                    value=f"Pingable {retry_timestamp}",
                )
        if bad_pings:
            await message.reply(embed=embed)

    async def apply_rate_limits(self, message: Message) -> None:
        for role in message.role_mentions:
            if not (limit := self.limits.get(role.id, None)):
                continue
            limit.update_rate_limit()
            if limit.get_tokens() > 0:
                continue
            await role.edit(
                mentionable=False,
                reason="Ping rate limit exhausted",
            )
            task = self.bot.loop.create_task(
                self.__delayed_reset(role, limit.get_retry_after())
            )
            self.reset_tasks[role.id] = task
            role_id = (
                role.id
            )  # Little addition to satisfy type-checking in the closure below
            task.add_done_callback(
                lambda _: self.reset_tasks.pop(role_id)  # noqa: B023
            )

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        await self.why_isnt_my_ping_working(message)
        await self.apply_rate_limits(message)

    @commands.hybrid_group(aliases=["prl"], fallback="list")
    @commands.guild_only()
    async def ping_rate_limits(self, ctx: KolkraContext) -> None:
        """List the roles with ping rate limits enforced by the bot."""
        if not ctx.guild:
            raise NoPrivateMessage()
        embed = InfoEmbed(
            title="Ping Rate-Limited Roles",
            description="These roles are automatically made unpingable when their rate limit is reached.",
        )
        embeds = []
        for role, limit in [
            (role, v) for k, v in self.limits.items() if (role := ctx.guild.get_role(k))
        ]:
            if not role:
                continue

            retry_timestamp = (
                format_dt(
                    datetime.now() + timedelta(seconds=limit.get_retry_after()),
                    "R",
                )
                if limit.get_tokens() <= 0
                else None
            )
            value = f"{limit.get_tokens()}/{limit.rate} per {humanize.precisedelta(int(limit.per))}{f' (Pingable {retry_timestamp})' if retry_timestamp else ''}"
            if len(embed.fields) >= 10:
                embeds.append(embed)
                embed = Embed(color=embed.color)
            embed.add_field(name=role.name, value=value)
        embeds.append(embed)
        await Pager(group_embeds(embeds)).respond(ctx)

    @ping_rate_limits.command(aliases=["clear"])
    @commands.guild_only()
    @is_staff_level(StaffLevel.mod)
    @commands.bot_has_permissions(manage_roles=True)
    async def reset(
        self,
        ctx: KolkraContext,
        roles: commands.Greedy[Role] = commands.parameter(
            description="Roles to reset the rate limit for",
            displayed_default="all rate-limited roles",
            default=None,
        ),
    ) -> None:
        """Reset role ping rate limits."""
        if not ctx.guild or not isinstance(ctx.author, Member):
            raise NoPrivateMessage()
        selection = [
            (role, limit)
            for role in (roles or ctx.guild.roles)
            if (limit := self.limits.get(role.id, None)) and role < ctx.author.top_role
        ]
        if not await Confirm(ctx.author).respond(
            ctx,
            embed=QuestionEmbed(
                title="Reset rate limits?",
                description=f"You are about to reset the rate limits on {len(selection)} roles. Are you sure you want to continue?",
            ),
        ):
            return
        for role, limit in selection:
            if task := self.reset_tasks.get(role.id, None):
                task.cancel()
            limit.reset()
            await role.edit(
                mentionable=True,
                reason=audit_log_reason_template(
                    author_name=ctx.author.name,
                    author_id=ctx.author.id,
                    reason=f"Used {ctx.invoked_with}",
                ),
            )

        await ctx.respond(
            embed=OkEmbed(description=f"Reset rate limits for {len(selection)} roles.")
        )


async def setup(bot: Kolkra) -> None:
    await bot.add_cog(PingRateLimitsCog(bot))
