from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Generic, TypeVar

from beanie import Document, Indexed, Link, PydanticObjectId
from discord import Role
from pydantic import BaseModel, Field
from pydantic.functional_validators import AfterValidator
from typing_extensions import Self

from kolkra_ng.bot import Kolkra

T = TypeVar("T")
DocumentT = TypeVar("DocumentT", bound=Document)


@dataclass
class ReferenceNotFound(ValueError, Generic[DocumentT]):
    link: Link[DocumentT]


async def fetch_link(
    klass: type[DocumentT], link: Link[DocumentT], **kwargs
) -> DocumentT:
    fetched = link.fetch(**kwargs)
    if not isinstance(fetched, klass):
        raise ReferenceNotFound(link)
    return fetched


class KolkraDocument(Document):
    id: PydanticObjectId | None = Field(default_factory=PydanticObjectId)

    async def fetch(self, *args, **kwargs) -> Self:
        """Helper for dealing with Links that are already fetched."""
        return self


UtcDateTime = Annotated[
    datetime,
    AfterValidator(
        lambda dt: (
            dt.replace(tzinfo=timezone.utc)
            if dt.tzinfo is None
            else dt.astimezone(tz=timezone.utc)
        )
    ),
]
"""A datetime that is assumed to be in UTC unless explicitly included.
"""


class RoleRepr(BaseModel):
    guild_id: Annotated[int, Indexed()]
    role_id: int

    @classmethod
    def _from(cls, role: Role) -> Self:
        return cls(guild_id=role.guild.id, role_id=role.id)

    async def get(self, bot: Kolkra) -> Role | None:
        return (
            bot.get_guild(self.guild_id) or await bot.fetch_guild(self.guild_id)
        ).get_role(self.role_id)

    def __hash__(self) -> int:
        return hash((self.guild_id, self.role_id))
