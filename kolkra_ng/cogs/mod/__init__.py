import asyncio
import logging
import re

from beanie import PydanticObjectId
from beanie.operators import NE
from discord import (
    BanEntry,
    Color,
    Embed,
    File,
    Forbidden,
    Guild,
    Member,
    Message,
    NotFound,
    Object,
    PartialMessageable,
    User,
)
from discord.abc import PrivateChannel, Snowflake
from discord.ext import commands
from discord.utils import format_dt, sleep_until

from kolkra_ng.bot import Kolkra
from kolkra_ng.checks import is_staff_level
from kolkra_ng.cogs.mod.converters import (
    ApplyFlags,
    ChannelMuteApplyFlags,
    ChannelMuteLiftFlags,
    TargetConverter,
)
from kolkra_ng.cogs.mod.message_select import (
    SelectMessageFlags,
    generate_message_log,
    mass_delete,
)
from kolkra_ng.cogs.mod.mod_actions.abc import ModAction, ModActionLift
from kolkra_ng.cogs.mod.mod_actions.channel_mute import MUTE_PERMS, ChannelMute
from kolkra_ng.cogs.mod.mod_actions.server_ban import ServerBan
from kolkra_ng.cogs.mod.mod_actions.softban import Softban
from kolkra_ng.cogs.mod.mod_actions.warning import ModWarning
from kolkra_ng.context import KolkraContext
from kolkra_ng.embeds import (
    AccessDeniedEmbed,
    ErrorEmbed,
    InfoEmbed,
    OkEmbed,
    WarningEmbed,
    icons8,
)
from kolkra_ng.enums.staff_level import StaffLevel
from kolkra_ng.error_handling import exc_info
from kolkra_ng.utils import audit_log_reason_template
from kolkra_ng.views.confirm import Confirm
from kolkra_ng.views.pager import Pager, group_embeds

log = logging.getLogger(__name__)


async def try_dm(bot: Kolkra, user_id: int, **kwargs) -> Message | None:
    if (
        dmable := bot.get_user(user_id)
        or await bot.fetch_user(user_id)
        or await bot.create_dm(Object(user_id))
    ):
        try:
            return await dmable.send(**kwargs)
        except Exception as e:
            log.warn("Couldn't send DM to %s", dmable, exc_info=exc_info(e))
    else:
        log.warn("Can't get DM channel for user ID %s", user_id)


MOD_ACTION_MODELS = [ServerBan, Softban, ChannelMute, ModWarning]

async def fetch_ban(target: Snowflake, guild: Guild) -> BanEntry | None:
    try: return await guild.fetch_ban(target)
    except NotFound: return None

