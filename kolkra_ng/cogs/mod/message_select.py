import re
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import cached_property
from io import BytesIO
from typing import TYPE_CHECKING, Literal

from discord import Member, Message, User
from discord.abc import GuildChannel
from discord.ext import commands
from discord.utils import utcnow

from kolkra_ng.converters import DatetimeConverter, Flags
from kolkra_ng.utils import audit_log_reason_template

if TYPE_CHECKING:
    from discord.abc import MessageableChannel


def get_user_type(
    m: Message,
) -> Literal["human", "bot", "webhook", "system"]:
    if m.author.bot:
        return "bot"
    elif m.webhook_id:
        return "webhook"
    elif m.is_system():
        return "system"
    else:
        return "human"


class SelectMessageFlags(Flags):
    # Search constraints
    limit: commands.Range[int, 1] | None = commands.flag(
        aliases=["max"],
        description="The maximum number of messages to select.",
        default=None,
        positional=True,
    )
    search_limit: commands.Range[int, 1] | None = commands.flag(
        aliases=["search"],
        description="The maximum number of messages to search.",
        default=None,
    )
    before: datetime | None = commands.flag(
        converter=DatetimeConverter("past"),
        description="Search messages from before this date/time.",
        default=None,
    )
    after: datetime | None = commands.flag(
        converter=DatetimeConverter("past"),
        description="Search messages from after this date/time.",
        default=None,
    )
    around: datetime | None = commands.flag(
        converter=DatetimeConverter("past"),
        description="Search messages from around this date/time.",
        default=None,
    )

    # Match predicates
    regex: re.Pattern[str] | None = commands.flag(
        aliases=["matches", "pattern"],
        converter=re.compile,
        description="Select messages that match this regular expression.",
        default=None,
    )
    author: Member | None = commands.flag(
        aliases=["user", "from", "by"],
        description="Select messages by this user.",
        default=None,
    )
    mentions: Member | None = commands.flag(
        aliases=["pings"],
        description="Select messages that mention this user.",
        default=None,
    )
    user_type: Literal["human", "bot", "webhook", "system"] | None = commands.flag(
        description="Select messages from this type of user.", default=None
    )
    references_message: Message | None = commands.flag(
        aliases=["ref", "reply"],
        description="Select messages that reference this message.",
        default=None,
        converter=commands.MessageConverter,
    )
    embeds: bool | None = commands.flag(
        description="Select messages with embeds.", default=None
    )
    attachments: bool | None = commands.flag(
        aliases=["files"],
        description="Select messages with attachments.",
        default=None,
    )
    reactions: bool | None = commands.flag(
        description="Select messages with reactions.", default=None
    )
    emotes: bool | None = commands.flag(
        description="Select messages with emotes.", default=None
    )
    stickers: bool | None = commands.flag(
        description="Select messages with stickers.", default=None
    )
    pinned: bool | None = commands.flag(
        description="Select pinned messages.", default=None
    )

    require: Literal["all", "any"] = commands.flag(
        description="Whether all/any of the selected criteria should be met for a message to be selected.",
        default="all",
    )

    @cached_property
    def check(self) -> Callable[[Message], bool]:  # noqa: C901
        predicates: list[Callable[[Message], bool]] = []

        # Match predicates
        if regex := self.regex:
            predicates.append(lambda m: bool(regex.match(m.content)))
        if author := self.author:
            predicates.append(lambda m: m.author == author)
        if mentions := self.mentions:
            predicates.append(lambda m: mentions in m.mentions)
        if user_type := self.user_type:
            predicates.append(lambda m: get_user_type(m) in user_type)
        if references_message := self.references_message:
            predicates.append(
                lambda m: (
                    (ref.message_id == references_message.id)
                    if (ref := m.reference)
                    else False
                )
            )
        if embeds := self.embeds:
            predicates.append(lambda m: embeds == bool(m.embeds))
        if attachments := self.attachments:
            predicates.append(lambda m: attachments == bool(m.attachments))
        if reactions := self.reactions:
            predicates.append(lambda m: reactions == bool(m.reactions))
        if emotes := self.emotes:
            emote_regex = re.compile(
                r"<a?:(\w+):(\d+)>"
            )  # Thanks Danny! ;) (https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/mod.py#L3515)
            predicates.append(lambda m: emotes == bool(emote_regex.search(m.content)))
        if stickers := self.stickers:
            predicates.append(lambda m: stickers == bool(m.stickers))
        if pinned := self.pinned:
            predicates.append(lambda m: pinned == m.pinned)

        def inner(message: Message) -> bool:
            return (any if self.require == "any" else all)(
                p(message) for p in predicates
            )

        return inner

    async def find_matches(self, channel: "MessageableChannel") -> list[Message]:
        matches: list[Message] = []

        async for message in channel.history(
            limit=self.search_limit,
            before=self.before,
            after=self.after,
            around=self.around,
        ):
            if self.limit and len(matches) >= self.limit:
                break
            if self.check(message):
                matches.append(message)

        return matches


NEWLINE = "\n"
ESCAPED_NEWLINE = r"\n"


def stringify_message(message: Message) -> str:
    return f"[{message.author}@{message.created_at.isoformat()}] {message.content.replace(NEWLINE, ESCAPED_NEWLINE)}"


def generate_message_log(messages: list[Message]) -> BytesIO:
    """Generate a log of messages in the form of a BytesIO object"""

    return BytesIO(
        "\n".join(
            f"{stringify_message(message)}"
            for message in sorted(messages, key=lambda m: m.created_at)
        ).encode()
    )


MAX_BULK_DELETE_AGE = timedelta(days=14)
MAX_MESSAGES_PER_BULK_DELETE = 100


async def mass_delete(messages: list[Message], author: Member | User) -> None:
    bulk_deleteable: list[Message] = []
    too_old: list[Message] = []
    for message in messages:
        (
            too_old
            if utcnow() - message.created_at > MAX_BULK_DELETE_AGE
            else bulk_deleteable
        ).append(message)

    # Sort out the messages that we *can* bulk-delete by channel
    messages_to_channels: dict[MessageableChannel, list[Message]] = {}
    for message in bulk_deleteable:
        if not (v := messages_to_channels.get(message.channel)):
            v = messages_to_channels[message.channel] = []
        v.append(message)

    # Delete the messages in each channel
    for channel, to_delete in messages_to_channels.items():
        if not isinstance(channel, GuildChannel):
            continue

        for i in range(0, len(to_delete), MAX_MESSAGES_PER_BULK_DELETE):
            await channel.delete_messages(
                to_delete[i : i + MAX_MESSAGES_PER_BULK_DELETE],
                reason=audit_log_reason_template(
                    author_name=author.name,
                    author_id=author.id,
                    reason="Mass delete",
                ),
            )

    for message in too_old:
        await message.delete()
