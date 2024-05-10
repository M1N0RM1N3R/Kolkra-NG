from discord import Member
from discord.ext import commands
from discord.ext.commands._types import Check

from kolkra_ng.context import KolkraContext
from kolkra_ng.enums.staff_level import StaffLevel


class InsufficientStaffLevel(commands.CheckFailure):
    def __init__(self, author_level: StaffLevel | None, min_level: StaffLevel) -> None:
        min_str = min_level.name
        author_str = author_level.name if author_level is not None else "none"
        super().__init__(
            message=f"You must be at least {min_str} to use this command. (your staff level: {author_str})"
        )
        self.author_level = author_level
        self.required_level = min_level


def is_staff_level(min_level: StaffLevel) -> Check[KolkraContext]:
    """Command decorator that requires users to be at least a certain StaffLevel to use the command.

    Args:
        min_level (StaffLevel): The minimum level the user must be to use the command.
    """

    def inner(ctx: KolkraContext) -> bool:
        if not isinstance(ctx.author, Member):
            raise commands.NoPrivateMessage()
        if (
            not (author_level := ctx.bot.get_staff_level_for(ctx.author))
            or author_level < min_level
        ):
            raise InsufficientStaffLevel(author_level, min_level)
        return True

    return commands.check(inner)


class NotBooster(commands.CheckFailure):
    def __init__(self, message: str | None = None, *args) -> None:
        super().__init__(
            message or "You must be boosting the server to use this command.", *args
        )


def is_booster() -> Check[KolkraContext]:
    def inner(ctx: KolkraContext) -> bool:
        if not isinstance(ctx.author, Member):
            raise commands.NoPrivateMessage()
        if not ctx.author.premium_since:
            raise NotBooster()
        return True

    return commands.check(inner)


def has_named_role(name: str) -> Check[KolkraContext]:
    def inner(ctx: KolkraContext) -> bool:
        if not (ctx.guild and isinstance(ctx.author, Member)):
            raise commands.NoPrivateMessage()
        if not (role := ctx.guild.get_role(ctx.bot.config.named_roles[name])):
            raise ValueError()
        if role not in ctx.author.roles:
            raise commands.MissingRole(role.mention)
        return True

    return commands.check(inner)
