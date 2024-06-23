"""Because every other bot we've tried can go f**k themselves.
"""

import logging
from typing import Annotated
from uuid import UUID

from aiohttp import ClientSession
from discord import Color, Embed, Message
from discord.ext import commands
from pydantic import BaseModel, Field, HttpUrl, Secret, StringConstraints

# from pydantic_extra_types.language_code import LanguageAlpha2
from kolkra_ng.bot import Kolkra
from kolkra_ng.cogs.translate.api import (
    DetectRequest,
    DetectResponseItem,
    LanguagesResponseItem,
    TranslateRequest,
    TranslateResponse,
)
from kolkra_ng.embeds import WarningEmbed, icons8

log = logging.getLogger(__name__)

LanguageAlpha2 = Annotated[str, StringConstraints(pattern=r"[a-z]{2}")]


class TranslateConfig(BaseModel):
    target_language: LanguageAlpha2 = Field(
        default="en",
        description="The language to translate foreign-language messages to. Defaults to 'en' (English).",
    )
    api_base_url: HttpUrl = Field(
        description="Base URL of a [LibreTranslate](https://github.com/LibreTranslate/LibreTranslate) instance.",
    )
    api_key: Secret[UUID] | None = Field(
        default=None,
        description="An API key for the LibreTranslate instance, if required.",
    )
    aiohttp_params: dict = Field(
        default_factory=dict,
        description="Extra parameters to pass to the aiohttp.ClientSession constructor.",
    )


class TranslateCog(commands.Cog):
    def __init__(self, bot: Kolkra) -> None:
        super().__init__()
        self.bot = bot
        self.config = TranslateConfig(**bot.config.cogs.get(self.__cog_name__, {}))
        self.session = ClientSession(
            base_url=self.config.api_base_url.unicode_string(),
            **self.config.aiohttp_params,
        )

    async def cog_load(self) -> None:
        async with self.session.get("/languages") as resp:
            resp.raise_for_status()
            languages_response = [
                LanguagesResponseItem(**item) for item in await resp.json()
            ]
        self.all_languages = {
            language.code: language for language in languages_response
        }
        self.supported_languages = {
            code: language
            for code, language in self.all_languages.items()
            if self.config.target_language in language.targets
        }

    async def cog_unload(self) -> None:
        await self.session.close()

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        prefixes = await self.bot.get_prefix(message)
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        if (
            message.author.bot  # Ignore bots
            or not message.content  # Ignore empty messages
            or any(
                message.content.startswith(p) for p in prefixes
            )  # Ignore command invocations
        ):
            return
        async with self.session.post(
            "/detect",
            data=DetectRequest(
                q=message.content,
                api_key=(
                    key.get_secret_value() if (key := self.config.api_key) else None
                ),
            ).model_dump(mode="json", exclude_none=True),
        ) as resp:
            resp.raise_for_status()
            detect_response = [DetectResponseItem(**item) for item in await resp.json()]
        detected_language = max(detect_response, key=lambda x: x.confidence)
        if detected_language.language == self.config.target_language:
            return
        elif detected_language.language not in self.supported_languages:
            await message.reply(
                embed=WarningEmbed(
                    title="Language not supported!",
                    description=f"This message's detected language ({self.all_languages[detected_language.language].name}) cannot be translated to {self.all_languages[detected_language.language].name}.",
                ),
                mention_author=False,
            )
            return
        async with self.session.post(
            "/translate",
            data=TranslateRequest(
                q=message.content,
                api_key=(
                    key.get_secret_value() if (key := self.config.api_key) else None
                ),
                source=detected_language.language,
                target=self.config.target_language,
            ).model_dump(mode="json", exclude_none=True),
        ) as resp:
            resp.raise_for_status()
            translate_response = TranslateResponse(**await resp.json())
        await message.reply(
            embed=Embed(
                color=Color.blue(),
                title="Automatic translation",
                description=translate_response.translatedText,
            )
            .add_field(
                name="Language",
                value=f"{self.all_languages[detected_language.language].name} ({detected_language.confidence}% confidence) -> {self.all_languages[self.config.target_language].name}",
            )
            .set_thumbnail(url=icons8("translate-text"))
            .set_footer(text="Machine translations may not be 100% accurate."),
            mention_author=False,
        )


async def setup(bot: Kolkra) -> None:
    await bot.add_cog(TranslateCog(bot))
