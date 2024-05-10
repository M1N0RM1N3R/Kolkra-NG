from datetime import datetime
from typing import ClassVar

from discord import AppCommandOptionType, Interaction, Member, app_commands
from discord.abc import GuildChannel
from discord.ext import commands

from kolkra_ng.bot import Kolkra
from kolkra_ng.cogs.mod.mod_actions.abc import ModAction
from kolkra_ng.converters import DatetimeConverter, Flags


class TargetCheckFailure(commands.CheckFailure):
    template: ClassVar[str]

    def __init__(self, verb: str) -> None:
        super().__init__(self.template.format(verb))


class TargetSelf(TargetCheckFailure):
    template = "You can't {} yourself, silly!"


class TargetMe(TargetCheckFailure):
    template = "I'm sorry, Dave. I'm afraid I can't do that."


class TargetDev(TargetCheckFailure):
    template = "How dare you try and {} my creator like that?! 💢"


class TargetBot(TargetCheckFailure):
    template = "You can't {} a bot!"


class TargetGEStaffLevel(TargetCheckFailure):
    template = "I can't let you {} that user because they are the same or higher staff level than you."


class TargetAboveMe(TargetCheckFailure):
    template = (
        "I can't {} that user because their top role is the same as or above mine."
    )


class DuplicateAction(commands.CheckFailure):
    def __init__(self, action: ModAction) -> None:
        super().__init__(
            f"I already have a {action.noun()} for that user in my database. "
            f"({action.get_collection_name()} ID: {action.id})"
        )


class TargetConverter(commands.MemberConverter, app_commands.Transformer):
    """A MemberConverter with some added checks to make sure the user is allowed to moderate the specified member."""

    def __init__(
        self,
        verb: str = "moderate",
        check_existing: type[ModAction] | None = None,
    ) -> None:
        super().__init__()
        self.verb = verb
        self.check_existing = check_existing

    async def check(self, bot: Kolkra, author: Member, target: Member) -> None:
        if author.id == target.id:
            raise TargetSelf(self.verb)
        elif target.id == bot.user.id:  # pyright: ignore [reportOptionalMemberAccess]
            raise TargetMe(self.verb)
        elif await bot.is_owner(target):
            raise TargetDev(self.verb)
        elif target.bot:
            raise TargetBot(self.verb)
        elif (bot.get_staff_level_for(author) or 0) <= (
            bot.get_staff_level_for(target) or 0
        ):
            raise TargetGEStaffLevel(self.verb)
        elif target.guild.me.top_role <= target.top_role:
            raise TargetAboveMe(self.verb)
        elif self.check_existing and (
            action := await self.check_existing.fetch_existing_for(
                author.guild.id, target.id
            ).first_or_none()
        ):
            raise DuplicateAction(action)

    async def convert(self, ctx: commands.Context, argument: str) -> Member:
        if not isinstance(ctx.author, Member):
            raise commands.NoPrivateMessage()
        target: Member = await super().convert(ctx, argument)
        await self.check(ctx.bot, ctx.author, target)
        return target

    @property
    def type(self) -> AppCommandOptionType:
        return AppCommandOptionType.user

    async def transform(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, interaction: Interaction[Kolkra], value: Member, /
    ) -> Member:
        if not isinstance(interaction.user, Member):
            raise commands.NoPrivateMessage()
        await self.check(interaction.client, interaction.user, value)
        return value


class PosReason(Flags):
    reason: str | None = commands.flag(
        aliases=["r"],
        default=None,
        positional=True,
    )


class Channel(Flags):
    channel: GuildChannel | None = commands.flag(
        aliases=["c"],
        default=None,
    )


class ApplyFlags(PosReason):
    expiration: datetime | None = commands.flag(
        aliases=["e", "until"],
        default=None,
        converter=DatetimeConverter(prefer_dates_from="future"),
    )
    silent: bool = commands.flag(
        aliases=["nodm", "quiet"],
        default=False,
    )


class ChannelMuteApplyFlags(ApplyFlags, Channel):
    pass


class ChannelMuteLiftFlags(PosReason, Channel):
    pass
