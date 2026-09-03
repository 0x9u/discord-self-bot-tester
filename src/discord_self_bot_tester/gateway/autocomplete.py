from ._base import GatewayEvent

from pydantic import BaseModel
from typing import TypeAlias

from typing import List

CommandAutoCompleteChoiceValueType: TypeAlias = float | int | str

class CommandAutoCompleteChoice(BaseModel):
    name: str
    value: CommandAutoCompleteChoiceValueType

    def __hash__(self):
        return hash((self.name, self.value))

class CommandAutoCompleteResponse(GatewayEvent):
    choices: List[CommandAutoCompleteChoice]
