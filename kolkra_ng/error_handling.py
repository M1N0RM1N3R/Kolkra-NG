import logging

from discord import Embed
from discord.ext import commands

from kolkra_ng.bot import KolkraContext
from kolkra_ng.embeds import icon_urls

log = logging.getLogger(__name__)


async def unknown_command_error(context: KolkraContext, exception: commands.CommandError):
    log.error(
        "Command `%s` raised exception (Invocation ID: %s)",
        context.command.qualified_name if context.command else None,
        context.invocation_id,
        exc_info=(type(exception), exception, exception.__traceback__),
    )
    await context.respond(
        embed=Embed(
            title="pakala a!",
            description="An unexpected error occurred while running this command.",
        )
        .set_thumbnail(url=icon_urls["error"])
        .add_field(name="What happened", value=str(exception.__cause__))
        .add_field(
            name="Invocation ID (include this when reporting the error)",
            value=context.invocation_id,
        )
    )


async def handle_command_error(context: KolkraContext, exception: commands.CommandError):
    if isinstance(exception, ()):
        pass
    else:
        await unknown_command_error(context, exception)
