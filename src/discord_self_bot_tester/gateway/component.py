from ..shared import Emoji

from enum import Enum
from pydantic import BaseModel
from typing import Literal, TypeAlias

class ActionRowComponent(BaseModel):
    type: Literal[1]
    components: "Component"

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
    # what we actually want to use
    custom_id: str
    sku_id: str | None = None
    url: str | None = None
    disabled: bool | None = None

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

Component : TypeAlias = (
    ActionRowComponent
    | ButtonComponent
    | StringSelectComponent
    | UserSelectComponent
    | RoleSelectComponent
    | MentionableSelectComponent
    | ChannelSelectComponent
    | LabelComponent
    | FileUpload
    | RadioGroup
    | CheckboxGroup
    | Checkbox
)