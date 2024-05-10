from datetime import datetime, timezone
from typing import Annotated, TypeVar

from pydantic.functional_validators import AfterValidator

T = TypeVar("T")


UtcDateTime = Annotated[
    datetime,
    AfterValidator(
        lambda dt: (
            dt.replace(tzinfo=timezone.utc)
            if dt.tzinfo is None
            else dt.astimezone(tz=timezone.utc)
        )
    ),
]
"""A datetime that is assumed to be in UTC unless explicitly included.
"""
