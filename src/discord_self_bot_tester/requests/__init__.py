"""
The sending half of the library: everything that goes out to discord's HTTP API.

A `Request` knows how to post itself; the builders assemble one. Interactions
(slash commands, button presses, dropdown selections, modal submissions) are the main
event, with scheduled events and reactions alongside them as ways of provoking a bot
into replying.

Requests can be sent on their own with `send`, but are normally handed to an
`..assertions` object instead, which installs a gateway filter first so the reply
cannot be missed.
"""

from ._base import Request, SelfBotRequestError, SelfBotRequestSetupError
from .commands import (
    InteractionType,
    ComponentType,
    ApplicationCommandArgValueType,
    ApplicationCommandType,
    ApplicationCommand,
    MessageComponent,
    ModalSubmitComponentData,
    ModalSubmitData,
    Interaction,
    ApplicationCommandBuilder
)
from .modal import ModalResponseBuilder
from .component import (
    find_button,
    find_dropdown,
    press_button,
    select_dropdown,
    select_dropdown_values
)
from .events import (
    PrivacyLevel,
    GuildScheduledEventEntityType,
    RecurrenceRuleFrequency,
    RecurrenceRuleWeekday,
    RecurrenceRuleMonth,
    RecurrenceRuleNWeekday,
    RecurrenceRule,
    GuildScheduledEventEntity,
    ScheduledEvent,
    ScheduledEventBuilder
)
from .reactions import Reaction, build_reaction
from .attachments import Attachment, build_attachment

__all__ = [
    "Request",
    "SelfBotRequestError",
    "SelfBotRequestSetupError",
    "InteractionType",
    "ComponentType",
    "ApplicationCommandArgValueType",
    "ApplicationCommandType",
    "ApplicationCommand",
    "MessageComponent",
    "ModalSubmitComponentData",
    "ModalSubmitData",
    "Interaction",
    "ApplicationCommandBuilder",
    "ModalResponseBuilder",
    "find_button",
    "find_dropdown",
    "press_button",
    "select_dropdown",
    "select_dropdown_values",
    "PrivacyLevel",
    "GuildScheduledEventEntityType",
    "RecurrenceRuleFrequency",
    "RecurrenceRuleWeekday",
    "RecurrenceRuleMonth",
    "RecurrenceRuleNWeekday",
    "RecurrenceRule",
    "GuildScheduledEventEntity",
    "ScheduledEvent",
    "ScheduledEventBuilder",
    "Reaction",
    "build_reaction",
    "Attachment",
    "build_attachment"
]
