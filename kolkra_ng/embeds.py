from typing import Any

from discord import Color, Embed


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
        color = color or None
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
