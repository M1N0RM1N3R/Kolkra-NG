import logging
from datetime import datetime, timedelta
from typing import Literal

import dateparser
import emoji
import pytimeparse
from discord import Interaction, app_commands
from discord.ext import commands

log = logging.getLogger(__name__)


class Flags(commands.FlagConverter):
    pass


class BadDatetime(commands.BadArgument):
    def __init__(self, argument: str):
        super().__init__(f"{argument!r} is not in a known date/time format.")


class DatetimeConverter(commands.Converter[datetime], app_commands.Transformer):
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

    def parse(self, argument: str) -> datetime:
        if not (dt := self.parser.get_date_data(argument)["date_obj"]):
            raise BadDatetime(argument)
        return dt.replace(microsecond=0)

    async def convert(self, ctx: commands.Context, argument: str) -> datetime:
        return self.parse(argument)

    async def transform(self, interaction: Interaction, value: str, /) -> datetime:
        return self.parse(value)

    async def autocomplete(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, interaction: Interaction, value: str, /
    ) -> list[app_commands.Choice[str]]:
        try:
            iso = self.parse(value).isoformat()
        except commands.BadArgument:
            return []
        return [app_commands.Choice(name=iso, value=iso)]


class BadTimeDelta(commands.BadArgument):
    def __init__(self, argument: str):
        super().__init__(f"{argument!r} is not in a known duration format.")


class TimeDeltaConverter(commands.Converter[timedelta], app_commands.Transformer):
    def parse(self, argument: str) -> timedelta:
        secs = pytimeparse.parse(argument)
        if secs is None:
            raise BadTimeDelta(argument)
        return timedelta(seconds=secs)

    async def convert(self, ctx: commands.Context, argument: str) -> timedelta:
        return self.parse(argument)

    async def transform(self, interaction: Interaction, value: str, /) -> timedelta:
        return self.parse(value)

    async def autocomplete(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, interaction: Interaction, value: str, /
    ) -> list[app_commands.Choice[str]]:
        try:
            fmt = str(self.parse(value))
        except commands.BadArgument:
            return []
        return [app_commands.Choice(name=fmt, value=fmt)]


class BadUnicodeEmoji(commands.BadArgument):
    def __init__(self, argument: str) -> None:
        super().__init__(f"{argument!r} is not a valid Unicode emoji.")


def unicode_emoji_converter(argument: str) -> str:
    e = emoji.emojize(argument.strip())
    if not emoji.is_emoji(e):
        raise BadUnicodeEmoji(e)
    return e
