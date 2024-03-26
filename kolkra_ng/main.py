import asyncio
import logging

import discord
from rich.logging import RichHandler

from kolkra_ng.bot import Kolkra
from kolkra_ng.config import read_config

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(
            rich_tracebacks=True,
            tracebacks_suppress=[discord],
            tracebacks_show_locals=True,
        ),
    ],
)


async def main() -> None:
    """The main entrypoint."""
    config = read_config("config.toml")
    bot = Kolkra(config)
    await bot.load_extension("cogs")
    try:
        await bot.start(config.bot_token.get_secret_value())
    except KeyboardInterrupt:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
