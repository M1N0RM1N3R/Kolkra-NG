import asyncio
import logging

from rich.logging import RichHandler

from kolkra_ng.bot import Kolkra
from kolkra_ng.config import read_config

FORMAT = "%(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])


async def main() -> None:
    """The main entrypoint."""
    config = read_config("config.toml")
    bot = Kolkra(config)
    try:
        await bot.start(config.bot_token.get_secret_value())
    except KeyboardInterrupt:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
