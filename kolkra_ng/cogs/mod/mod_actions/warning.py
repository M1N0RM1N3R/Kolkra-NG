import logging

import humanize
from discord import Embed, Member
from pydantic import PrivateAttr

from kolkra_ng.bot import Kolkra
from kolkra_ng.cogs.mod.mod_actions.abc import ModAction
from kolkra_ng.cogs.mod.mod_actions.server_ban import ServerBan
from kolkra_ng.embeds import icons8

log = logging.getLogger(__name__)

BAN_WARNINGS = 5


class ModWarning(ModAction):
    _count: int = PrivateAttr(
        default=None
    )  # Cached warning count for logging and sending to the user

    async def cached_count(self, refresh: bool = False) -> int:
        if self._count is None or refresh:
            self._count = await self.fetch_existing_for(
                self.guild_id, self.target_id
            ).count()
        return self._count

    @classmethod
    def noun(cls) -> str:
        return "warning"

    def dm_base(self) -> Embed:
        return Embed(
            title="Warning",
            description="You have been issued a warning in the Splatfest server.",
        ).set_thumbnail(url=icons8("error"))

    async def dm_embed(self, bot: Kolkra) -> Embed:
        count = await self.cached_count()
        embed = (await super().dm_embed(bot)).add_field(
            name="Warning count",
            value=f"{'⚠' * count} This is your **{humanize.ordinal(count)} active warning**.",
        )
        if count == BAN_WARNINGS - 1:
            embed.add_field(
                name="FINAL WARNING!",
                value="If you receive **one more warning**, "
                "you will be **permanently banned** from the server.",
            )
        elif count >= BAN_WARNINGS:
            embed.add_field(
                name="Banned",
                value=f"You have been banned for accumulating {count} warnings.",
            )
        else:
            embed.add_field(
                name=f"{BAN_WARNINGS} warnings = ban",
                value=f"If you accumulate {BAN_WARNINGS} warnings, "
                "you will be permanently banned from the server.",
            )
        return embed

    def log_base(self) -> Embed:
        return Embed(title="Warning").set_thumbnail(url=icons8("error"))

    async def log_embed(self) -> Embed:
        count = await self.cached_count()
        embed = (await super().log_embed()).add_field(
            name="Warning count",
            value=f"{'⚠️' * count} {humanize.ordinal(count)} warning",
        )
        if count == BAN_WARNINGS - 1:
            embed.add_field(
                name="FINAL WARNING!",
                value="The user will be banned if they receive another warning.",
            )
        elif count == BAN_WARNINGS:
            embed.add_field(
                name="Auto-banned",
                value=f"The user was banned for accumulating over {BAN_WARNINGS} warnings.",
            )
        return embed

    async def apply(self, bot: Kolkra) -> None:
        count = await self.cached_count()
        if count >= BAN_WARNINGS:
            from kolkra_ng.cogs.mod import ModCog

            if not (cog := bot.typed_get_cog(ModCog)):
                log.warn("Bot does not have ModCog installed--can't auto-ban")
                return

            await cog.do_apply(
                ServerBan(
                    issuer_id=bot.user.id,  # pyright: ignore [reportOptionalMemberAccess]
                    target_id=self.target_id,
                    guild_id=self.guild_id,
                    reason=f"Accumulated {count}/{BAN_WARNINGS} warnings",
                    expiration=None,
                ),
                True,
            )

    async def lift(self, bot: Kolkra, author: Member, lift_reason: str | None) -> None:
        pass  # It's just a warning--there's nothing we need to do guild-side.
