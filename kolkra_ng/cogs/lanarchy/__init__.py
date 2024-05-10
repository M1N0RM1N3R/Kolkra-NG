from beanie.operators import Eq
from discord import Member
from discord.ext import commands
from discord.ext.commands._types import Check
from openskill.models import PlackettLuce

from kolkra_ng.bot import Kolkra
from kolkra_ng.checks import has_named_role
from kolkra_ng.cogs.lanarchy.config import LANarchyConfig
from kolkra_ng.cogs.lanarchy.models import LANarchyProfile
from kolkra_ng.context import KolkraContext
from kolkra_ng.embeds import InfoEmbed


class NotInMatchmakingChannel(commands.CheckFailure):
    def __init__(self, channel_id: int) -> None:
        super().__init__(f"This command can only be used in <#{channel_id}>.")


def in_matchmaking_channel() -> Check[KolkraContext]:
    def inner(ctx: KolkraContext) -> bool:
        if not isinstance(ctx.cog, LANarchyCog):
            raise TypeError()
        if ctx.channel.id != ctx.cog.config.matchmaking_channel:
            raise NotInMatchmakingChannel(ctx.cog.config.matchmaking_channel)
        return True

    return commands.check(inner)


class LANarchyCog(commands.Cog):
    def __init__(self, bot: Kolkra) -> None:
        super().__init__()
        self.bot = bot
        self.openskill = PlackettLuce()
        self.config = LANarchyConfig(**bot.config.cogs.get(self.__cog_name__, {}))

    async def cog_load(self) -> None:
        await self.bot.init_db_models(LANarchyProfile)

    @commands.hybrid_group()
    async def lanarchy(self, ctx: KolkraContext) -> None:
        """Commands for interacting with the LANarchy ranked system."""
        await ctx.send_help(ctx.command)

    @lanarchy.command(aliases=["rank", "lookup"])
    async def get_rank(
        self, ctx: KolkraContext, player: Member = commands.Author
    ) -> None:
        if not (
            profile := await LANarchyProfile.find(
                Eq(LANarchyProfile.user_id, player.id)
            ).first_or_none()
        ):
            await ctx.respond(
                embed=InfoEmbed(
                    title="Player not found",
                    description=(
                        "Looks like you're not in the system yet. "
                        f"Type {ctx.clean_prefix}{self.start_matchmaking.qualified_name} "
                        f"in <#{self.config.matchmaking_channel}> or join a matchmaking group there "
                        "and I'll get you set up."
                        if player == ctx.author
                        else f"I couldn't find {player.mention} in the system. "
                        "Chances are they just haven't started or joined a matchmaking group yet."
                    ),
                )
            )
            return
        await ctx.respond(embed=await profile.embed(self.config, ctx.bot))

    @lanarchy.command(aliases=["findmatch", "mkgroup"])
    @has_named_role("verified")
    @in_matchmaking_channel()
    async def start_matchmaking(self, ctx: KolkraContext) -> None:
        """Start a new matchmaking group."""
        raise NotImplementedError()


async def setup(bot: Kolkra) -> None:
    raise NotImplementedError()
    await bot.add_cog(LANarchyCog(bot))
