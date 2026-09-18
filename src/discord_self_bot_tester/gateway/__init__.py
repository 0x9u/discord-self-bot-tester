"""
The receiving half of the library: everything that arrives over discord's user
websocket.

`Gateway` owns the connection and turns raw payloads into `GatewayEvent` models
(`Message`, `Modal`, `CommandAutoCompleteResponse`). It only builds an event when a
`Filter` installed by an assertion claims the payload, so unrelated traffic on a busy
account is discarded rather than queued.

Nothing here sends anything to discord; see `..requests` for that, and `..assertions`
for the pairing of a request with the event it is expected to produce.
"""

from ._base import GatewayEvent, MessageFilter, ModalFilter
from .ws import Gateway, GatewayException
from .autocomplete import (
    CommandAutoCompleteChoice,
    CommandAutoCompleteChoiceValueType,
    CommandAutoCompleteResponse
)
from .message import Message, MessageAuthor
from .modal import Modal
from .component import (
    ActionRowComponent,
    ButtonStyle,
    ButtonComponent,
    TextInputStyle,
    TextInputComponent,
    SelectOption,
    StringSelectComponent,
    UserSelectComponent,
    RoleSelectComponent,
    MentionableSelectComponent,
    ChannelSelectComponent,
    TextDisplayComponent,
    LabelComponent,
    FileUpload,
    RadioGroupOption,
    RadioGroup,
    CheckboxGroupOption,
    CheckboxGroup,
    Checkbox,
    Component,
    child_components,
    walk_components,
)

__all__ = [
    "GatewayEvent",
    "MessageFilter",
    "ModalFilter",
    "Gateway",
    "GatewayException",
    "CommandAutoCompleteChoice",
    "CommandAutoCompleteChoiceValueType",
    "CommandAutoCompleteResponse",
    "Message",
    "MessageAuthor",
    "Modal",
    "ActionRowComponent",
    "ButtonStyle",
    "ButtonComponent",
    "TextInputStyle",
    "TextInputComponent",
    "SelectOption",
    "StringSelectComponent",
    "UserSelectComponent",
    "RoleSelectComponent",
    "MentionableSelectComponent",
    "ChannelSelectComponent",
    "TextDisplayComponent",
    "LabelComponent",
    "FileUpload",
    "RadioGroupOption",
    "RadioGroup",
    "CheckboxGroupOption",
    "CheckboxGroup",
    "Checkbox",
    "Component",
    "child_components",
    "walk_components"
]
