from __future__ import annotations

import logging
import random
import sys
import traceback
from datetime import datetime, timedelta
from types import TracebackType
from typing import TypeVar

from discord import Color, Embed
from discord.ext import commands
from discord.utils import format_dt

from kolkra_ng.checks import InsufficientStaffLevel
from kolkra_ng.context import KolkraContext
from kolkra_ng.embeds import (
    AccessDeniedEmbed,
    ErrorEmbed,
    QuestionEmbed,
    SplitEmbed,
    WaitEmbed,
    WarningEmbed,
    icons8,
)

log = logging.getLogger(__name__)

ExceptionT = TypeVar("ExceptionT", bound=BaseException)


def root_cause(e: BaseException) -> BaseException:
    if e.__cause__:
        return root_cause(e.__cause__)
    return e


def exc_info(
    e: ExceptionT,
) -> tuple[type[ExceptionT], ExceptionT, TracebackType | None]:
    """Returns a facsimile of `sys.exc_info()` for an exception.

    Args:
        e (ExceptionT): The exception to convert.

    Returns:
        Tuple[Type[ExceptionT], ExceptionT, TracebackType | None]: The created exc_info tuple.
    """
    return type(e), e, e.__traceback__


def format_traceback(max_length: int = 4096, exc: BaseException | None = None) -> str:
    p = commands.Paginator(max_size=max_length)
    for line in traceback.format_exception(*(exc_info(exc) if exc else sys.exc_info())):
        p.add_line(line)
    return p.pages[-1]


async def unknown_command_error(
    context: KolkraContext, exception: commands.CommandError
) -> None:
    log.exception(
        "Command `%s` raised exception (Invocation ID: %s)",
        context.command.qualified_name if context.command else None,
        context.invocation_id,
        exc_info=exc_info(exception),
    )
    title = random.choice(
        [
            "pakala a!",
            "Well, this is embarrassing...",
            "It's not you, it's me.",
            "Abort, Retry, Fail?",
            "lp0 on fire",
            "Guru Meditation. Ommmmmmmm...",
            "Task failed successfully",
            "💣",
            "THAT wasn't supposed to happen!",
            "Whoops!",
            "This is fine.",
        ]
    )
    await context.respond(
        embed=ErrorEmbed(
            title=title,
            description="An unexpected error occurred while running this command.",
        )
        .add_field(name="What happened", value=exception)
        .add_field(
            name="Invocation ID (include this when reporting the error)",
            value=context.invocation_id,
        )
    )
    await context.bot.webhooks.send(
        context.bot.log_channel,
        embeds=SplitEmbed.from_single(
            ErrorEmbed(
                title="Unexpected command error",
                description=format_traceback(exc=exception),
            )
        )
        .add_field(
            name="Command",
            value=(context.command.qualified_name if context.command else "Unknown"),
        )
        .add_field(name="Invocation ID", value=context.invocation_id)
        .embeds(),
    )


async def handle_check_failure(
    context: KolkraContext, exception: commands.CommandError
) -> None:
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
                description="You do not meet any of the conditions required to use this command.",
            ).add_field(name="Failed checks", value=errors)
        )
        return
    elif isinstance(exception, InsufficientStaffLevel):
        await context.respond(
            embed=AccessDeniedEmbed(
                title="Insufficient staff level",
                description=f"You must be at least {exception.required_level.name} to use this command.",
            ).add_field(
                name="Your staff level",
                value=(level.name if (level := exception.author_level) else "none"),
            )
        )
    else:
        await context.respond(
            embed=AccessDeniedEmbed(title="Check failed", description=str(exception))
        )


async def handle_command_error(
    context: KolkraContext, exception: commands.CommandError
) -> None:
    if isinstance(exception, commands.CheckFailure):
        await handle_check_failure(context, exception)
    elif isinstance(exception, commands.DisabledCommand):
        await context.respond(
            embed=AccessDeniedEmbed(
                title="Command disabled",
                description="This command is currently disabled. Sorry for the inconvenience.",
            )
        )
        return
    elif isinstance(exception, commands.CommandNotFound):
        await context.respond(
            embed=QuestionEmbed(
                title="Unknown command",
                description=f"Type `{context.clean_prefix}help` for a list of available commands.",
            )
        )
    elif isinstance(exception, commands.UserInputError):
        await context.respond(
            embed=WarningEmbed(
                title="Invalid input",
                description=f"Type `{context.clean_prefix}help {context.command}` for usage information.",
            ).add_field(name="Error message", value=exception)
        )
    else:
        await unknown_command_error(context, exception)
