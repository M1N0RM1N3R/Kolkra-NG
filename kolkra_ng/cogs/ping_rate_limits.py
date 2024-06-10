import asyncio
import logging
from datetime import datetime, timedelta
from typing import Annotated, Any

import humanize
from beanie import Indexed
from beanie.operators import Eq, In
from discord import Member, Message, Role
from discord.ext import commands
from discord.utils import format_dt, utcnow
from typing_extensions import Self

from kolkra_ng.bot import Kolkra, KolkraContext
from kolkra_ng.checks import is_staff_level
from kolkra_ng.converters import Flags, TimeDeltaConverter
from kolkra_ng.db_types import KolkraDocument, RoleRepr
from kolkra_ng.embeds import (
    AccessDeniedEmbed,
    InfoEmbed,
    OkEmbed,
    QuestionEmbed,
    SplitEmbed,
    WaitEmbed,
)
from kolkra_ng.enums.staff_level import StaffLevel
from kolkra_ng.utils import audit_log_reason_template
from kolkra_ng.views.confirm import Confirm
from kolkra_ng.views.pager import Pager, group_embeds

log = logging.getLogger(__name__)


# https://adamj.eu/tech/2021/10/13/how-to-create-a-transparent-attribute-alias-in-python/
class Alias:
    def __init__(self, source_name: str):
        self.source_name = source_name

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            # Class lookup, return descriptor
            return self
        return getattr(obj, self.source_name)

    def __set__(self, obj: Any, value: Any) -> None:
        setattr(obj, self.source_name, value)


class PingRateLimit(KolkraDocument):
    """A Beanie representation of a rate limit with methods borrowed from `commands.Cooldown`.
    I'm so sorry...
    """

    class Settings:
        use_cache = True
        cache_expiration_time = timedelta(seconds=10)

    role_repr: Annotated[RoleRepr, Indexed(unique=True)]

    rate: int
    per: float
    window: float = 0
    tokens: int
    last: float = 0

    @classmethod
    def new(cls, rate: int, per: float, role_repr: RoleRepr) -> Self:
        return cls(rate=rate, per=per, tokens=rate, role_repr=role_repr)

    @property
    def available_at(self) -> datetime:
        return utcnow() + timedelta(seconds=self.get_retry_after())

    # Borrowstealing some methods from commands.Cooldown...
    # ️⚠ CURSED CODE AHEAD!

    _window = Alias("window")
    _tokens = Alias("tokens")
    _last = Alias("last")

    def get_retry_after(self, current: float | None = None) -> float:
        return commands.Cooldown.get_retry_after(
            self, current  # pyright: ignore [reportArgumentType]
        )

    def get_tokens(self, current: float | None = None) -> int:
        return commands.Cooldown.get_tokens(
            self, current  # pyright: ignore [reportArgumentType]
        )

    def reset(self) -> None:
        return commands.Cooldown.reset(self)  # pyright: ignore [reportArgumentType]

    def update_rate_limit(
        self, current: float | None = None, *, tokens: int = 1
    ) -> float | None:
        return commands.Cooldown.update_rate_limit(
            self,  # pyright: ignore [reportArgumentType]
            current,
            tokens=tokens,
        )


class RateLimitFlags(Flags):
    rate: commands.Range[int, 1] = commands.flag(aliases=["tokens"], default=1)
    per: timedelta = commands.flag(
        aliases=["cooldown", "bucket"],
        converter=TimeDeltaConverter(),
        positional=True,
    )


