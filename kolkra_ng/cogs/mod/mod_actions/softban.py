from discord import Color, Embed, Member

from kolkra_ng.bot import Kolkra
from kolkra_ng.cogs.mod.mod_actions.abc import ModAction
from kolkra_ng.embeds import icons8


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

    async def apply(self, bot: Kolkra) -> None:
        return await bot.http.kick(
            self.target_id, self.guild_id, self.apply_audit_reason(bot)
        )

    async def lift(self, bot: Kolkra, author: Member, lift_reason: str | None) -> None:
        pass  # There's nothing to do, just stop kicking them
