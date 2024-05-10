from discord import ButtonStyle, Interaction, Member, Message, User
from discord.abc import Messageable
from discord.ui import Button, View, button

from kolkra_ng.context import KolkraContext
from kolkra_ng.embeds import AccessDeniedEmbed


class Confirm(View):
    message: Message
    value: bool | None = None

    def __init__(
        self,
        author: User | Member | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.author = author

    async def disable(self) -> None:
        self.stop()
        for component in self.children:
            component.disabled = True  # pyright: ignore [reportAttributeAccessIssue]
        await self.message.edit(view=self)

    async def send(self, destination: Messageable, *args, **kwargs) -> bool | None:
        self.message = await destination.send(*args, view=self, **kwargs)
        await self.wait()
        return self.value

    async def respond(self, ctx: KolkraContext, *args, **kwargs) -> bool | None:
        self.message = await ctx.respond(*args, view=self, **kwargs)
        await self.wait()
        return self.value

    async def on_timeout(self) -> None:
        await self.disable()

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        if self.author and interaction.user != self.author:
            await interaction.response.send_message(
                embed=AccessDeniedEmbed(description="This is not for you!")
            )
            return False
        await interaction.response.defer()
        return True

    @button(label="Yes", emoji="✔️", style=ButtonStyle.green)
    async def confirm(self, interaction: Interaction, button: Button) -> None:
        self.value = True
        await self.disable()

    @button(label="No", emoji="❌")
    async def decline(self, interaction: Interaction, button: Button) -> None:
        self.value = False
        await self.disable()
