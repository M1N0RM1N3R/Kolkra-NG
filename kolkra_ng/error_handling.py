from __future__ import annotations

import logging
from datetime import datetime, timedelta

from discord import Color, Embed
from discord.ext import commands
from discord.utils import format_dt

from kolkra_ng.bot import KolkraContext
from kolkra_ng.embeds import AccessDeniedEmbed, ErrorEmbed, WaitEmbed, icons8

log = logging.getLogger(__name__)


async def unknown_command_error(context: KolkraContext, exception: commands.CommandError):
    log.exception(
        "Command `%s` raised exception (Invocation ID: %s)",
        context.command.qualified_name if context.command else None,
        context.invocation_id,
        exc_info=(type(exception), exception, exception.__traceback__),
    )
    await context.respond(
        embed=ErrorEmbed(
            title="pakala a!",
            description="An unexpected error occurred while running this command.",
        )
        .add_field(name="What happened", value=exception)
        .add_field(
            name="Invocation ID (include this when reporting the error)",
            value=context.invocation_id,
        )
    )


async def handle_check_failure(context: KolkraContext, exception: commands.CommandError):
    if isinstance(exception, commands.NotOwner):
        await context.respond(
            embed=AccessDeniedEmbed(
                title="Dev-only command",
                description="This command is restricted to bot devs only.",
            )
        )
        return
    elif isinstance(exception, commands.CommandOnCooldown):
        await context.respond(
            embed=WaitEmbed(description="This command is on cooldown.").add_field(
                name="Cooldown ends",
                value=format_dt(
                    datetime.now() + timedelta(seconds=exception.retry_after),
                    "R",
                ),
            )
        )
        return
    elif isinstance(exception, commands.NSFWChannelRequired):
        await context.respond(
            embed=Embed(
                title="NSFW command",
                description="This command is only available in age-restricted (NSFW) channels.",
                color=Color.red(),
            ).set_thumbnail(url=icons8("18-plus"))
        )
        return
    elif isinstance(exception, commands.CheckAnyFailure):
        errors = "\n".join(f"- {error}" for error in exception.errors)
        await context.respond(
            embed=AccessDeniedEmbed(
                title="All checks failed",
                description="You do not meet any of the conditions required to run this command.",
            ).add_field(name="Failed checks", value=errors)
        )
        return
    else:
        await context.respond(embed=AccessDeniedEmbed(title="Check failed", description=str(exception)))


async def handle_command_error(context: KolkraContext, exception: commands.CommandError):
    if isinstance(exception, commands.CheckFailure):
        await handle_check_failure(context, exception)
    else:
        await unknown_command_error(context, exception)
