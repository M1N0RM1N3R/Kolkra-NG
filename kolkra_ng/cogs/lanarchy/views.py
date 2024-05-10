from datetime import datetime, timedelta

from discord import ButtonStyle, Interaction, Member
from discord.ui import Button, View, button
from discord.utils import utcnow


class MatchmakingGroup(View):
    players: set[Member]
    expiration: datetime
    last_ping: datetime
    _history: set[Member]

    def __init__(self):
        super().__init__(timeout=None)
        self.players = set()
        self.expiration = utcnow() + timedelta(minutes=10)

    @button(label="Join", emoji="➡", style=ButtonStyle.primary)
    async def join_group(self, interaction: Interaction, button: Button) -> None:
        pass

    @button(label="Leave", emoji="⬅", style=ButtonStyle.red)
    async def leave_group(self, interaction: Interaction, button: Button) -> None:
        pass

    @button(label="Reping", emoji="📳", style=ButtonStyle.secondary)
    async def reping(self, interaction: Interaction, button: Button) -> None:
        pass
