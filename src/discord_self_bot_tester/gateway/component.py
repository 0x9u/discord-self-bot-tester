from ..shared import Emoji

from collections.abc import Iterator
from enum import Enum
from pydantic import BaseModel, Field
from typing import Annotated, Literal, TypeAlias

class ActionRowComponent(BaseModel):
    type: Literal[1]
    id: int | None = None
    components: list["Component"]

class ButtonStyle(Enum):
	PRIMARY = 1
	SECONDARY = 2
	SUCCESS = 3
	DANGER = 4
	LINK = 5
	PREMIUM = 6

class ButtonComponent(BaseModel):
    type: Literal[2]
    # https://discordjs.dev/docs/packages/discord-api-types/0.38.41/v10/APIButtonBase:Interface#id
    id: int | None = None
    style: ButtonStyle
    label: str | None = None
    emoji: str | None = None
    # what we actually want to use, absent on LINK and PREMIUM buttons
    custom_id: str | None = None
    sku_id: str | None = None
    url: str | None = None
    disabled: bool | None = None

class TextInputStyle(Enum):
    SHORT = 1
    PARAGRAPH = 2

class TextInputComponent(BaseModel):
    type: Literal[4]
    id: int | None = None
    custom_id: str
    style: TextInputStyle
    # deprecated by discord in favour of wrapping the input in a LabelComponent
    label: str | None = None
    min_length: int | None = None
    max_length: int | None = None
    required: bool | None = None
    value: str | None = None
    placeholder: str | None = None

class SelectOption(BaseModel):
	label: str
	value: str
	description: str | None = None
	emoji: Emoji | None = None
	default: bool | None = None

class SelectComponent(BaseModel):
	id: int | None = None
	custom_id: str
	options: list[SelectOption]
	placeholder: str | None = None
	min_values: int | None = None
	max_values: int | None = None
	required: bool | None = None
	disabled: bool | None = None

class StringSelectComponent(SelectComponent):
    type: Literal[3]

class UserSelectComponent(SelectComponent):
    type: Literal[5]

class RoleSelectComponent(SelectComponent):
    type: Literal[6]

class MentionableSelectComponent(SelectComponent):
    type: Literal[7]

class ChannelSelectComponent(SelectComponent):
    type: Literal[8]

class TextDisplayComponent(BaseModel):
    type: Literal[10]
    id: int | None = None
    content: str

class LabelComponent(BaseModel):
    type: Literal[18]
    id: int | None = None
    label: str
    description: str | None = None
    component: "Component"

class FileUpload(BaseModel):
    type: Literal[19]
    id: int | None = None
    custom_id: str
    min_values: int | None = None
    max_values: int | None = None
    required: bool | None = None
    file_types : list[str] | None = None

class RadioGroupOption(BaseModel):
	value: str
	label: str
	description: str | None = None
	default: bool | None = None

class RadioGroup(BaseModel):
    type: Literal[21]
    id: int | None = None
    custom_id: str
    options: list[RadioGroupOption]
    required: bool | None = None

class CheckboxGroupOption(BaseModel):
	value: str
	label: str
	description: str | None = None
	default: bool | None = None

class CheckboxGroup(BaseModel):
    type: Literal[22]
    id: int | None = None
    custom_id: str
    options: list[CheckboxGroupOption]
    min_values: int | None = None
    max_values: int | None = None
    required: bool | None = None

class Checkbox(BaseModel):
    type: Literal[23]
    id: int | None = None
    custom_id: str
    default: bool | None = None

Component : TypeAlias = Annotated[
    ActionRowComponent
    | ButtonComponent
    | TextInputComponent
    | StringSelectComponent
    | UserSelectComponent
    | RoleSelectComponent
    | MentionableSelectComponent
    | ChannelSelectComponent
    | TextDisplayComponent
    | LabelComponent
    | FileUpload
    | RadioGroup
    | CheckboxGroup
    | Checkbox,
    Field(discriminator="type")
]

# `Component` is only defined now, so the self referencing models need a second pass
ActionRowComponent.model_rebuild()
LabelComponent.model_rebuild()

def child_components(component: Component) -> list[Component]:
    """
    The components nested directly inside `component`, layout components only.
    """
    if isinstance(component, ActionRowComponent):
        return component.components
    if isinstance(component, LabelComponent):
        return [component.component]
    return []

def walk_components(components: list[Component]) -> Iterator[Component]:
    """
    Every component in the tree, parents before their children.
    """
    for component in components:
        yield component
        yield from walk_components(child_components(component))
