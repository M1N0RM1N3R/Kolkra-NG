from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints

# from pydantic_extra_types.language_code import LanguageAlpha2

LanguageAlpha2 = Annotated[str, StringConstraints(pattern=r"[a-z]{2}")]


class DetectRequest(BaseModel):
    q: str
    api_key: UUID | None


class DetectResponseItem(BaseModel):
    confidence: int = Field(ge=0, le=100)
    language: LanguageAlpha2


class LanguagesResponseItem(BaseModel):
    code: LanguageAlpha2
    name: str
    targets: set[LanguageAlpha2]


class TranslateRequest(BaseModel):
    q: str
    source: LanguageAlpha2 | Literal["auto"]
    target: LanguageAlpha2
    format: Literal["text", "html"] = "text"
    alternatives: NonNegativeInt = 0
    api_key: UUID | None


class TranslateResponse(BaseModel):
    translatedText: str
    detectedLanguage: DetectResponseItem | None = None
    alternatives: list[str] | None = None
