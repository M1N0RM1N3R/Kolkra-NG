import re
from pathlib import Path
from typing import Any

import tomli
from pydantic import (
    BaseModel,
    Field,
    JsonValue,
    MongoDsn,
    SecretStr,
    field_validator,
)


class Config(BaseModel):
    bot_token: SecretStr
    guild_id: int
    mongodb_url: MongoDsn = (  # pyright: ignore [reportUnknownVariableType]
        MongoDsn(  # pyright: ignore [reportCallIssue]
            "mongodb://127.0.0.1:27017"
        )
    )

    cogs: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)

    @field_validator("bot_token", mode="after")
    @classmethod
    def validate_token(cls, value: Any) -> SecretStr:
        if not isinstance(value, SecretStr):
            raise TypeError()
        if not re.fullmatch(
            r"^([MN][\w-]{23,25})\.([\w-]{6})\.([\w-]{27,39})$",  # https://regex101.com/r/18EMsv/1
            value.get_secret_value(),
        ):
            raise ValueError()
        return value


def read_config(*paths: Path) -> Config:
    data: dict[str, JsonValue] = {}
    for path in paths:
        with open(path, "rb") as f:
            data |= tomli.load(f)
    return Config(
        **data  # pyright: ignore [reportArgumentType] # Pydantic will coerce our data for us.
    )
