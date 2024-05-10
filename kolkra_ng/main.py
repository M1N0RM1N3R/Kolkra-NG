import asyncio
import logging
from pathlib import Path

import discord
from rich.logging import RichHandler

from kolkra_ng.bot import Kolkra
from kolkra_ng.config import Config

logging.basicConfig(
    format="%(message)s",
    level=0,
    handlers=[
        RichHandler(
            rich_tracebacks=True,
            tracebacks_suppress=[discord],
            tracebacks_show_locals=True,
            level=logging.INFO,
        )
    ],
)
logging.captureWarnings(True)

log = logging.getLogger(__name__)


async def main() -> None:
    log.info("Parsing configuration")
    config = Config.from_files(Path("config.toml"))
    log.info("Initializing client")
    bot = Kolkra(config)

    log.info("Starting up")
    try:
        await bot.start(config.bot_token.get_secret_value())
    except KeyboardInterrupt:
        log.fatal("Caught KeyboardInterrupt")
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
