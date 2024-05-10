import logging
from pathlib import Path
from typing import TypeVar

from beanie import Document, init_beanie
from discord import Intents, Interaction, Member, Message
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient

from kolkra_ng.config import Config
from kolkra_ng.context import KolkraContext
from kolkra_ng.enums.staff_level import StaffLevel
from kolkra_ng.help import KolkraHelp
from kolkra_ng.webhooks import SupportsWebhooks, WebhookManager

log = logging.getLogger(__name__)


CogT = TypeVar("CogT", bound=commands.Cog)
ContextT = TypeVar("ContextT", bound=commands.Context)


class Kolkra(commands.Bot):
    def __init__(self, config: Config) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or(";"),
            intents=Intents.default() | Intents(members=True, message_content=True),
        )
        self.config = config
        self.motor = AsyncIOMotorClient(
            self.config.mongodb_url.get_secret_value().unicode_string()
        )
        self.help_command = KolkraHelp()
        self.webhooks = WebhookManager(self)

    async def init_db_models(self, *models: type[Document]) -> None:
        log.info(
            "Setting up database models: %s", ", ".join(m.__qualname__ for m in models)
        )
        await init_beanie(
            database=self.motor.get_database(
                (self.config.mongodb_url.get_secret_value().path or "kolkra_ng").strip(
                    "/"
                )
            ),
            document_models=list(models),
        )

    async def update_attrs(self) -> None:
        self.guild = self.get_guild(self.config.guild) or await self.fetch_guild(
            self.config.guild
        )
        log.info("Configured guild (server): %s", self.guild)
        self.log_channel: SupportsWebhooks = (
            self.get_channel(  # pyright: ignore [reportAttributeAccessIssue]
                self.config.log_channel
            )
            or await self.fetch_channel(self.config.log_channel)
        )
        if not isinstance(self.log_channel, SupportsWebhooks):
            log.warning("Configured log channel %s does not support webhooks!")
        else:
            log.info("Configured log channel: %s", self.log_channel)

    async def load_modules(self) -> None:
        log.info("Loading modules")
        pkg_root = Path(__file__).parent
        for path in pkg_root.joinpath("cogs").iterdir():
            if path.name.startswith("__"):
                continue
            module = (
                path.relative_to(pkg_root)
                .as_posix()
                .removesuffix(".py")
                .replace("/", ".")
            )
            try:
                await self.load_extension(module)
            except Exception as e:
                log.warning("Failed to load module %s", module, exc_info=e)
            else:
                log.info("Loaded module %s", module)
        await self.load_extension("jishaku")
        log.info("Loaded Jishaku (debug module)")

    async def register_commands(self) -> None:
        log.info("Registering application (slash) commands")
        self.tree.copy_global_to(guild=self.guild)
        await self.tree.sync(guild=self.guild)

    async def setup_hook(self) -> None:
        """Does setup stuff."""
        log.info("Performing initial setup")
        await super().setup_hook()
        await self.update_attrs()
        await self.load_modules()
        # raise
        await self.register_commands()
        log.info("Initial setup complete")

    async def get_context(
        self,
        origin: Message | Interaction,
        /,
        *,
        cls: type[ContextT] = KolkraContext,
    ) -> ContextT:
        return await super().get_context(origin, cls=cls)

    async def on_ready(self) -> None:
        log.info("Ready!")

    def typed_get_cog(self, cls: type[CogT]) -> CogT | None:
        cog = self.get_cog(cls.__cog_name__)
        if not isinstance(cog, cls | None):
            raise TypeError()
        return cog

    async def on_command(self, context: KolkraContext) -> None:
        log.info(
            "Command `%s` invoked by `%s` with args `%s` (Invocation ID: %s)",
            context.command.qualified_name if context.command else None,
            context.author,
            (context.args, context.kwargs),
            context.invocation_id,
        )

    async def on_command_error(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, context: KolkraContext, exception: commands.CommandError, /
    ) -> None:
        from kolkra_ng.error_handling import handle_command_error

        await handle_command_error(context, exception)

    def get_staff_level_for(self, user: Member) -> StaffLevel | None:
        """Get a user's staff level based on the configured staff roles.

        Args:
            user (Member): The user to find the staff level for.

        Returns:
            StaffLevel: The user's staff level.
        """
        if not (
            levels := [
                level
                for level, roles in self.config.staff_roles.items()
                if user.get_role(roles.permission_role)
            ]
        ):
            return None

        return max(levels)

    async def close(self) -> None:
        log.info("Closing database connection")
        self.motor.close()
        log.info("Shutting down")
        await super().close()
