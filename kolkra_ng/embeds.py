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


icon_urls = {
    "check": icons8("ok"),
    "warning": icons8("error"),
    "error": icons8("broken-robot"),
    "question": icons8("ask-question"),
}
