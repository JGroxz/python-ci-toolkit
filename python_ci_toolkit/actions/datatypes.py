from dataclasses import dataclass, field
from typing import TypeAlias

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass
class ActionOutput:
    """
    Represents the output of a CI action.
    """
    values: dict[str, JsonValue] = field(default_factory=dict)
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
