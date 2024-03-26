import logging

from discord import Intents, Interaction, Message, Object, WebhookMessage
from discord.ext import commands
from odmantic import AIOEngine

from kolkra_ng.config import Config

log = logging.getLogger(__name__)


class KolkraContext(commands.Context["Kolkra"]):
    async def respond(self, *args, **kwargs) -> WebhookMessage | Message | None:
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
                return await self.interaction.response.send_message(*args, **kwargs)
        elif self.message is not None:
            return await self.message.reply(*args, **kwargs)


class Kolkra(commands.Bot):
    def __init__(self, config: Config) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or("k;"),
            intents=Intents.default() | Intents(members=True, message_content=True),
        )
        self.config = config
        self.engine = AIOEngine(self.config.mongodb_url)

    async def setup_hook(self) -> None:
        """Syncs application commands on startup."""
        await super().setup_hook()
        self.tree.copy_global_to(guild=Object(self.config.guild_id))
        await self.tree.sync(guild=Object(self.config.guild_id))

    async def get_context(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, origin: Message | Interaction, /, *, cls=KolkraContext
    ):
        return await super().get_context(origin, cls=cls)

    async def on_ready(self) -> None:
        """Creates a log when the bot is ready. That's it."""
        log.info("Ready!")
