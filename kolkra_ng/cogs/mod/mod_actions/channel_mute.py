from typing import TYPE_CHECKING

from beanie.odm.queries.find import FindMany
from beanie.operators import Eq
from discord import Color, Embed, Member, PermissionOverwrite
from typing_extensions import Self

from kolkra_ng.cogs.mod.mod_actions.abc import ModAction
from kolkra_ng.embeds import icons8
from kolkra_ng.utils import audit_log_reason_template

if TYPE_CHECKING:
    from kolkra_ng.cogs.mod import ModCog
MUTE_PERMS = PermissionOverwrite(
    send_messages=False,
    send_messages_in_threads=False,
    create_public_threads=False,
    create_private_threads=False,
    add_reactions=False,
    speak=False,
)


class ChannelMute(ModAction):
    channel_id: int

    @classmethod
    def noun(cls) -> str:
        return "mute"

    def dm_base(self) -> Embed:
        return Embed(
            color=Color.orange(),
            title="Channel muted",
            description=f"You have been muted in <#{self.channel_id}>.\n"
            "If you feel this was unjustified, you may appeal by DMing <@575252669443211264>.",
        ).set_thumbnail(url=icons8("mute"))

    def log_base(self) -> Embed:
        return (
            Embed(color=Color.orange(), title="Channel mute")
            .add_field(name="Channel", value=f"<#{self.channel_id}>")
            .set_thumbnail(url=icons8("mute"))
        )

    async def apply(self, cog: "ModCog") -> None:
        allow, deny = MUTE_PERMS.pair()
        await cog.bot.http.edit_channel_permissions(
            self.channel_id,
            self.target_id,
            str(allow.value),
            str(deny.value),
            1,  # Individual member
            reason=self.apply_audit_reason(cog.bot),
        )

    async def lift(
        self, cog: "ModCog", author: Member, lift_reason: str | None
    ) -> None:
        await cog.bot.http.delete_channel_permissions(
            self.channel_id,
            self.target_id,
            reason=audit_log_reason_template(
                author_name=author.name,
                author_id=author.id,
                reason=lift_reason,
            ),
        )

    @classmethod
    def fetch_existing_for(
        cls, *args, channel_id: int | None = None, **kwargs
    ) -> FindMany[Self]:
        cur = super().fetch_existing_for(*args, **kwargs)
        return (
            cur.find(Eq(cls.channel_id, channel_id)) if channel_id is not None else cur
        )
