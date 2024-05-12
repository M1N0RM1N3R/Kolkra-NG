import contextlib
from datetime import datetime
from typing import Any

from discord import Color, Embed
from discord.ext import commands
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self


def icons8(name: str, style: str = "color", animated: bool = False) -> str:
    """Fills in the blanks in an Icons8 CDN URL for a given icon.

    Args:
        name (str): The name of the icon.
        style (str, optional): The icon style. Defaults to "color".
        animated (bool, optional): Whether to look for an animated GIF or static PNG. Defaults to False.

    Returns:
        str: The filled-in URL.
    """
    return f"https://img.icons8.com/{style}/{name}.{'gif' if animated else 'png'}"


class OkEmbed(Embed):
    def __init__(
        self,
        title: str = "Success",
        color: Color | None = None,
        **kwargs: Any,
    ):
        color = color or Color.green()
        super().__init__(title=title, color=color, **kwargs)
        self.set_thumbnail(url=icons8("ok"))


class WarningEmbed(Embed):
    def __init__(
        self,
        title: str = "Warning",
        color: Color | None = None,
        **kwargs: Any,
    ):
        color = color or Color.orange()
        super().__init__(title=title, color=color, **kwargs)
        self.set_thumbnail(url=icons8("error"))


class ErrorEmbed(Embed):
    def __init__(
        self,
        title: str = "Error",
        color: Color | None = None,
        **kwargs: Any,
    ):
        color = color or Color.red()
        super().__init__(title=title, color=color, **kwargs)
        self.set_thumbnail(url=icons8("broken-robot"))


class QuestionEmbed(Embed):
    def __init__(
        self,
        title: str = "Question",
        color: Color | None = None,
        **kwargs: Any,
    ):
        color = color or Color.blurple()
        super().__init__(title=title, color=color, **kwargs)
        self.set_thumbnail(url=icons8("ask-question"))


class InfoEmbed(Embed):
    def __init__(
        self,
        title: str = "Info",
        color: Color | None = None,
        **kwargs: Any,
    ):
        color = color or Color.blue()
        super().__init__(title=title, color=color, **kwargs)
        self.set_thumbnail(url=icons8("info"))


class AccessDeniedEmbed(Embed):
    def __init__(
        self,
        title: str = "Access Denied",
        color: Color | None = None,
        **kwargs: Any,
    ):
        color = color or Color.red()
        super().__init__(title=title, color=color, **kwargs)
        self.set_thumbnail(url=icons8("no-entry"))


class WaitEmbed(Embed):
    def __init__(self, title: str = "Wait", color: Color | None = None, **kwargs: Any):
        color = color or Color.yellow()
        super().__init__(title=title, color=color, **kwargs)
        self.set_thumbnail(url=icons8("hourglass"))


MAX_LENGTHS = {
    "title": 256,
    "description": 4096,
    "fields": 25,
    "field.name": 256,
    "field.value": 1024,
    "footer.text": 2048,
    "author.name": 256,
    "total": 6000,
}


class _EmbedFooter(BaseModel):
    text: str | None = Field(max_length=MAX_LENGTHS["footer.text"], default=None)
    icon_url: str | None = None


class _EmbedField(BaseModel):
    name: str | None = Field(max_length=MAX_LENGTHS["field.name"], default=None)
    value: str | None = Field(max_length=MAX_LENGTHS["field.value"], default=None)
    inline: bool = True


class _EmbedMedia(BaseModel):
    url: str | None = None


class _EmbedAuthor(BaseModel):
    name: str | None = Field(max_length=MAX_LENGTHS["author.name"], default=None)
    url: str | None = None
    icon_url: str | None = None


class SplitEmbed(BaseModel):
    """Representation of an embed that can have its description and fields split across multiple embeds."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    color: int | Color | None = None
    title: str | None = Field(default=None, max_length=MAX_LENGTHS["title"])
    url: str | None = None
    description: str | None = None
    timestamp: datetime | None = None
    footer: _EmbedFooter | None = None
    image: _EmbedMedia | None = None
    thumbnail: _EmbedMedia | None = None
    author: _EmbedAuthor | None = None
    fields: list[_EmbedField] | None = None

    @classmethod
    def from_single(cls, embed: Embed) -> Self:
        return cls(**embed.to_dict())  # pyright: ignore [reportCallIssue]

    def __split_description(self) -> list[str] | None:
        if not self.description:
            return None
        paginator = commands.Paginator(
            prefix=None, suffix=None, max_size=MAX_LENGTHS["description"]
        )
        for line in self.description.split(paginator.linesep):
            paginator.add_line(line)
        return paginator.pages

    def __populate_top_embed(self, embed: Embed) -> None:
        if self.thumbnail:
            embed.set_thumbnail(**dict(self.thumbnail))
        if self.author:
            embed.set_author(**dict(self.author))
        embed.title = self.title
        embed.url = self.url

    def __populate_bottom_embed(self, embed: Embed) -> None:
        embed.timestamp = self.timestamp
        if self.footer:
            embed.set_footer(**dict(self.footer))
        if self.image:
            embed.set_image(**dict(self.image))

    def embeds(self) -> list[Embed]:
        base = lambda: Embed(color=self.color)
        result = []
        e = base()

        if chunks := self.__split_description():
            for chunk in chunks:
                e = base()
                e.description = chunk
                result.append(e)

        if self.fields:
            for field in self.fields:
                if (
                    len(e.fields) > MAX_LENGTHS["fields"]
                    or len(e) + len((field.name or "") + (field.value or ""))
                    > MAX_LENGTHS["total"]
                ):
                    result.append(e)
                    e = base()
                e.add_field(**dict(field))

        if not result:
            result.append(e)
        self.__populate_top_embed(result[0])
        self.__populate_bottom_embed(result[-1])
        return result

    # Clone of d.py's Embed API
    def set_footer(self, **kwargs) -> Self:
        self.footer = _EmbedFooter(**kwargs)
        return self

    def remove_footer(self) -> Self:
        self.footer = None
        return self

    def set_image(self, **kwargs) -> Self:
        self.image = _EmbedMedia(**kwargs)
        return self

    def set_thumbnail(self, **kwargs) -> Self:
        self.thumbnail = _EmbedMedia(**kwargs)
        return self

    def set_author(self, **kwargs) -> Self:
        self.author = _EmbedAuthor(**kwargs)
        return self

    def remove_author(self) -> Self:
        self.author = None
        return self

    def add_field(self, **kwargs) -> Self:
        f = _EmbedField(**kwargs)
        if self.fields is None:
            self.fields = []
        self.fields.append(f)
        return self

    def insert_field_at(self, index: int, **kwargs) -> Self:
        f = _EmbedField(**kwargs)
        if self.fields is None:
            self.fields = []
        self.fields.insert(index, f)
        return self

    def clear_fields(self) -> Self:
        self.fields = None
        return self

    def remove_field(self, index: int) -> Self:
        if self.fields is None:
            return self
        with contextlib.suppress(IndexError):
            self.fields.pop(index)
        return self

    def set_field_at(self, index: int, **kwargs) -> Self:
        try:
            self.fields[index] = _EmbedField(**kwargs)  # pyright: ignore # noqa: PGH003
        except (TypeError, IndexError, AttributeError) as e:
            raise IndexError(index) from e
        return self
