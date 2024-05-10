import re
from pathlib import Path
from typing import Any

import tomli
from pydantic import BaseModel, Field, MongoDsn, Secret, field_validator
from typing_extensions import Self

from kolkra_ng.enums.staff_level import StaffLevel


class StaffRoles(BaseModel):
    """Represents role(s) assigned to staff members.
    The permission_role is the role ID that should be used to determine a user's StaffLevel,
    while optional cosmetic_roles are for display purposes and are not used in such decisions.
    """

    permission_role: int
    cosmetic_roles: list[int] = Field(default_factory=list)


class Config(BaseModel):
    bot_token: Secret[str]
    guild: int
    log_channel: int
    mongodb_url: Secret[MongoDsn] = (
        Secret(  # pyright: ignore [reportUnknownVariableType]
            MongoDsn(  # pyright: ignore [reportCallIssue]
                "mongodb://127.0.0.1:27017/kolkra_ng"
            )
        )
    )
    staff_roles: dict[StaffLevel, StaffRoles]
    named_roles: dict[str, int] = Field(default_factory=dict)
    cogs: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @field_validator("bot_token", mode="after")
    @classmethod
    def validate_token(cls, value: Any) -> Secret[str]:
        if not isinstance(value, Secret):
            raise TypeError()
        if not re.fullmatch(
            r"^([MN][\w-]{23,25})\.([\w-]{6})\.([\w-]{27,39})$",  # https://regex101.com/r/18EMsv/1
            value.get_secret_value(),
        ):
            raise ValueError()
        return value

    @classmethod
    def from_files(cls, *paths: Path) -> Self:
        """Parse a configuration from one or more TOML files.

        Returns:
            Self: The parsed config files.
        """
        data: dict[str, Any] = {}
        for path in paths:
            with open(path, "rb") as f:
                data |= tomli.load(f)
        return cls(**data)
