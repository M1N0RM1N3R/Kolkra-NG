"""Miscellaneous functions/classes that I couldn't think of a better place to put."""

from abc import ABC
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Generic, ParamSpec, TypeVar

from beanie import Link
from discord import Member, Role
from discord.ext import commands
from pydantic import Field
from typing_extensions import Never

from kolkra_ng.db_types import DocumentT, KolkraDocument

T = TypeVar("T")


def audit_log_reason_template(
    *,
    author_name: str | None = None,
    author_id: int,
    reason: str | None = None,
    **extras,
) -> str:
    """A lightweight-ish template for audit log reason strings with added author info for accountability.

    Args:
        author_id (int): The author's user ID.
        author_name (str | None, optional): The author's username, if available in the current context. Defaults to None.
        reason (str | None, optional): The reason for the operation. Defaults to None.

    Raises:
        ValueError: The combined string is over 512 characters long--the maximum allowed by Discord.

    Returns:
        str: The templated reason string.
    """
    extra_fmt = "".join(
        f" ({k.replace('_', ' ')}: {v})" for k, v in extras.items() if v is not None
    )
    output = f"{author_name or '<UNKNOWN>'}|{author_id}: {reason or 'no reason provided'}{extra_fmt}"
    if len(output) > 512:
        raise ValueError()
    return output


def safe_div(dividend: float, divisor: float, default: T = None) -> float | T:
    """A teensy-tiny function to help avoid accidentally dividing by zero.
    This function is literally more docstring than code.

    Args:
        dividend (float): The dividend, i.e. the x of x/y.
        divisor (float): The divisor, i.e. the y.
        default (T, optional): A default value to return if the divisor is 0. Defaults to None.

    Returns:
        float | T: The result of the division operation, or the default value if the divisor is zero.
    """
    if divisor == 0:
        return default
    return dividend / divisor


class RoleAboveBot(commands.CheckFailure):
    def __init__(self, role: Role) -> None:
        super().__init__(f"{role.mention} is the same as or above my top role.")
        self.role = role


async def update_member_roles(
    roles: Mapping[Role, bool], target: Member, **kwargs
) -> None:
    """Update a member's posession of certain roles to a given state.

    Args:
        roles (Mapping[Role, bool]): A mapping of roles to their desired states--True to add, False to remove.
        target (Member): The member to apply these changes to.

    Raises:
        RoleAboveBot: Self-explanatory.
    """
    add: list[Role] = []
    remove: list[Role] = []
    for role, state in roles.items():
        if state == (role in target.roles):
            continue
        if role >= role.guild.me.top_role:
            raise RoleAboveBot(role)
        (add if state else remove).append(role)
    await target.add_roles(*add, **kwargs)
    await target.remove_roles(*remove, **kwargs)


InT = TypeVar("InT")
OutT = TypeVar("OutT")
ParamT = ParamSpec("ParamT")


@dataclass
class NoTransformerFound(TypeError):
    transformers_for_types: set[type]
    received_type: type


def validate_by_input_type(
    transformers: Mapping[type, Callable[..., OutT]]
) -> Callable[..., OutT]:
    """Returns a function that runs objects through a transformer function based on its type.

    Args:
        transformers (Mapping[type, Callable[..., OutT]]): A mapping of types to functions that take an instance of the key type and return the output type

    Returns:
        Callable[..., OutT]: The combined validator function.
    """

    def inner(i: Any) -> OutT:
        for t, fn in transformers.items():
            if isinstance(i, t):
                return fn(i)
        raise NoTransformerFound(set(transformers.keys()), type(i))

    return inner


def raise_exc(exc: Exception) -> Never:
    raise exc


class Match(KolkraDocument, Generic[DocumentT], ABC):
    teams: list[Annotated[set[Link[DocumentT]], Field(min_length=1, max_length=4)]]
    winner_index: int

    async def check_valid(self) -> None:
        if self.winner_index is not None and self.winner_index not in range(
            len(self.teams)
        ):
            raise IndexError(self)


# https://stackoverflow.com/a/952952
def flatten(xss: Iterable[Iterable[T]]) -> Iterable[T]:
    return (x for xs in xss for x in xs)
