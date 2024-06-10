from typing import Literal

from discord import (
    Color,
    Embed,
    ForumChannel,
    Game,
    Member,
    Role,
    StageChannel,
    TextChannel,
    VoiceChannel,
)
from discord.abc import GuildChannel
from discord.ext import commands

from kolkra_ng.bot import Kolkra
from kolkra_ng.checks import is_staff_level
from kolkra_ng.context import KolkraContext
from kolkra_ng.converters import Flags, unicode_emoji_converter
from kolkra_ng.embeds import AccessDeniedEmbed, ErrorEmbed, InfoEmbed, OkEmbed, icons8
from kolkra_ng.enums.staff_level import StaffLevel
from kolkra_ng.utils import audit_log_reason_template, update_member_roles


class AdminCog(commands.Cog):
    """Administrative commands."""

    def __init__(self, bot: Kolkra) -> None:
        super().__init__()
        self.bot = bot

    @commands.hybrid_command(aliases=["say"], rest_is_raw=True)
    @commands.guild_only()
    @commands.check_any(is_staff_level(StaffLevel.admin), commands.is_owner())
    async def echo(
        self,
        ctx: KolkraContext,
        channel: TextChannel = commands.CurrentChannel,
        *,
        content: str,
    ) -> None:
        """Make the bot say anything!"""
        if ctx.guild != channel.guild:
            await ctx.respond(
                embed=AccessDeniedEmbed(
                    description="You cannot echo messages across guilds."
                )
            )
            return
        await channel.send(content)
        if ctx.interaction:
            await ctx.respond(
                embed=OkEmbed(description="Sent message."), ephemeral=True
            )

    @commands.hybrid_command(aliases=["presence", "setplaying"], rest_is_raw=True)
    @commands.check_any(is_staff_level(StaffLevel.admin), commands.is_owner())
    async def change_presence(
        self, ctx: KolkraContext, *, status: str | None = None
    ) -> None:
        """Change the bot's status message."""
        await ctx.bot.change_presence(activity=Game(status) if status else None)
        await ctx.respond(
            embed=OkEmbed(
                description=(
                    f"Set status message to {status!r}."
                    if status
                    else "Cleared status message."
                )
            )
        )

    class RenameChannelFlags(Flags):
        emoji: str = commands.flag(converter=unicode_emoji_converter)
        name: str
        channel: TextChannel | VoiceChannel | StageChannel | ForumChannel | None = (
            commands.flag(default=None)
        )

    @commands.hybrid_command(aliases=["formatname"])
    @commands.guild_only()
    @is_staff_level(StaffLevel.mod)
    @commands.bot_has_permissions(manage_channels=True)
    async def rename_channel(
        self, ctx: KolkraContext, *, flags: RenameChannelFlags
    ) -> None:
        """Rename a channel according to the server's channel style."""
        if not isinstance(ctx.channel, GuildChannel):
            raise commands.NoPrivateMessage()
        channel = flags.channel or ctx.channel
        if not channel.category:
            await ctx.respond(
                embed=ErrorEmbed(
                    title="Uncategorized channel",
                    description="Formatting the names of channels not in a category is not currently supported.",
                )
            )
            return

        sibling_channels = channel.category.channels
        if channel == sibling_channels[0]:
            bracket = "┏"
        elif channel == sibling_channels[-1]:
            bracket = "┗"
        else:
            bracket = "︱"

        formatted = f"{bracket}･{flags.emoji}･{flags.name}"
        await channel.edit(
            name=formatted,
            reason=audit_log_reason_template(
                author_name=ctx.author.name,
                author_id=ctx.author.id,
                reason=f"Used {ctx.invoked_with}",
            ),
        )

        await ctx.respond(embed=OkEmbed(description="Channel renamed."))

    @commands.hybrid_command(aliases=["stafflevel"])
    @commands.guild_only()
    @is_staff_level(StaffLevel.arbit)
    @commands.bot_has_permissions(manage_roles=True)
    async def promote(
        self,
        ctx: KolkraContext,
        user: Member,
        to: Literal[
            tuple(x.name for x in StaffLevel)  # pyright: ignore # noqa: PGH003
        ],
    ) -> None:
        """Promote (or demote) a user to a staff level.
        You can only promote users below your own staff level to a staff level below your own.
        """
        to = StaffLevel[to]
        if not (ctx.guild and isinstance(ctx.author, Member)):
            raise commands.NoPrivateMessage()

        if user == ctx.author:
            await ctx.respond(
                embed=AccessDeniedEmbed(
                    description="You can't promote yourself!"
                ).set_image(
                    url="https://i.kym-cdn.com/photos/images/original/001/510/176/e33.jpg"
                )
            )
            return

        author_level = ctx.bot.get_staff_level_for(ctx.author) or 0

        allowed_levels = ", ".join(
            level.name for level in StaffLevel if level < author_level
        )

        if to >= author_level:
            await ctx.respond(
                embed=AccessDeniedEmbed(
                    description="You can only promote users to a staff level below yours."
                ).add_field(name="Allowed levels", value=allowed_levels)
            )
            return

        target_level = ctx.bot.get_staff_level_for(user) or 0

        if target_level >= author_level:
            await ctx.respond(
                embed=AccessDeniedEmbed(
                    description="You can only update the staff level of users with a staff level below yours."
                ).add_field(name="Allowed levels", value=allowed_levels)
            )
            return

        if target_level == to:
            await ctx.respond(
                embed=InfoEmbed(
                    description=f"{user.mention} is already a{'n' if to.name[0].lower() in 'aeiou' else ''} {to.name}."
                )
            )
            return

        update: dict[Role | None, bool] = {}

        for level in StaffLevel:
            roles = ctx.bot.config.staff_roles[level]
            state = level <= to
            update.update(
                {
                    ctx.guild.get_role(role_id): state
                    for role_id in [
                        roles.permission_role,
                        *roles.cosmetic_roles,
                    ]
                }
            )

        alr = audit_log_reason_template(
            author_name=ctx.author.name,
            author_id=ctx.author.id,
            reason=f"Promoting to {to.name}",
        )

        update.pop(
            None, None
        )  # Remove None from the dict in case any configured roles don't exist
        await update_member_roles(
            update, user, reason=alr  # pyright: ignore [reportArgumentType]
        )
        await ctx.bot.webhooks.send(
            ctx.bot.log_channel,
            embed=Embed(title="Staff Promotion", color=Color.gold())
            .set_thumbnail(url=icons8("corporal-cpl"))
            .add_field(name="User", value=user.mention)
            .add_field(name="Promoted by", value=ctx.author.mention)
            .add_field(name="To level", value=to.name),
        )

        await ctx.respond(
            embed=OkEmbed(
                description=f"{user.mention} is now a{'n' if to.name[0].lower() in 'aeiou' else ''} {to.name}!"
            )
        )


async def setup(bot: Kolkra) -> None:
    await bot.add_cog(AdminCog(bot))
