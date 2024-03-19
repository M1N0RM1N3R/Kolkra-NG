import re
from typing import Any

import tomli
from pydantic import BaseModel, SecretStr, field_validator


class Config(BaseModel):
    bot_token: SecretStr
    guild_id: int

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


def read_config(path: str = "config.toml") -> Config:
    with open(path, "rb") as f:
        data = tomli.load(f)
    return Config(**data)