@commands.guild_only()
@commands.bot_has_permissions(manage_roles=True)
class PingRateLimitsCog(commands.Cog):
    def __init__(self, bot: Kolkra) -> None:
        super().__init__()
        self.bot = bot
        self.reset_tasks: dict[RoleRepr, asyncio.Task[None]] = {}

    async def cog_load(self) -> None:
        await self.bot.init_db_models(PingRateLimit)
        async for rl in PingRateLimit.find_all():
            self.setup_reset(rl)

    async def cog_unload(self) -> None:
        for task in self.reset_tasks.values():
            task.cancel()

    async def reset(
        self, rate_limit: PingRateLimit, manual_by: Member | None = None
    ) -> None:
        await self.bot.http.edit_role(
            rate_limit.role_repr.guild_id,
            rate_limit.role_repr.role_id,
            reason=(
                audit_log_reason_template(
                    author_name=manual_by.name,
                    author_id=manual_by.id,
                    reason="Manually reset rate limit",
                )
                if manual_by
                else "Rate limit reset"
            ),
            mentionable=True,
        )
        if not manual_by:
            return
        if task := self.reset_tasks.pop(rate_limit.role_repr, None):
            task.cancel()
        rate_limit.reset()
        await rate_limit.save()

    def setup_reset(self, rate_limit: PingRateLimit) -> None:
        if existing := self.reset_tasks.pop(rate_limit.role_repr, None):
            existing.cancel()
        task = self.bot.schedule(self.reset, rate_limit.available_at, rate_limit)
        self.reset_tasks[rate_limit.role_repr] = task

    async def why_isnt_my_my_ping_working(
        self, message: Message, bad_pings: list[tuple[Role, PingRateLimit]]
    ) -> None:
        split_embed = SplitEmbed.from_single(
            WaitEmbed(
                title="Pings not working?",
                description="One or more roles you tried to mention is currently on cooldown.",
            )
        )
        for role, rl in bad_pings:
            split_embed.add_field(
                name=role.name,
                value=f"Pingable {format_dt(rl.available_at, 'R')}",
            )
        await message.reply(embeds=split_embed.embeds())

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        if not message.guild:
            return
        to_delete = []
        bad_pings = []
        async for rl in PingRateLimit.find(
            Eq(PingRateLimit.role_repr.guild_id, message.guild.id)
        ):
            if not (role := await rl.role_repr.get(self.bot)):
                log.info(
                    "Role %s doesn't seem to exist anymore--rate limit marked for deletion.",
                    rl.role_repr,
                )
                to_delete.append(rl)
                continue
            if role in message.role_mentions:
                rl.update_rate_limit()
                await rl.save()
            if rl.get_tokens() > 0:
                continue
            self.setup_reset(rl)
            if role.mentionable:
                await role.edit(
                    mentionable=False,
                    reason=f"Rate limit exhausted, resetting at {rl.available_at}",
                )
                continue
            if (
                role.mention in message.content and role not in message.role_mentions
            ) or f"@{role.name}" in message.content:
                bad_pings.append((role, rl))
        if bad_pings:
            await self.why_isnt_my_my_ping_working(message, bad_pings)
        for rl in to_delete:
            await rl.delete()

    @commands.hybrid_group(aliases=["prl"], fallback="list")
    async def ping_rate_limits(self, ctx: KolkraContext) -> None:
        """List the roles with ping rate limits enforced by the bot."""
        if not ctx.guild:
            raise commands.NoPrivateMessage()
        split_embed = SplitEmbed.from_single(
            InfoEmbed(
                title="Rate-limited roles",
                description="These roles are automatically made unpingable when their rate limit is reached.",
            )
        )
        async for limit in PingRateLimit.find(
            Eq(PingRateLimit.role_repr.guild_id, ctx.guild.id)
        ):
            if not (role := await limit.role_repr.get(ctx.bot)):
                continue

            per = humanize.precisedelta(int(limit.per))
            pingable = (
                f" (Pingable {format_dt(limit.available_at, 'R')})"
                if limit.get_tokens() <= 0
                else ""
            )
            value = f"{limit.get_tokens()}/{limit.rate} per {per}{pingable}"
            split_embed.add_field(name=role.name, value=value)
        await Pager(group_embeds(split_embed.embeds()), ctx.author).respond(
            ctx, ephemeral=True
        )

    @ping_rate_limits.command(name="reset", aliases=["clear"])
    @is_staff_level(StaffLevel.mod)
    async def reset_cmd(
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
            raise commands.NoPrivateMessage()
        limits = await PingRateLimit.find(
            In(
                PingRateLimit.role_repr,
                [RoleRepr._from(role) for role in roles],
            )
        ).to_list()
        if not await Confirm(ctx.author).respond(
            ctx,
            embed=QuestionEmbed(
                title="Reset rate limits?",
                description=f"You are about to reset the rate limits on {len(limits)} roles. Are you sure you want to continue?",
            ),
        ):
            return
        for limit in limits:
            await self.reset(limit, ctx.author)

        await ctx.respond(
            embed=OkEmbed(description=f"Reset rate limits for {len(limits)} roles.")
        )

    @ping_rate_limits.command(
        name="set",
        aliases=["setup", "new", "add", "create", "edit"],
        rest_is_raw=True,
    )
    @is_staff_level(StaffLevel.mod)
    async def set_cmd(
        self, ctx: KolkraContext, role: Role, *, flags: RateLimitFlags
    ) -> None:
        """Set up a ping rate limit for a role.
        This rate limit is consumed each time the role is mentioned, and is made unmentionable when it is exhausted.
        """
        if role >= role.guild.me.top_role:
            await ctx.respond(
                embed=AccessDeniedEmbed(
                    title="Can't manage role",
                    description="That role is the same or higher than my top role!",
                )
            )
            return
        role_repr = RoleRepr._from(role)
        if rl := await PingRateLimit.find(
            Eq(PingRateLimit.role_repr, role_repr)
        ).first_or_none():
            rl.rate = flags.rate
            rl.per = flags.per.total_seconds()
            rl.update_rate_limit(tokens=0)
        else:
            rl = PingRateLimit.new(flags.rate, flags.per.total_seconds(), role_repr)
        await rl.save()
        await ctx.respond(
            embed=OkEmbed(
                description=f"Set rate limit of {flags.rate} ping{'s' if flags.rate != 1 else ''} "
                f"per {humanize.precisedelta(flags.per)} for {role.mention}."
            )
        )

    @ping_rate_limits.command(aliases=["del", "remove", "rm"])
    @is_staff_level(StaffLevel.mod)
    async def delete(self, ctx: KolkraContext, role: Role) -> None:
        """Remove the ping rate limit from a role."""
        if not isinstance(ctx.author, Member):
            raise commands.NoPrivateMessage()
        if not (
            limit := await PingRateLimit.find(
                Eq(PingRateLimit.role_repr, RoleRepr._from(role))
            ).first_or_none()
        ):
            await ctx.respond(
                embed=InfoEmbed(
                    title="No rate limit set",
                    description=f"There is no ping rate limit set for {role.mention}.",
                )
            )
            return
        if not await Confirm(ctx.author).respond(
            ctx,
            embed=QuestionEmbed(
                title="Delete ping rate limit?",
                description=f"You are about to permanently remove {role.mention}'s rate limit. "
                "This will make the role permanently mentionable again, and delete the rate limit from the database. "
                "Are you sure you want to continue?",
            ),
        ):
            return
        await self.reset(limit, ctx.author)
        await limit.delete()
        await ctx.respond(
            embed=OkEmbed(description=f"Removed rate limit from {role.mention}.")
        )


async def setup(bot: Kolkra) -> None:
    await bot.add_cog(PingRateLimitsCog(bot))
