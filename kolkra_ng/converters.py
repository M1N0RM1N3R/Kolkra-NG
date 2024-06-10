import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Generic, Literal, TypeVar

import dateparser
import emoji
import pytimeparse
from discord import Interaction, app_commands
from discord.ext import commands

from kolkra_ng.bot import Kolkra
from kolkra_ng.context import KolkraContext

log = logging.getLogger(__name__)


class Flags(commands.FlagConverter):
    pass


T = TypeVar("T")


class SimpleConverter(commands.Converter[T], app_commands.Transformer, Generic[T], ABC):
    @abstractmethod
    async def parse(self, argument: str, *, bot: Kolkra) -> T:
        """Parse a value from a human-readable string into an object.

        Args:
            argument (str): The user-provided string.
            bot (Kolkra): The bot instance, if needed to return a dynamic value.

        Returns:
            T: The parsed object.
        """

    @abstractmethod
    async def generate_autocomplete(self, value: T, *, bot: Kolkra) -> str:
        """Return a human-readable string representation of a value that can be parsed back into the original value.
        For example, for a datetime converter, you may return an ISO 8601 formatted string.

        Args:
            value (T): The value parsed from user input.
            bot (Kolkra): The bot instance, if needed to return a dynamic value.

        Returns:
            str: A string representation to be returned to the user.
        """

    async def convert(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, ctx: KolkraContext, argument: str
    ) -> T:
        return await self.parse(argument, bot=ctx.bot)

    async def transform(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, interaction: Interaction[Kolkra], value: str, /
    ) -> T:
        return await self.parse(value, bot=interaction.client)

    async def autocomplete(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, interaction: Interaction[Kolkra], value: str, /
    ) -> list[app_commands.Choice[str]]:
        try:
            res = await self.generate_autocomplete(
                await self.parse(value, bot=interaction.client),
                bot=interaction.client,
            )
        except commands.BadArgument:
            return []
        return [app_commands.Choice(name=res, value=res)]


class BadDatetime(commands.BadArgument):
    def __init__(self, argument: str):
        super().__init__(f"{argument!r} is not in a known date/time format.")


class DatetimeConverter(SimpleConverter[datetime]):
    def __init__(
        self, prefer_dates_from: Literal["current_period", "past", "future"]
    ) -> None:
        super().__init__()
        self.parser = dateparser.date.DateDataParser(
            settings={
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DATES_FROM": prefer_dates_from,
            }
        )

    async def parse(self, argument: str, *, bot: Kolkra) -> datetime:
        if not (dt := self.parser.get_date_data(argument)["date_obj"]):
            raise BadDatetime(argument)
        return dt.replace(microsecond=0)

    async def generate_autocomplete(self, value: datetime, *, bot: Kolkra) -> str:
        return value.isoformat()


class BadTimeDelta(commands.BadArgument):
    def __init__(self, argument: str):
        super().__init__(f"{argument!r} is not in a known duration format.")


class TimeDeltaConverter(SimpleConverter[timedelta]):
    async def parse(self, argument: str, *, bot: Kolkra) -> timedelta:
        secs = pytimeparse.parse(argument)
        if secs is None:
            raise BadTimeDelta(argument)
        return timedelta(seconds=secs)

    async def generate_autocomplete(self, value: timedelta, *, bot: Kolkra) -> str:
        return str(value)


class BadUnicodeEmoji(commands.BadArgument):
    def __init__(self, argument: str) -> None:
        super().__init__(f"{argument!r} is not a valid Unicode emoji.")


def unicode_emoji_converter(argument: str) -> str:
    e = emoji.emojize(argument.strip())
    if not emoji.is_emoji(e):
        raise BadUnicodeEmoji(e)
    return e
