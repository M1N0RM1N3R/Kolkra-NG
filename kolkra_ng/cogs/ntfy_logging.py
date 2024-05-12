"""sends errors and warnings to ntfy.sh bc sentry is kinda overkill"""

from __future__ import annotations

import logging
from abc import ABC
from asyncio import Queue
from datetime import datetime, timedelta
from logging.handlers import QueueHandler
from typing import Annotated, Literal, TypeAlias

from aiohttp import ClientSession
from discord.ext import commands
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    HttpUrl,
    JsonValue,
    PlainValidator,
    Secret,
)
from pydantic_core import Url
from pydantic_extra_types.phone_numbers import PhoneNumber
from wonderwords.random_word import RandomWord

from kolkra_ng.bot import Kolkra

log = logging.getLogger(__name__)


class BaseAction(BaseModel, ABC):
    label: str
    clear: bool | None = None


class ViewAction(BaseAction):
    action: Literal["view"] = "view"
    url: Url


class AndroidBroadcastAction(BaseAction):
    action: Literal["broadcast"] = "broadcast"
    intent: str | None = None
    extras: dict[str, JsonValue | BaseModel]


class HttpAction(BaseAction):
    action: Literal["http"] = "http"
    url: HttpUrl
    method: (
        Literal[
            "GET",
            "HEAD",
            "POST",
            "PUT",
            "DELETE",
            "CONNECT",
            "OPTIONS",
            "TRACE",
            "PATCH",
        ]
        | str
        | None
    ) = None
    headers: dict[str, str] | None = None
    body: str | None = None


Action: TypeAlias = Annotated[
    ViewAction | AndroidBroadcastAction | HttpAction, Field(discriminator="action")
]


class NtfyRequest(BaseModel):
    topic: str
    message: str | None = None
    title: str | None = None
    tags: list[str] | None = None
    priority: int | None = Field(ge=1, le=5, default=None)
    actions: list[Action] | None = Field(max_length=3, default=None)
    click: Url | None = None
    attach: HttpUrl | None = None
    markdown: bool | None = None
    icon: HttpUrl | None = None
    filename: str | None = None
    delay: datetime | timedelta | None = None
    email: EmailStr | None = None
    call: PhoneNumber | None = None

    async def send(
        self,
        session: ClientSession,
        server: HttpUrl = HttpUrl(  # pyright: ignore [reportCallIssue]
            "https://ntfy.sh/"
        ),
    ) -> None:
        async with session.put(
            server.unicode_string(),
            json=self.model_dump(mode="json", exclude_defaults=True),
        ) as resp:
            resp.raise_for_status()


def random_topic() -> Secret[str]:
    """Logs and returns a random topic string consisting of 4 hyphen-delimited words.

    Returns:
        Secret[str]: A random topic string, wrapped in a Pydantic secret to prevent accidental logging.
    """
    pool = RandomWord()
    result = "-".join(pool.random_words(4))
    log.warning(
        "Using random default ntfy topic `%s`. THIS IS NOT RECOMMENDED FOR PRODUCTION!",
        result,
    )
    return Secret(result)


class NtfyLoggingConfig(BaseModel):
    minimum_level: Annotated[
        int,
        PlainValidator(
            lambda value: (
                value if isinstance(value, int) else logging.getLevelName(value)
            )
        ),
    ] = logging.WARNING
    topic: Secret[str] = Field(
        default_factory=random_topic  # Doing the smart/responsible thing and not using a static default topic name
    )
    server: HttpUrl = HttpUrl("https://ntfy.sh")  # pyright: ignore [reportCallIssue]

    aiohttp_params: dict = Field(default_factory=dict)


class NtfyLoggingCog(commands.Cog):
    def __init__(self, bot: Kolkra) -> None:
        super().__init__()
        self.bot = bot
        self.config = NtfyLoggingConfig(
            **self.bot.config.cogs.get(self.__cog_name__, {})
        )
        self.queue = Queue[logging.LogRecord]()
        self.handler = QueueHandler(
            self.queue  # pyright: ignore [reportArgumentType] # put_nowait is compatible, that's all we need
        )
        self.session = ClientSession(**self.config.aiohttp_params)

    async def _run(self) -> None:
        await self.bot.wait_until_ready()
        while True:
            record = await self.queue.get()
            if record.levelno < self.config.minimum_level:
                continue
            await NtfyRequest(
                topic=self.config.topic.get_secret_value(),
                title=f"{record.levelname} in {record.funcName} at {record.pathname}:{record.lineno}",
                markdown=True,
                message=record.message
                + (
                    f"\n# Exc info\n```\n{record.exc_text}\n```"
                    if record.exc_text
                    else ""
                ),
                tags=[record.levelname.lower(), f"shard{self.bot.shard_id}"],
                # Default level numbers range from 10 (debug) to 50 (critical), ntfy priorities range from 1 (min) to 5 (urgent).
                priority=max(min(1, round(record.levelno / 10)), 5),
            ).send(self.session, self.config.server)

    async def cog_load(self) -> None:
        logging.getLogger().addHandler(self.handler)
        self.task = self.bot.loop.create_task(self._run())

    async def cog_unload(self) -> None:
        logging.getLogger().removeHandler(self.handler)
        self.task.cancel()
        await self.session.close()


async def setup(bot: Kolkra) -> None:
    await bot.add_cog(NtfyLoggingCog(bot))
