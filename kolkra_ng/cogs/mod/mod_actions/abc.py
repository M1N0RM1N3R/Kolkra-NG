import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from beanie.odm.queries.find import FindMany
from beanie.operators import Eq
from discord import Embed, Member
from discord.utils import format_dt, utcnow
from pydantic import BaseModel, Field
from typing_extensions import Self

from kolkra_ng.bot import Kolkra
from kolkra_ng.db_types import KolkraDocument, UtcDateTime
from kolkra_ng.utils import audit_log_reason_template

if TYPE_CHECKING:
    from kolkra_ng.cogs.mod import ModCog

log = logging.getLogger(__name__)


class ModActionLift(BaseModel):
    lifter_id: int
    reason: str | None = None
    timestamp: UtcDateTime = Field(default_factory=utcnow)


class ModAction(KolkraDocument, ABC):
    """
    To implement:
    - noun
    - dm_base
    - log_base
    - apply
    - lift
    """

    class Settings:
        is_root = True

    guild_id: int
    issuer_id: int
    target_id: int
    reason: str | None = None
    timestamp: UtcDateTime = Field(default_factory=utcnow)
    expiration: UtcDateTime | None = None
    lifted: ModActionLift | None = None

    @classmethod
    @abstractmethod
    def noun(cls) -> str:
        return "restriction"

    @abstractmethod
    def dm_base(self) -> Embed:
        """A base embed for DMs to send to target users.
        This method should be implemented by subclasses.

        Returns:
            Embed: The base embed.
        """
        pass

    async def dm_embed(self, bot: Kolkra) -> Embed:
        """Adds specific details to a base embed to DM to the target.

        Args:
            bot (Kolkra): The bot instance to use.

        Returns:
            Embed: The final embed.
        """
        embed = self.dm_base().set_footer(
            text=f"{self.get_collection_name()} ID: {self.id}"
        )
        embed.timestamp = self.timestamp
        if guild := bot.get_guild(self.guild_id):
            embed.set_author(
                name=guild.name,
                icon_url=icon.url if (icon := guild.icon) else None,
            )
        if self.reason:
            embed.add_field(name="The given reason is", value=self.reason)
        if self.expiration:
            embed.add_field(
                name=f"This {self.noun()} expires",
                value=format_dt(self.expiration),
            )
        return embed

    @abstractmethod
    def log_base(self) -> Embed:
        """A base embed for messages to post in the modlog.
        This method should be implemented by subclasses.

        Returns:
            Embed: The base embed.
        """
        pass

    async def log_embed(self) -> Embed:
        """Adds specific details to a base embed to post in the modlog.

        Args:
            bot (Kolkra): The bot instance to use.

        Returns:
            Embed: The final embed.
        """
        embed = (
            self.log_base()
            .set_footer(text=f"{self.get_collection_name()} ID: {self.id}")
            .add_field(
                name="Issued",
                value=f"by <@{self.issuer_id}> at {format_dt(self.timestamp)}",
            )
            .add_field(name="Target", value=f"<@{self.target_id}>")
            .add_field(name="Reason", value=self.reason)
            .add_field(
                name="Expiration",
                value=(format_dt(self.expiration) if self.expiration else "None"),
            )
        )
        if self.lifted:
            embed.add_field(
                name="Lifted",
                value=f"by <@{self.lifted.lifter_id}> at {format_dt(self.lifted.timestamp)}",
            ).add_field(name="Lift reason", value=self.lifted.reason)
        return embed

    def apply_audit_reason(
        self,
        bot: Kolkra,
    ) -> str:
        return audit_log_reason_template(
            author_name=(user.name if (user := bot.get_user(self.issuer_id)) else None),
            author_id=self.issuer_id,
            reason=self.reason,
            case_id=f"{self.get_collection_name()}:{self.id}",
            expires=self.expiration,
        )

    @abstractmethod
    async def apply(self, cog: "ModCog") -> None:
        """Do whatever needs to be done to apply the restriction.
        This method should be implemented by subclasses.

        Args:
            cog (ModCog): The cog triggering the action.
        """
        pass

    @abstractmethod
    async def lift(
        self, cog: "ModCog", author: Member, lift_reason: str | None
    ) -> None:
        """Do whatever needs to be done to remove the restriction.
        This method should be implemented by subclasses.

        Args:
            cog (ModCog): The cog triggering the lift.
            author (Member): The user who initiated the lift.
            lift_reason (str | None): The reason the user provided for lifting the action.
        """
        pass

    @classmethod
    def fetch_existing_for(
        cls, guild_id: int, target_id: int, *, include_lifted: bool = False, **kwargs
    ) -> FindMany[Self]:
        cur = cls.find(
            Eq(cls.guild_id, guild_id), Eq(cls.target_id, target_id), **kwargs
        )
        return cur if include_lifted else cur.find(Eq(cls.lifted, None))