class ModCog(commands.Cog):
    def __init__(self, bot: Kolkra) -> None:
        super().__init__()
        self.bot = bot
        self.__lift_tasks: dict[PydanticObjectId | None, asyncio.Task] = {}

    async def __delayed_lift(self, action: ModAction) -> None:
        if not action.expiration:
            raise ValueError(action)
        await sleep_until(action.expiration)
        log.info("Mod action %s expired, lifting", action)
        await self.do_lift(
            action,
            (
                self.bot.get_guild(action.guild_id)
                or await self.bot.fetch_guild(action.guild_id)
            ).me,
            "Expired",
            __exp=True,
        )

    async def cog_load(self) -> None:
        await self.bot.init_db_models(*MOD_ACTION_MODELS)
        for cls in MOD_ACTION_MODELS:
            async for action in cls.find(NE(cls.expiration, None)):
                log.info("Creating lift task for %s", action)
                self.__lift_tasks[action.id] = self.bot.loop.create_task(
                    self.__delayed_lift(action)
                )

    async def cog_unload(self) -> None:
        for k in list(self.__lift_tasks):
            self.__lift_tasks.pop(k).cancel()

    async def do_apply(
        self,
        action: ModAction,
        silent: bool = False,
    ) -> None:
        await action.save()
        if not silent:
            await try_dm(
                self.bot,
                action.target_id,
                embed=await action.dm_embed(self.bot),
            )
        await action.apply(self)
        if action.expiration:
            self.__lift_tasks[action.id] = self.bot.loop.create_task(
                self.__delayed_lift(action)
            )
        await self.bot.webhooks.send(
            self.bot.log_channel, embed=await action.log_embed()
        )

    async def do_lift(
        self,
        action: ModAction,
        author: Member,
        lift_reason: str | None,
        *,
        __exp: bool = False,
    ) -> None:
        """Lifts the mod action and does various cleanup tasks.

        Args:
            action (ModAction): The action to lift.
            author (Member): The member lifting the action.
            lift_reason (str | None): The reason the action is being lifted.
            __exp (bool, optional): Internal flag to prevent the expiration task from cancelling itself. Defaults to False.
        """
        await action.lift(self, author, lift_reason)
        if (task := self.__lift_tasks.pop(action.id, None)) and not __exp:
            task.cancel()
        action.lifted = ModActionLift(lifter_id=author.id, reason=lift_reason)
        await action.save()
        await self.bot.webhooks.send(
            self.bot.log_channel, embed=await action.log_embed()
        )

    @commands.hybrid_command(aliases=["purge", "clean"])
    @commands.guild_only()
    @is_staff_level(StaffLevel.mod)
    @commands.bot_has_permissions(manage_messages=True)
    async def mass_delete(
        self, ctx: KolkraContext, *, flags: SelectMessageFlags
    ) -> None:
        """Delete multiple messages at once according to several criteria."""
        await ctx.defer()
        if not (matches := await flags.find_matches(ctx.channel)):
            await ctx.respond(
                embed=InfoEmbed(
                    title="No messages found",
                    description=f"There are no messages in this channel that meet {flags.require} "
                    "of the criteria specified.",
                )
            )
            return
        msg_log = generate_message_log(matches)
        if not await Confirm(ctx.author).respond(
            ctx,
            embed=WarningEmbed(
                description=f"You are about to delete {len(matches)} messages "
                "(listed in the attached log file) from this channel. "
                "Are you sure you want to continue?\n"
                "**THIS CANNOT BE UNDONE!**\n"
            ),
            file=File(msg_log, filename=f"{ctx.invocation_id}.purgelog.txt"),
        ):
            return
        await mass_delete(matches, ctx.author)
        await ctx.send(embed=OkEmbed(description=f"Deleted {len(matches)} messages."))
        msg_log.seek(0)
        await ctx.bot.webhooks.send(
            ctx.bot.log_channel,
            embed=Embed(
                title="Mass delete",
                description="(log of deleted messages attached)",
                color=Color.yellow(),
            )
            .set_thumbnail(url=icons8("delete-message"))
            .add_field(name="Initiated by", value=ctx.author.mention)
            .add_field(name="in channel", value=ctx.channel),
            file=File(msg_log, filename=f"{ctx.invocation_id}.purgelog.txt"),
        )

    @commands.hybrid_command(aliases=["yeet"])
    @commands.guild_only()
    @is_staff_level(StaffLevel.mod)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(
        self,
        ctx: KolkraContext,
        target: Member = commands.parameter(
            converter=TargetConverter("ban", check_existing=ServerBan)
        ),
        *,
        flags: ApplyFlags,
    ) -> None:
        """Ban a user from the server from within Discord."""
        if not ctx.guild:
            raise commands.NoPrivateMessage()
        if await fetch_ban(target, ctx.guild):
            await ctx.respond(
                embed=InfoEmbed(
                    title="User already banned",
                    description=f"{target} is already b&.",
                )
            )
            return
        await self.do_apply(
            ServerBan(
                guild_id=ctx.guild.id,
                issuer_id=ctx.author.id,
                target_id=target.id,
                reason=flags.reason,
                expiration=flags.expiration,
            ),
            flags.silent,
        )
        await ctx.respond(embed=OkEmbed(description=f"{target} is now b&."))
    
    @commands.hybrid_command()


    @commands.hybrid_command(aliases=["unyeet"], rest_is_raw=True)
    @commands.guild_only()
    @is_staff_level(StaffLevel.mod)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(
        self,
        ctx: KolkraContext,
        target: User,
        *,
        reason: str | None = None,
    ) -> None:
        """Revoke a user's ban. If not found in the database, will fallback to the native ban list."""
        if not (ctx.guild and isinstance(ctx.author, Member)):
            raise commands.NoPrivateMessage()
        if action := await ServerBan.fetch_existing_for(
            guild_id=ctx.guild.id, target_id=target.id
        ).first_or_none():
            await self.do_lift(action, ctx.author, reason)
        elif await fetch_ban(target, ctx.guild):
            await ctx.guild.unban(
                target,
                reason=audit_log_reason_template(
                    author_name=ctx.author.name,
                    author_id=ctx.author.id,
                    reason=reason,
                ),
            )
        else:
            await ctx.respond(
                embed=InfoEmbed(
                    title="User not banned",
                    description="I could not find a ban for that user in my database or in the server ban list.",
                )
            )
            return
        await ctx.respond(embed=OkEmbed(description=f"{target} is now unb&."))

    @commands.Cog.listener("on_member_join")
    async def enforce_softban(self, member: Member) -> None:
        if not (
            action := await Softban.fetch_existing_for(member.guild.id, member.id)
            .find(ignore_cache=True)
            .first_or_none()
        ):
            return
        dm_embed = AccessDeniedEmbed(
            title="Softban in effect",
            description="You were automatically kicked because this account has been softbanned.\n"
            "If you believe you have gotten this message in error or wish to appeal your softban, "
            "please join our ban appeal server for next steps: https://discord.gg/HgjBcmrfa6",
        )
        dm_embed.set_author(
            name=member.guild.name,
            icon_url=icon.url if (icon := member.guild.icon) else None,
        ).set_footer(text=f"{Softban.get_collection_name()} ID: {action.id}")
        if action.reason:
            dm_embed.add_field(name="The given reason is", value=action.reason)
        if action.expiration:
            dm_embed.add_field(
                name=f"This {Softban.noun()} expires",
                value=format_dt(action.expiration),
            )
        await try_dm(
            self.bot,
            member.id,
            embed=dm_embed,
        )
        try:
            await member.kick(reason="Attempted to join while softbanned")
        except Exception:
            await self.bot.webhooks.send(
                self.bot.log_channel,
                content="Manual intervention needed: softban auto-kick failed | "
                + "".join(
                    role.mention
                    for role in member.guild.roles
                    if role.permissions.kick_members and role > member.top_role
                ),
                embed=ErrorEmbed(
                    title="Auto-kick failed",
                    description=f"{member.mention} just joined while softbanned, and I tried and failed to automatically kick them. Someone needs to manually kick them ASAP.",
                ),
            )
        else:
            await self.bot.webhooks.send(
                self.bot.log_channel,
                embed=Embed(
                    title="User auto-kicked",
                    description=f"{member.mention} tried to join while softbanned!",
                    color=Color.dark_orange(),
                )
                .set_thumbnail(url=icons8("action2"))
                .set_footer(text=f"{Softban.get_collection_name()} ID: {action.id}"),
            )

    @commands.hybrid_command(aliases=["gentleyeet"])
    @commands.guild_only()
    @is_staff_level(StaffLevel.mod)
    @commands.bot_has_permissions(kick_members=True)
    async def softban(
        self,
        ctx: KolkraContext,
        target: Member = commands.parameter(
            converter=TargetConverter("softban", check_existing=Softban)
        ),
        *,
        flags: ApplyFlags,
    ) -> None:
        """ "Softban" a user by automatically kicking them whenever they try to join."""
        if not ctx.guild:
            raise commands.NoPrivateMessage()
        await self.do_apply(
            Softban(
                guild_id=ctx.guild.id,
                issuer_id=ctx.author.id,
                target_id=target.id,
                reason=flags.reason,
                expiration=flags.expiration,
            ),
            flags.silent,
        )
        await ctx.respond(
            embed=OkEmbed(
                description=f"{target} is now gone. I'll make sure they don't come back."
            )
        )

    @commands.hybrid_command(aliases=["ungentleyeet"], rest_is_raw=True)
    @commands.guild_only()
    @is_staff_level(StaffLevel.mod)
    async def unsoftban(
        self,
        ctx: KolkraContext,
        target: User,
        *,
        reason: str | None = None,
    ) -> None:
        """Revoke a user's softban."""
        if not (ctx.guild and isinstance(ctx.author, Member)):
            raise commands.NoPrivateMessage()
        if not (
            action := await Softban.fetch_existing_for(
                guild_id=ctx.guild.id, target_id=target.id
            ).first_or_none()
        ):
            await ctx.respond(
                embed=InfoEmbed(
                    title="User not softbanned",
                    description="I could not find a softban for that user in my database.",
                )
            )
            return
        await self.do_lift(action, ctx.author, reason)

        await ctx.respond(embed=OkEmbed(description=f"{target} can now join again."))

    @commands.Cog.listener("on_member_join")
    async def restore_channel_mutes(self, member: Member) -> None:
        allow, deny = MUTE_PERMS.pair()
        async for action in ChannelMute.fetch_existing_for(
            member.guild.id, member.id
        ).find(ignore_cache=True):
            await self.bot.http.edit_channel_permissions(
                action.channel_id,
                action.target_id,
                str(allow.value),
                str(deny.value),
                1,  # Individual member
                reason="Restoring channel mutes to returning member",
            )

    @commands.hybrid_command(aliases=["shaddap"])
    @commands.guild_only()
    @is_staff_level(StaffLevel.arbit)
    @commands.bot_has_permissions(manage_permissions=True)
    async def channel_mute(
        self,
        ctx: KolkraContext,
        target: Member = commands.parameter(converter=TargetConverter("mute")),
        *,
        flags: ChannelMuteApplyFlags,
    ) -> None:
        """Take away a user's ability to speak in a channel."""
        channel = flags.channel or ctx.channel
        if isinstance(channel, PartialMessageable) and not (
            channel := await ctx.bot.fetch_channel(channel.id)
        ):
            raise commands.ChannelNotFound(channel.id)
        if not ctx.guild or isinstance(channel, PrivateChannel):
            raise commands.NoPrivateMessage()
        if await ChannelMute.fetch_existing_for(
            ctx.guild.id, target.id, channel_id=channel.id
        ).first_or_none():
            await ctx.respond(
                embed=InfoEmbed(
                    description=f"{target.mention} is already muted in {channel.mention}."
                )
            )
            return
        await self.do_apply(
            ChannelMute(
                channel_id=channel.id,
                guild_id=ctx.guild.id,
                issuer_id=ctx.author.id,
                target_id=target.id,
                reason=flags.reason,
                expiration=flags.expiration,
            ),
            flags.silent,
        )
        await ctx.respond(
            embed=OkEmbed(
                description=f"{target.mention} can no longer speak in {channel.mention}."
            )
        )

    @commands.hybrid_command(aliases=["unshaddap"], rest_is_raw=True)
    @commands.guild_only()
    @is_staff_level(StaffLevel.arbit)
    @commands.bot_has_permissions(manage_permissions=True)
    async def channel_unmute(
        self,
        ctx: KolkraContext,
        target: Member,
        *,
        flags: ChannelMuteLiftFlags,
    ) -> None:
        """Allow a user to speak again in a channel."""
        channel = flags.channel or ctx.channel
        if isinstance(channel, PartialMessageable) and not (
            channel := await ctx.bot.fetch_channel(channel.id)
        ):
            raise commands.ChannelNotFound(channel.id)
        if isinstance(channel, PrivateChannel) or not (
            ctx.guild and isinstance(ctx.author, Member)
        ):
            raise commands.NoPrivateMessage()
        if not (
            action := await ChannelMute.fetch_existing_for(
                guild_id=ctx.guild.id,
                target_id=target.id,
                channel_id=channel.id,
            ).first_or_none()
        ):
            all_existing_mutes = await ChannelMute.fetch_existing_for(
                ctx.guild.id, target.id
            ).to_list()
            await ctx.respond(
                embed=InfoEmbed(
                    title="User not muted in channel",
                    description=f"{target.mention} is not muted in {channel.mention}. "
                    f"They are muted in: {', '.join(f'<#{r.channel_id}>' for r in all_existing_mutes)}.",
                ),
            )
            return
        await self.do_lift(action, ctx.author, flags.reason)
        await ctx.respond(
            embed=OkEmbed(
                description=f"{target.mention} can now speak again in {channel.mention}."
            )
        )

    @commands.hybrid_command()
    @commands.guild_only()
    @is_staff_level(StaffLevel.arbit)
    @commands.bot_has_permissions(kick_members=True, ban_members=True)
    async def warn(
        self,
        ctx: KolkraContext,
        target: Member = commands.parameter(converter=TargetConverter("warn")),
        *,
        flags: ApplyFlags,
    ) -> None:
        """Issue a formal warning to a user.
        Users that accumulate 5 active warnings are automatically banned from the server.
        """
        if not ctx.guild:
            raise commands.NoPrivateMessage()
        action = ModWarning(
            guild_id=ctx.guild.id,
            issuer_id=ctx.author.id,
            target_id=target.id,
            reason=flags.reason,
            expiration=flags.expiration,
        )
        await self.do_apply(action, flags.silent)
        count = await action.cached_count()
        await ctx.respond(
            embed=OkEmbed(
                description=f"{target} warned. User has {count} warning{'s' if count != 1 else ''}."
            ).add_field(name="Warning ID", value=action.id)
        )

    @commands.hybrid_command(aliases=["warns"])
    @commands.guild_only()
    async def list_warnings(
        self, ctx: KolkraContext, user: Member = commands.Author
    ) -> None:
        """List active warnings for yourself or another user.
        Anyone can list their own warnings, Arbits+ can list warnings of other users.
        """
        if not (ctx.guild and isinstance(ctx.author, Member)):
            raise commands.NoPrivateMessage()
        if (
            user != ctx.author
            and (ctx.bot.get_staff_level_for(ctx.author) or 0) < StaffLevel.arbit
        ):
            await ctx.respond(
                embed=AccessDeniedEmbed(
                    description="You must be at least Arbit to list other users' warnings."
                )
            )
            return
        if not (
            warns := await ModWarning.fetch_existing_for(
                ctx.guild.id, user.id
            ).to_list()
        ):

            await ctx.respond(
                embed=InfoEmbed(
                    title="No warnings found",
                    description=(
                        "You have no active warnings. Good for you! <:musiyay:876680470597873664>"
                        if ctx.author == user
                        else f"{user.mention} has no active warnings."
                    ),
                ),
                ephemeral=True,
            )
            return
        await Pager(
            group_embeds(
                [
                    Embed(timestamp=warn.timestamp)
                    .add_field(name="Warning ID", value=warn.id)
                    .add_field(name="Reason", value=warn.reason)
                    .add_field(name="Issuer", value=f"<@{warn.issuer_id}>")
                    .add_field(
                        name="Expiration",
                        value=(format_dt(warn.expiration) if warn.expiration else None),
                    )
                    for warn in warns
                ]
            ),
            ctx.author,
        ).respond(ctx, ephemeral=True)

    @commands.hybrid_command(aliases=["rmwarn"], rest_is_raw=True)
    @commands.guild_only()
    @is_staff_level(StaffLevel.arbit)
    async def remove_warning(
        self, ctx: KolkraContext, warning_id: str, *, reason: str | None = None
    ) -> None:
        """Remove a warning based on its ID.
        If a user was banned for accumulating 5 warnings, this will not automatically unban them.
        """
        if not (ctx.guild and isinstance(ctx.author, Member)):
            raise commands.NoPrivateMessage()
        if (
            not (action := await ModWarning.get(warning_id))
        ) or action.guild_id != ctx.guild.id:
            await ctx.respond(
                embed=InfoEmbed(
                    title="No such warning",
                    description="I couldn't find a warning with that ID.",
                )
            )
            return
        elif action.lifted is not None:
            await ctx.respond(
                embed=InfoEmbed(
                    title="Already removed",
                    description="That warning has already been lifted.",
                )
            )
            return
        await self.do_lift(action, ctx.author, reason)
        count = await action.cached_count(refresh=True)
        await ctx.respond(
            embed=OkEmbed(
                description=f"Removed warning {warning_id} from <@{action.target_id}>. "
                f"User now has {count} warning{'s' if count != 1 else ''}."
            )
        )

    @commands.hybrid_command(aliases=["userlog"])
    @commands.guild_only()
    @is_staff_level(StaffLevel.mod)
    async def list_mod_actions(self, ctx: KolkraContext, user: Member | User) -> None:
        """List all mod actions issued against a user. Aaall of them, even expired/lifted ones.
        When a mod action issued through Kolkra expires or is manually removed, it is still retained in the database for accountability reasons. If you want to have an expired/lifted mod action removed from your record, please contact @m1n3r_spl.
        """
        if not ctx.guild:
            raise commands.NoPrivateMessage()
        await ctx.defer()
        embeds = []
        for cls in MOD_ACTION_MODELS:
            async for action in cls.fetch_existing_for(
                ctx.guild.id, user.id, include_lifted=True
            ):
                embeds.append(await action.log_embed())
        if embeds:
            await Pager(group_embeds(embeds)).respond(ctx, ephemeral=True)
            return
        await ctx.respond(
            embed=InfoEmbed(
                title="No entries found",
                description=f"{user.mention}'s rap sheet is just a blank piece of paper. Right back in the printer it goes, then...",
            ).set_footer(text="Note: This only applies to info in my own database."),
            ephemeral=True,
        )

    @commands.Cog.listener("on_message")
    async def autoban_ban_evaders(self, message: Message) -> None:
        if not (
            message.guild
            and self.bot.user
            and message.author.id == DOUBLE_COUNTER_ID
            and (match := re.search(DC_ALT_PATTERN, message.content))
        ):
            return
        alt_id, main_id = match.groups()
        try:
            if not (ban := await fetch_ban(Object(main_id), message.guild)):
                return
        except Forbidden:
            return  # We don't have permission to ban them anyway
        await self.do_apply(
            ServerBan(
                guild_id=message.guild.id,
                issuer_id=self.bot.user.id,
                target_id=int(alt_id),
                reason=f"Ban evasion - flagged as alt of banned user {ban.user.name!r} (ID: {main_id})",
                expiration=None,
            ),
            False,
        )


DOUBLE_COUNTER_ID = 703886990948565003
DC_ALT_PATTERN = re.compile(
    r":small_red_triangle: Alt-account intrusion attempt blocked : [\w\d._]* \((\d*)\) - Main account : <@\d*> \((\d*)\)"
)


async def setup(bot: Kolkra) -> None:
    await bot.add_cog(ModCog(bot))
