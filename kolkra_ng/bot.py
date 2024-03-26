import logging
from types import TracebackType
from typing import Any, Tuple, Type, TypeVar

from discord import (
    Intents,
    Interaction,
    Message,
    Object,
    WebhookMessage,
)
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine

from kolkra_ng.config import Config
from kolkra_ng.error_handling import handle_command_error

log = logging.getLogger(__name__)


class KolkraContext(commands.Context["Kolkra"]):
    @property
    def invocation_id(self) -> str:
        return f"I{self.interaction.id}" if self.interaction else f"P{self.message.id}"

    async def respond(self, *args: Any, **kwargs: Any) -> WebhookMessage | Message | None:
        """Sends a response to a command invocation; as a reply to a prefix
        invocation, a message response to an interaction, or a follow-up
        message to a responded interaction.

        Returns:
            WebhookMessage | Message | None: The datatype returned from the
                response; a WebhookMessage for an interaction followup, a
                Message for a prefix invocation, or None for an interaction
                response--use `await KolkraContext.original_response()` in this
                case.
        """
        if self.interaction is not None:
            if self.interaction.response.is_done():
                return await self.interaction.followup.send(*args, **kwargs)
            else:
                await self.interaction.response.send_message(*args, **kwargs)
        return await self.message.reply(*args, **kwargs)


CogT = TypeVar("CogT", bound=commands.Cog)
ExceptionT = TypeVar("ExceptionT", bound=Exception)


def exc_info(
    e: ExceptionT,
) -> Tuple[Type[ExceptionT], ExceptionT, TracebackType | None]:
    """Returns a facsimile of `sys.exc_info()` for an exception.

    Args:
        e (ExceptionT): The exception to convert.

    Returns:
        Tuple[Type[ExceptionT], ExceptionT, TracebackType | None]: The created exc_info tuple.
    """
    return type(e), e, e.__traceback__


ContextT = TypeVar("ContextT", bound=commands.Context[Any])


class Kolkra(commands.Bot):
    def __init__(self, config: Config) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or("k;"),
            intents=Intents.default() | Intents(members=True, message_content=True),
        )
        self.config = config
        self.engine = AIOEngine(AsyncIOMotorClient(self.config.mongodb_url.unicode_string()))

    async def setup_hook(self) -> None:
        """Syncs application commands on startup."""
        await super().setup_hook()
        self.tree.copy_global_to(guild=Object(self.config.guild_id))
        await self.tree.sync(guild=Object(self.config.guild_id))

    async def get_context(
        self,
        origin: Message | Interaction,
        /,
        *,
        cls: Type[ContextT] = KolkraContext,
    ) -> ContextT:
        return await super().get_context(origin, cls=cls)

    async def on_ready(self) -> None:
        """Creates a log when the bot is ready. That's it."""
        log.info("Ready!")

    def typed_get_cog(self, cls: Type[CogT]) -> CogT | None:
        cog = self.get_cog(cls.__name__)
        if not isinstance(cog, cls | None):
            raise TypeError()
        return cog

    async def on_command(self, context: KolkraContext) -> None:
        log.info(
            "Command `%s` invoked by `%s` with args `%s` (Invocation ID: %s)",
            context.command.qualified_name if context.command else None,
            context.author,
            context.args,
            context.invocation_id,
        )

    async def on_command_error(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, context: KolkraContext, exception: commands.CommandError, /
    ) -> None:
        await handle_command_error(context, exception)
