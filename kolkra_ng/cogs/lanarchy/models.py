from __future__ import annotations

import logging
from typing import Annotated, ClassVar

import numpy as np
from beanie import Document, Indexed
from beanie.operators import GT, NE, Eq
from discord import Embed
from openskill.models import PlackettLuce, PlackettLuceRating
from pydantic import BaseModel
from typing_extensions import Self

from kolkra_ng.bot import Kolkra
from kolkra_ng.cogs.lanarchy.config import LANarchyConfig, RankConfig
from kolkra_ng.utils import safe_div

log = logging.getLogger(__name__)


class OpenSkillData(BaseModel):
    mu: float
    sigma: float

    @classmethod
    def from_openskill(cls, rating: PlackettLuceRating) -> Self:
        return cls(mu=rating.mu, sigma=rating.sigma)

    def to_openskill(self, model: PlackettLuce) -> PlackettLuceRating:
        return model.rating(**self.model_dump())


class Rank(BaseModel):
    config: RankConfig
    points: int


class LANarchyProfile(Document):
    user_id: Annotated[int, Indexed(unique=True)]
    openskill: OpenSkillData
    absolute_rank_points: int | None = None
    wins: int = 0
    losses: int = 0

    @classmethod
    def new(cls, user_id: int, model: PlackettLuce) -> Self:
        return cls(
            user_id=user_id,
            openskill=OpenSkillData.from_openskill(model.rating()),
        )

    @classmethod
    def match(
        cls: type[Self],
        winners: list[Self],
        losers: list[Self],
        model: PlackettLuce,
        config: LANarchyConfig,
    ) -> None:
        new_winner_ratings, new_loser_ratings = model.rate(
            [
                [p.openskill.to_openskill(model) for p in winners],
                [p.openskill.to_openskill(model) for p in losers],
            ]
        )
        for player, new_rating in zip(
            winners + losers, new_winner_ratings + new_loser_ratings, strict=False
        ):
            player.openskill = OpenSkillData.from_openskill(new_rating)
        for player in winners:
            if rank := player.rank(config):
                player.absolute_rank_points += (
                    rank.config.points_per_win
                )  # pyright: ignore [reportOperatorIssue]
            player.wins += 1
        for player in losers:
            if rank := player.rank(config):
                player.absolute_rank_points = max(
                    player.absolute_rank_points  # pyright: ignore [reportOptionalOperand]
                    - rank.config.points_per_loss,
                    0,
                )
            player.losses += 1

    def rank(self, config: LANarchyConfig) -> Rank | None:
        """Returns the player's standing within the configured rank ladder.
        For the top rank, `RankConfig.point_band` is ignored.

        Args:
            config (LANarchyConfig): The module config to pull the ladder from.

        Returns:
            Rank | None: The player's rank, if there is an `absolute_rank_points` value.
        """
        if not (running_count := self.absolute_rank_points):
            return None
        rank = None
        for rank in config.ranks:
            if running_count < rank.point_band:
                return Rank(config=rank, points=running_count)
            running_count -= rank.point_band
        return (
            Rank(config=rank, points=running_count + rank.point_band) if rank else None
        )

    async def place(self, base: int) -> None:
        ratings: list[float] = []
        points: list[int] = []

        class Projection(BaseModel):
            """MongoDB projection to fetch only what we need--the OpenSkill ratings and rank points for each player in the system."""

            rating: float
            absolute_rank_points: int

            class Settings:
                projection: ClassVar = {
                    "rating": "$openskill.mu",
                    "absolute_rank_points": 1,
                }

        async for player in self.find(
            NE(type(self).absolute_rank_points, None)
        ).project(Projection):
            ratings.append(player.rating)
            points.append(player.absolute_rank_points)
        if len(ratings) <= 2:
            self.absolute_rank_points = base
        else:
            self.absolute_rank_points = round(
                np.polynomial.Polynomial.fit(ratings, points, 2)(self.openskill.mu)
            )

    async def embed(self, config: LANarchyConfig, bot: Kolkra) -> Embed:
        rank = self.rank(config)
        member = bot.guild.get_member(self.user_id) or await bot.guild.fetch_member(
            self.user_id
        )

        embed = (
            Embed(
                title=rank.config.name if rank else "Unrated",
                description=(
                    None
                    if rank
                    else "Play your first few matches to get a rank and official LANarchy Power!"
                ),
            )
            .set_author(name=member.display_name, icon_url=member.display_avatar.url)
            .set_footer(text=f"{self.get_collection_name()} ID: {self.id}")
            .add_field(
                name="LANarchy Power",
                value=f"{round(self.openskill.mu, 2)}{' (unofficial estimate)' if not rank else ''}",
            )
            .add_field(
                name="Record",
                value=f"{self.wins}-{self.losses} ({safe_div(self.wins, self.wins + self.losses):.0%} win rate)",
            )
        )

        if rank:
            embed.set_thumbnail(url=rank.config.icon_url)
            if rank.config != config.ranks[-1]:
                points_to_promo = rank.config.point_band - rank.points
                progress = safe_div(rank.points, rank.config.point_band, 0)
                bar_size = 20
                fill = round(bar_size * progress)
                empty = bar_size - fill
                embed.add_field(
                    name="Rank Progress",
                    value=f"{rank.points}p {'🟦' * fill}{'⬛' * empty} {points_to_promo}p to rank-up",
                    inline=False,
                )
            else:
                position = (
                    await LANarchyProfile.find(
                        GT(
                            LANarchyProfile.absolute_rank_points,
                            self.absolute_rank_points,
                        )
                    ).count()
                    + 1
                )
                embed.add_field(name="Points", value=f"{rank.points}p (#{position})")

        return embed

    @classmethod
    async def fetch_or_new(cls, user_id: int, model: PlackettLuce) -> Self:
        return (await cls.find(Eq(cls.user_id, user_id)).first_or_none()) or cls.new(
            user_id, model
        )
