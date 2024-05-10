from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord import Message
from discord.ext import commands

if TYPE_CHECKING:
    from kolkra_ng.bot import Kolkra

DEFER_REACTION = "⏳"


class KolkraContext(commands.Context[Kolkra]):
    __prefix_deferred = False

    @property
    def invocation_id(self) -> str:
        return f"I{self.interaction.id}" if self.interaction else f"P{self.message.id}"

    async def respond(
        self, *args: Any, ephemeral: bool = False, **kwargs: Any
    ) -> Message:
        """Sends a response to a command invocation; as a reply to a prefix
        invocation, a message response to an interaction, or a follow-up
        message to a responded interaction.

        Returns:
            Message: The sent response.
        """
        if self.interaction is not None:
            if self.interaction.response.is_done():
                return await self.interaction.followup.send(
                    *args, ephemeral=ephemeral, **kwargs
                )
            else:
                await self.interaction.response.send_message(
                    *args, ephemeral=ephemeral, **kwargs
                )
                return await self.interaction.original_response()
        if self.__prefix_deferred:
            await self.message.remove_reaction(DEFER_REACTION, self.me)
            self.__prefix_deferred = False
        return await self.message.reply(*args, **kwargs)

    async def defer(self, **kwargs: Any) -> None:
        """Acknowledges a command invocation that may take more than 3 seconds to return a meaningful response.
        Sends a defer response in the case of an interaction, or reacts to the invocation message in the case of a prefix invocation.
        For prefix invocations, also sets an internal flag to remove the reaction when `KolkraContext.respond()` is called.
        """
        if self.interaction is not None and not self.interaction.response.is_done():
            await super().defer(**kwargs)
            return
        self.__prefix_deferred = True
        await self.message.add_reaction(DEFER_REACTION)
