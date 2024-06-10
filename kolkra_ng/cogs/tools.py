import ipaddress
import random
from datetime import datetime
from hashlib import sha256
from typing import Any

import pint
from discord import Message, TextChannel, Thread, VoiceChannel
from discord.ext import commands
from discord.utils import TimestampStyle, format_dt, utcnow

from kolkra_ng.bot import Kolkra, KolkraContext
from kolkra_ng.converters import DatetimeConverter, Flags, SimpleConverter
from kolkra_ng.embeds import ErrorEmbed, OkEmbed


def pick_lan_ip(seed: Any = None) -> ipaddress.IPv4Address:
    ip = random.Random(seed).choice(
        list(ipaddress.IPv4Network("10.13.0.1/16", strict=False))
    )

    # 10.13.37.1 is the gateway IP in a LAN play setup.
    if ip == ipaddress.IPv4Address("10.13.37.1"):
        return pick_lan_ip()

    return ip


class RandomLanIpFlags(Flags):
    seeded: bool = commands.flag(
        default=False,
        aliases=["s", "deterministic", "d"],
        description="Generate your IP deterministically based on your user ID to avoid collisions.",
    )


class QuantityConverter(SimpleConverter[pint.Quantity]):
    async def parse(self, argument: str, *, bot: Kolkra) -> pint.Quantity:
        return bot.typed_get_cog(
            ToolsCog
        ).ureg.Quantity(  # pyright: ignore [reportOptionalMemberAccess, reportReturnType]
            argument
        )

    async def generate_autocomplete(self, value: pint.Quantity, *, bot: Kolkra) -> str:
        return f"{value:P}"


class ToolsCog(commands.Cog):
    def __init__(self, bot: Kolkra) -> None:
        super().__init__()
        self.bot = bot
        self.ureg = pint.UnitRegistry(
            autoconvert_offset_to_baseunit=True, default_as_delta=False
        )

    @commands.hybrid_command(aliases=["lanip"])
    async def random_lan_ip(
        self, ctx: KolkraContext, *, flags: RandomLanIpFlags
    ) -> None:
        """Generate a random LAN play IP."""
        seed = (
            sha256(ctx.bot.config.bot_token.get_secret_value().encode()).hexdigest()
            + str(ctx.author.id)
            if flags.seeded
            else None
        )
        await ctx.respond(
            embed=OkEmbed(
                title="Random LAN IP",
                description=f"Your LAN IP is {pick_lan_ip(seed)}",
            ),
            ephemeral=True,
        )

    @commands.hybrid_command(aliases=["top"])
    async def jump_to_top(
        self,
        ctx: KolkraContext,
        channel: TextChannel | Thread | VoiceChannel = commands.CurrentChannel,
    ) -> None:
        """Returns a link to jump to the top of a channel or thread."""
        async for message in channel.history(limit=1, oldest_first=True):
            first_message: Message = message
            await ctx.respond(
                embed=OkEmbed(
                    url=first_message.jump_url,
                    title="Jump to top",
                    description=f"Follow this link to jump to the top of {channel.mention}.",
                ),
                ephemeral=True,
            )
            return
        await ctx.respond(
            embed=ErrorEmbed(
                description="I can't seem to get a link to the top of this channel. "
                "I guess you could do [this](https://www.youtube.com/watch?v=dap5lEuS5uM)..."
            ),
            ephemeral=True,
        )

    @commands.hybrid_command(aliases=["ts"], rest_is_raw=True)
    async def timestamp(
        self,
        ctx: KolkraContext,
        style: TimestampStyle | None = None,
        *,
        when: datetime = commands.parameter(
            description="The date/time to convert",
            converter=DatetimeConverter("future"),
            default=lambda _: utcnow(),
            displayed_default="now",
        ),
    ) -> None:
        """Get a Discord-formatted timestamp for a specific date/time."""
        await ctx.respond(
            embed=OkEmbed(description=f"`{format_dt(when, style)}`").add_field(
                name="Preview", value=format_dt(when, style)
            ),
            ephemeral=True,
        )

    @commands.hybrid_command(rest_is_raw=True)
    async def convert(
        self,
        ctx: KolkraContext,
        *,
        quantity: pint.Quantity = commands.parameter(converter=QuantityConverter()),
    ) -> None:
        """Convert a measurement into several different units.
        Input is parsed and converted using the [pint](https://pint.readthedocs.io/en/stable/getting/tutorial.html#string-parsing) library.
        """
        pq = self.ureg.Quantity(quantity)
        results = "\n".join(f"- {pq.to(u):~P}" for u in pq.compatible_units())
        await ctx.respond(
            embed=OkEmbed(description=f"{pq:~P} is equivalent to:\n{results}")
        )


async def setup(bot: Kolkra) -> None:
    await bot.add_cog(ToolsCog(bot))
