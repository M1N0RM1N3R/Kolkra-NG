from typing import TYPE_CHECKING

from discord import Color, Embed, Member

from kolkra_ng.cogs.mod.mod_actions.abc import ModAction
from kolkra_ng.embeds import icons8

if TYPE_CHECKING:
    from kolkra_ng.cogs.mod import ModCog


class Softban(ModAction):
    @classmethod
    def noun(cls) -> str:
        return "softban"

    def dm_base(self) -> Embed:
        return Embed(
            color=Color.red(),
            title="Softbanned",
            description="This account is no longer permitted to participate in the Splatfest server.\n"
            "If you feel this was unjustified, please join our ban appeal server for next steps: https://discord.gg/HgjBcmrfa6",
        ).set_thumbnail(url=icons8("no-entry"))

    def log_base(self) -> Embed:
        return Embed(color=Color.red(), title="Softban").set_thumbnail(
            url=icons8("no-entry")
        )

    async def apply(self, cog: "ModCog") -> None:
        return await cog.bot.http.kick(
            self.target_id, self.guild_id, self.apply_audit_reason(cog.bot)
        )

    async def lift(
        self, cog: "ModCog", author: Member, lift_reason: str | None
    ) -> None:
        pass  # There's nothing to do, just stop kicking them
