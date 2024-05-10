"""Decorator to make Pydantic handle an enum by name rather than by value.
Adapted from https://github.com/pydantic/pydantic/discussions/6466.
"""

import types
from enum import EnumMeta
from typing import Any, TypeVar

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema


def __get_pydantic_core_schema__(
    cls: EnumMeta, _source_type: Any, _handler: GetCoreSchemaHandler
) -> CoreSchema:
    return core_schema.no_info_after_validator_function(
        lambda x: getattr(cls, x),
        core_schema.str_schema(),
        serialization=core_schema.plain_serializer_function_ser_schema(
            lambda x: x.name
        ),
    )


def __get_pydantic_json_schema__(
    cls: EnumMeta, _core_schema: CoreSchema, _handler: GetJsonSchemaHandler
) -> JsonSchemaValue:
    return {
        "enum": [m.name for m in cls],  # pyright: ignore [reportAttributeAccessIssue]
        "type": "string",
    }


E = TypeVar("E", bound=EnumMeta)


def by_name(cls: E) -> E:

    cls.__get_pydantic_core_schema__ = (  # pyright: ignore # noqa: PGH003
        types.MethodType(__get_pydantic_core_schema__, cls)
    )
    cls.__get_pydantic_json_schema__ = (  # pyright: ignore # noqa: PGH003
        types.MethodType(__get_pydantic_json_schema__, cls)
    )
    return cls
