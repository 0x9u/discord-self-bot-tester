"""
The suggestions discord's autocomplete handler sent back for a partially typed command
argument.
"""

from ._base import GatewayEvent

from pydantic import BaseModel
from typing import TypeAlias

CommandAutoCompleteChoiceValueType: TypeAlias = float | int | str

class CommandAutoCompleteChoice(BaseModel):
    """
    One suggestion: `name` is rendered in the client, `value` is what gets submitted.
    """

    name: str
    value: CommandAutoCompleteChoiceValueType

    def __hash__(self):
        return hash((self.name, self.value))

class CommandAutoCompleteResponse(GatewayEvent):
    """
    A full autocomplete response, queued by the gateway without needing a filter.
    """

    choices: list[CommandAutoCompleteChoice]
