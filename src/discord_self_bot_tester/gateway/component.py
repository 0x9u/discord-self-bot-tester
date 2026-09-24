"""
Discord's message and modal component tree.

Each component has its own model, descriminated by its `type` number. Note that components
can be recursive (see `ActionRowComponent` and `LabelComponent`) so `child_components` and `walk_components` exist to
traverse it without every caller re-learning which types nest.

The numbering is discord's own and is shared between message views and modals, so the
same models cover both; `..requests.commands.ComponentType` is the matching enum for
the payloads we send back.
"""

from .emoji import Emoji

from collections.abc import Iterator
from enum import Enum
from pydantic import BaseModel, Field
from typing import Annotated, Literal, TypeAlias

class ActionRowComponent(BaseModel):
    """
    A horizontal row holding up to five interactive components.
    """

    type: Literal[1]
    id: int | None = None
    components: list["Component"]

class ButtonStyle(Enum):
	"""
	How a button is rendered.

	LINK and PREMIUM are handled entirely by the client and send no interaction.
	"""

	PRIMARY = 1
	SECONDARY = 2
	SUCCESS = 3
	DANGER = 4
	LINK = 5
	PREMIUM = 6

class ButtonComponent(BaseModel):
    """
    A clickable button.

    Only buttons carrying a `custom_id` produce an interaction; LINK and PREMIUM
    buttons are handled entirely by the client, which is why `custom_id` is optional
    here and checked by `..requests.component.find_button`.
    """

    type: Literal[2]
    # https://discordjs.dev/docs/packages/discord-api-types/0.38.41/v10/APIButtonBase:Interface#id
    id: int | None = None
    style: ButtonStyle
    label: str | None = None
    emoji: Emoji | None = None
    # what we actually want to use, absent on LINK and PREMIUM buttons
    custom_id: str | None = None
    sku_id: str | None = None
    url: str | None = None
    disabled: bool | None = None

class TextInputStyle(Enum):
    """
    Whether a modal text field is a single line (SHORT) or a box (PARAGRAPH).
    """

    SHORT = 1
    PARAGRAPH = 2

class TextInputComponent(BaseModel):
    """
    A free text field in a modal, either one line (SHORT) or many (PARAGRAPH).
    """

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
	"""
	One entry in a string select or a radio/checkbox group.

	`label` is what the client renders and `value` is what gets submitted; the helpers
	let tests name either, since a test written against labels reads like the thing a
	user would actually click.
	"""

	label: str
	value: str
	description: str | None = None
	emoji: Emoji | None = None
	default: bool | None = None

class SelectComponentBase(BaseModel):
	"""
	Shared shape of every select menu.
    
    Contains the attributes that are shared among its subclasses, e.g. min_values and max_values.
    Note this is not a `Component`.
	"""

	id: int | None = None
	custom_id: str
	
	placeholder: str | None = None
	min_values: int | None = None
	max_values: int | None = None
	required: bool | None = None
	disabled: bool | None = None

class StringSelectComponent(SelectComponentBase):
    """
    A menu of developer defined options. The only select whose `options` are populated.
    """

    type: Literal[3]
    options: list[SelectOption]

class UserSelectComponent(SelectComponentBase):
    """
    A user picker. Submits user ids, so use `select_dropdown_values` on it.
    """

    type: Literal[5]

class RoleSelectComponent(SelectComponentBase):
    """
    A role picker. Submits role ids, so use `select_dropdown_values` on it.
    """

    type: Literal[6]

class MentionableSelectComponent(SelectComponentBase):
    """
    A picker over both users and roles. Submits ids of either kind.
    """

    type: Literal[7]

class ChannelSelectComponent(SelectComponentBase):
    """
    A channel picker. Submits channel ids, so use `select_dropdown_values` on it.
    """

    type: Literal[8]

SelectComponent : TypeAlias = (
    StringSelectComponent
    | UserSelectComponent
    | RoleSelectComponent
    | MentionableSelectComponent
    | MentionableSelectComponent
    | ChannelSelectComponent
)

class TextDisplayComponent(BaseModel):
    """
    Static markdown. Holds no value and produces no interaction.
    """

    type: Literal[10]
    id: int | None = None
    content: str

class LabelComponent(BaseModel):
    """
    Wraps a single component with the caption rendered above it.

    Discord's replacement for the text input's own deprecated `label`, and the thing
    `ModalResponseBuilder.select` matches on, because it is the text a user sees.
    """

    type: Literal[18]
    id: int | None = None
    label: str
    description: str | None = None
    component: "Component"

class FileUpload(BaseModel):
    """
    A file picker in a modal. Its submitted values are uploaded attachment ids.
    """

    type: Literal[19]
    id: int | None = None
    custom_id: str
    min_values: int | None = None
    max_values: int | None = None
    required: bool | None = None
    file_types : list[str] | None = None

class RadioGroupOption(BaseModel):
	"""
	One choice in a `RadioGroup`.
	"""

	value: str
	label: str
	description: str | None = None
	default: bool | None = None

class RadioGroup(BaseModel):
    """
    A set of options of which exactly one can be chosen.
    """

    type: Literal[21]
    id: int | None = None
    custom_id: str
    options: list[RadioGroupOption]
    required: bool | None = None

class CheckboxGroupOption(BaseModel):
	"""
	One choice in a `CheckboxGroup`.
	"""

	value: str
	label: str
	description: str | None = None
	default: bool | None = None

class CheckboxGroup(BaseModel):
    """
    A set of options of which several can be chosen, bounded by min/max values.
    """

    type: Literal[22]
    id: int | None = None
    custom_id: str
    options: list[CheckboxGroupOption]
    min_values: int | None = None
    max_values: int | None = None
    required: bool | None = None

class Checkbox(BaseModel):
    """
    A single on/off box. Submits a bool rather than a list of values.
    """

    type: Literal[23]
    id: int | None = None
    custom_id: str
    default: bool | None = None

# Any component discord may send us, discriminated on the wire `type` number so
# pydantic picks the right model without trying each in turn.
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

# requires second pass because `Component` is defined after
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
