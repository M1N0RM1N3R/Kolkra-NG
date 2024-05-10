import logging
import time
from datetime import datetime
from typing import TypeVar

import psutil
from discord import Embed, Thread
from discord.ext import commands
from discord.utils import Coro, format_dt

from kolkra_ng.bot import Kolkra, KolkraContext
from kolkra_ng.embeds import InfoEmbed, OkEmbed, WarningEmbed, icons8
from kolkra_ng.webhooks import SupportsWebhooks

log = logging.getLogger(__name__)


def ms(s: float) -> str:
    return f"{round(s * 1000)}ms"


async def time_it(coro: Coro) -> str:
    """Measure how long a coroutine takes to execute.

    Args:
        coro (Coro): The coroutine to time.

    Returns:
        str: The time taken, formatted as milliseconds for display.
    """
    start = time.perf_counter()
    await coro
    return ms(time.perf_counter() - start)


async def test_webhook(bot: Kolkra, channel: SupportsWebhooks | Thread) -> None:
    if msg := (await bot.webhooks.send(channel, "testing webhook", wait=True)):
        # Creating a task--we're timing how long it takes to send a message,
        # not how long it takes to delete one--not to mention that it may fail.
        bot.loop.create_task(msg.delete())


T = TypeVar("T")


async def catch(coro: Coro[T]) -> T | Exception:
    """Catch and return exceptions thrown by this coroutine.

    Args:
        coro (Coro[T]): The coroutine to run.

    Returns:
        T | Exception: The value returned by the coroutine, or an exception if one was thrown.
    """
    try:
        return await coro
    except Exception as e:
        return e


class BasicCog(commands.Cog):
    def __init__(self, bot: Kolkra) -> None:
        super().__init__()
        self.bot = bot

    @commands.hybrid_command(aliases=["status"])
    async def ping(self, ctx: KolkraContext) -> None:
        """See various metrics about the bot."""
        results: dict[str, str | Exception] = {}

        process_start = datetime.fromtimestamp(psutil.Process().create_time())

        system_boot = datetime.fromtimestamp(psutil.boot_time())

        results["Discord latency"] = ms(ctx.bot.latency)
        results["Message latency"] = await catch(time_it(ctx.defer()))
        results["MongoDB latency"] = await catch(
            time_it(ctx.bot.motor.admin.command("ping"))
        )
        if isinstance(ctx.channel, SupportsWebhooks | Thread):
            results["Webhook latency"] = await catch(
                time_it(test_webhook(ctx.bot, ctx.channel))
            )
        results["Process uptime"] = f"since {format_dt(process_start, 'R')}"
        results["System uptime"] = f"since {format_dt(system_boot, 'R')}"

        all_good = all((not isinstance(x, Exception)) for x in results.values())

        if all_good:
            embed = OkEmbed(
                title="Pong!", description="Everything looks good."
            ).set_thumbnail(url=icons8("ping-pong"))
        else:
            embed = WarningEmbed(
                title="Uh oh...",
                description="One or more status checks raised an error. Some features may not work.",
            )
        for name, value in results.items():
            embed.add_field(name=name, value=value)
        await ctx.respond(embed=embed)

    @commands.hybrid_command(aliases=["github", "repo"])
    async def source(self, ctx: KolkraContext) -> None:
        """Get a link to the bot's source code on GitHub."""
        await ctx.respond(
            embed=InfoEmbed(
                title="I'm powered by free (as in speech) software!",
                description="My source code is licensed under the GNU GPLv3. "
                "Feel free to examine it, copy it, and modify it to suit your needs. "
                "If you want, you can also give me new features and help fix any bugs you encounter.",
            ).add_field(
                name="Link to repo",
                value="https://github.com/m1n0rm1n3r/kolkra-ng",
            )
        )

    @commands.hybrid_command(aliases=["attribution", "acknowledgements", "credits"])
    async def thanks(self, ctx: KolkraContext) -> None:
        """🤍"""
        await ctx.respond(
            embed=Embed(title="Thank you for making Kolkra-NG possible!")
            .set_thumbnail(url=icons8("heart-puzzle"))
            .add_field(name="Icons", value="[Icons8](https://icons8.com/)")
            .add_field(name="discord.py", value="[Danny](https://github.com/Rapptz)")
            .add_field(name="Contributors", value="(your name/link here!)")
        )


async def setup(bot: Kolkra) -> None:
    await bot.add_cog(BasicCog(bot))
