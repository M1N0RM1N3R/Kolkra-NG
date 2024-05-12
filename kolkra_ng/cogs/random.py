import asyncio
import random
import re
from datetime import timedelta

import humanize
from discord import Embed, Member, Message, Object, Thread
from discord.abc import GuildChannel
from discord.ext import commands
from discord.utils import utcnow
from pydantic import BaseModel

from kolkra_ng.bot import Kolkra
from kolkra_ng.checks import is_staff_level
from kolkra_ng.context import KolkraContext
from kolkra_ng.embeds import InfoEmbed, OkEmbed, icons8
from kolkra_ng.enums.staff_level import StaffLevel
from kolkra_ng.webhooks import SupportsWebhooks


class RandomConfig(BaseModel):
    birthday_role: int | None = None


class RandomCog(commands.Cog):
    """Random commands for fun ~~and profit~~."""

    def __init__(self, bot: Kolkra) -> None:
        super().__init__()
        self.bot = bot
        self.config = RandomConfig(**bot.config.cogs.get(self.__cog_name__, {}))

    @commands.Cog.listener("on_message")
    async def rhymitis(self, message: Message) -> None:
        if message.author.id == 999714812068110436 and message.mention_everyone:  # Kyro
            await message.reply(
                "Oh no! Kyro's chronic at-everyone-itis is flaring up again!"
            )

    @commands.Cog.listener("on_message")
    async def at_someone(self, message: Message) -> None:
        """help ive fallen and i cant get up i need @someone"""
        if "@someone" not in message.content:
            return
        if not isinstance(message.channel, GuildChannel):
            await message.reply(
                embed=InfoEmbed(
                    title="Want to ping @someone?",
                    description="This only works in a server channel.",
                )
            )
            return
        if not isinstance(message.channel, SupportsWebhooks | Thread):
            await message.reply(
                embed=InfoEmbed(
                    title="No webhook support here!",
                    description="I can't make webhooks to send the ctrl-H'd message through in this channel.",
                )
            )
            return
        new_content = re.sub(
            r"@someone",
            lambda _: f"<@{random.choice(message.channel.members).id}>",  # pyright: ignore [reportAttributeAccessIssue]
            message.content,
        )
        await self.bot.webhooks.send(
            message.channel,
            new_content,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
        )
        await message.delete()

    @commands.hybrid_command(rest_is_raw=True)
    async def bean(
        self, ctx: KolkraContext, target: Member, *, reason: str | None = None
    ) -> None:
        """Smack someone (or even yourself) with a squeaky toy ban hammer filled with beeeeeans."""
        await ctx.respond(embed=OkEmbed(description=f"{target} is now 🫘d."))

    @commands.hybrid_command(rest_is_raw=True)
    async def warm(
        self, ctx: KolkraContext, target: Member, *, reason: str | None = None
    ) -> None:
        """Sometimes, people just need a little heat."""
        celsius = round(
            random.random() * 20 + 22, 1
        )  # 22°C (upper room temp) - 42°C (maximum temp humans can withstand)
        fahrenheit = round((celsius * 1.8) + 32, 2)
        await ctx.respond(
            embed=OkEmbed(
                description=f"{target} warmed. User is now {celsius}°C/{fahrenheit}°F."
            )
        )

    @commands.hybrid_command(aliases=["cakeday", "birthday", "bday", "🎂"])
    @commands.guild_only()
    @is_staff_level(StaffLevel.admin)
    @commands.bot_has_permissions(manage_roles=True)
    async def happy_birthday(
        self, ctx: KolkraContext, birthday_boi: Member, age: int | None = None
    ) -> None:
        """Wish someone a happy birthday. (and give them the birthday role, if it's configured)"""
        if not ctx.guild:
            raise commands.NoPrivateMessage()
        await ctx.respond(
            content=birthday_boi.mention,
            embed=Embed(
                title=f"Happy birthday, {birthday_boi.display_name}!",
                description=f"{ctx.author.mention} (and the rest of the Splatfest staff team)"
                f" wishes you a happy {humanize.ordinal(age) + ' ' if age else ''}birthday!",
            ).set_thumbnail(url=icons8("birthday-cake")),
        )
        if self.config.birthday_role:
            await birthday_boi.add_roles(Object(self.config.birthday_role))
            self.bot.schedule(
                self.bot.http.remove_role,
                utcnow() + timedelta(days=1),
                birthday_boi.guild.id,
                birthday_boi.id,
                self.config.birthday_role,
            )

    @commands.hybrid_command(aliases=["8ball"], rest_is_raw=True)
    async def magic_8_ball(self, ctx: KolkraContext, *, question: str) -> None:
        """Ask the Magic 8-Ball a question.
        Spoiler alert: it's not the manifestation of some omniscent being--it's just a die in some dye.
        ||try saying that 5 times fast||
        """
        await ctx.defer()
        await asyncio.sleep(random.random() * 10)
        response = random.choice(
            [
                "It is certain.",
                "It is decidedly so.",
                "Without a doubt.",
                "Yes, definitely.",
                "You may rely on it.",
                "As I see it, yes.",
                "Most likely.",
                "Outlook good.",
                "Yes.",
                "Signs point to yes.",
                "Reply hazy, try again.",
                "Ask again later.",
                "Better not tell you now.",
                "Cannot predict now.",
                "Concentrate and ask again.",
                "Concentrate and try again.",
                "Don't count on it.",
                "My reply is no.",
                "My sources say no.",
                "Very doubtful.",
                "Outlook not so good.",
                "Outlook bad.",
                "Better not tell you now.",
                "Don't count on it.",
            ]
        )
        await ctx.respond(embed=Embed(title="The 8-ball says", description=response))


async def setup(bot: Kolkra) -> None:
    await bot.add_cog(RandomCog(bot))
