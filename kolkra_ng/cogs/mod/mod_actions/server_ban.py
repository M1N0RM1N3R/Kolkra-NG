from typing import TYPE_CHECKING

from discord import Color, Embed, Member

from kolkra_ng.cogs.mod.mod_actions.abc import ModAction
from kolkra_ng.embeds import icons8
from kolkra_ng.utils import audit_log_reason_template

if TYPE_CHECKING:
    from kolkra_ng.cogs.mod import ModCog


class ServerBan(ModAction):
    @classmethod
    def noun(cls) -> str:
        return "ban"

    def dm_base(self) -> Embed:
        return Embed(
            color=Color.red(),
            title="Banned",
            description="You have been banned from the Splatfest server.\n"
            "If you feel this was unjustified, please join our ban appeal server for next steps: https://discord.gg/HgjBcmrfa6",
        ).set_thumbnail(url=icons8("law"))

    def log_base(self) -> Embed:
        return Embed(
            color=Color.red(),
            title="Server Ban",
        ).set_thumbnail(url=icons8("law"))

    async def apply(self, cog: "ModCog") -> None:
        await cog.bot.http.ban(
            user_id=self.target_id,
            guild_id=self.guild_id,
            reason=self.apply_audit_reason(cog.bot),
            delete_message_seconds=0,
        )

    async def lift(
        self, cog: "ModCog", author: Member, lift_reason: str | None
    ) -> None:
        await cog.bot.http.unban(
            user_id=self.target_id,
            guild_id=self.guild_id,
            reason=audit_log_reason_template(
                author_name=author.name, author_id=author.id, reason=lift_reason
            ),
        )
