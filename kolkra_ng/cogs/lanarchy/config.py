from typing import Annotated

from pydantic import AfterValidator, BaseModel, HttpUrl, PositiveInt


class RankConfig(BaseModel):
    name: str
    role_id: int
    icon_url: HttpUrl
    point_band: PositiveInt
    points_per_win: PositiveInt
    points_per_loss: PositiveInt
    position: float


class LANarchyConfig(BaseModel):
    ranks: Annotated[
        list[RankConfig],
        AfterValidator(lambda x: sorted(x, key=lambda i: i.position)),
    ]
    placement_role: int
    ping_role: int
    matchmaking_channel: int
