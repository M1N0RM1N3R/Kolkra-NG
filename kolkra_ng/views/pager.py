from discord import Embed, Interaction, Member, Message, SelectOption, User
from discord.abc import Messageable
from discord.ui import Button, Select, View, button, select

from kolkra_ng.context import KolkraContext
from kolkra_ng.embeds import AccessDeniedEmbed


def group_embeds(embeds: list[Embed]) -> list[list[Embed]]:
    """Splits a list of embeds into groups of a total size of up to 10 embeds or 6,000 characters' worth of content.
    Useful companion to the Pager.

    Args:
        embeds (list[Embed]): The embeds to group.

    Returns:
        list[list[Embed]]: The embeds split into API limit-compliant groups/pages.
    """
    groups: list[list[Embed]] = []
    current_group: list[Embed] = []
    for embed in embeds:
        if (
            len(current_group) == 10
            or len(embed) + sum(len(e) for e in current_group) > 6000
        ):
            groups.append(current_group)
            current_group = []
        current_group.append(embed)
    groups.append(current_group)
    return groups


class Pager(View):
    """A user-friendly paginator for groups of embeds."""

    current_page: int = 0
    message: Message

    def __init__(
        self,
        pages: list[list[Embed]],
        author: User | Member | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.pages = pages
        self.author = author
        self.jump.options = [
            SelectOption(label=f"Page {i + 1}", value=str(i))
            for i in range(len(self.pages))
        ]

    async def send(self, destination: Messageable, *args, **kwargs) -> None:
        await self.update(None)
        self.message = await destination.send(
            *args, embeds=self.pages[self.current_page], view=self, **kwargs
        )

    async def respond(self, ctx: KolkraContext, *args, **kwargs) -> None:
        await self.update(None)
        self.message = await ctx.respond(
            *args, embeds=self.pages[self.current_page], view=self, **kwargs
        )

    async def on_timeout(self) -> None:
        for component in self.children:
            component.disabled = True  # pyright: ignore [reportAttributeAccessIssue]
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        if self.author and interaction.user != self.author:
            await interaction.response.send_message(
                embed=AccessDeniedEmbed(description="This is not for you!")
            )
            return False
        return True

    async def update(self, interaction: Interaction | None) -> None:
        self.page_number.label = f"{self.current_page + 1}/{len(self.pages)}"
        self.first.disabled = self.previous.disabled = self.current_page == 0
        self.next.disabled = self.last.disabled = (
            self.current_page == len(self.pages) - 1
        )
        if interaction:
            await interaction.response.edit_message(
                embeds=self.pages[self.current_page], view=self
            )

    @select(placeholder="Jump to page...")
    async def jump(self, interaction: Interaction, select: Select) -> None:
        self.current_page = int(select.values[0])
        await self.update(interaction)

    @button(emoji="⏮")
    async def first(self, interaction: Interaction, button: Button) -> None:
        self.current_page = 0
        await self.update(interaction)

    @button(emoji="◀")
    async def previous(self, interaction: Interaction, button: Button) -> None:
        self.current_page = max(0, self.current_page - 1)
        await self.update(interaction)

    @button(disabled=True)
    async def page_number(self, interaction: Interaction, button: Button) -> None:
        pass

    @button(emoji="▶️")
    async def next(self, interaction: Interaction, button: Button) -> None:
        self.current_page = min(self.current_page + 1, len(self.pages) - 1)
        await self.update(interaction)

    @button(emoji="⏭")
    async def last(self, interaction: Interaction, button: Button) -> None:
        self.current_page = len(self.pages) - 1
        await self.update(interaction)
