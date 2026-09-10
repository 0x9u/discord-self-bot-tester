from ..bot import Bot

from ..gateway._base import MessageFilter
from ..gateway.component import (
    ButtonComponent,
    ButtonStyle,
    SelectComponent,
    walk_components,
)
from ..gateway.message import Message
from ..requests._base import Request
from ..requests.commands import Interaction

from ._base import Assertion

from pydantic import BaseModel
from typing import Self
import re

class ButtonExpectation(BaseModel):
    """
    A button the message has to carry, matched on whichever fields are set.
    """
    label: str | None = None
    custom_id: str | None = None
    style: ButtonStyle | None = None
    disabled: bool | None = None

    def matches(self, button: ButtonComponent) -> bool:
        if self.label is not None and self.label != button.label:
            return False
        if self.custom_id is not None and self.custom_id != button.custom_id:
            return False
        if self.style is not None and self.style != button.style:
            return False
        # an absent `disabled` means enabled, which is what discord defaults it to
        if self.disabled is not None and self.disabled != bool(button.disabled):
            return False
        return True

    def __str__(self) -> str:
        wanted = {name: value for name, value in (
            ("label", self.label),
            ("custom_id", self.custom_id),
            ("style", self.style.name if self.style is not None else None),
            ("disabled", self.disabled),
        ) if value is not None}
        return str(wanted)

class DropdownExpectation(BaseModel):
    """
    A select menu the message has to carry, matched on whichever fields are set.

    `option_labels` and `option_values` have to match the menu's options exactly, in
    order, so a reordered or padded out menu is caught.
    """
    custom_id: str | None = None
    placeholder: str | None = None
    option_labels: list[str] | None = None
    option_values: list[str] | None = None
    disabled: bool | None = None

    def matches(self, dropdown: SelectComponent) -> bool:
        if self.custom_id is not None and self.custom_id != dropdown.custom_id:
            return False
        if self.placeholder is not None and self.placeholder != dropdown.placeholder:
            return False
        if self.option_labels is not None and \
                self.option_labels != [option.label for option in dropdown.options]:
            return False
        if self.option_values is not None and \
                self.option_values != [option.value for option in dropdown.options]:
            return False
        if self.disabled is not None and self.disabled != bool(dropdown.disabled):
            return False
        return True

    def __str__(self) -> str:
        wanted = {name: value for name, value in (
            ("custom_id", self.custom_id),
            ("placeholder", self.placeholder),
            ("option_labels", self.option_labels),
            ("option_values", self.option_values),
            ("disabled", self.disabled),
        ) if value is not None}
        return str(wanted)

def _describe_button(button: ButtonComponent) -> dict[str, object]:
    return {"label": button.label, "custom_id": button.custom_id,
            "style": button.style.name, "disabled": bool(button.disabled)}

def _describe_dropdown(dropdown: SelectComponent) -> dict[str, object]:
    return {"custom_id": dropdown.custom_id, "placeholder": dropdown.placeholder,
            "option_labels": [option.label for option in dropdown.options],
            "disabled": bool(dropdown.disabled)}

class MessageAssertion(Assertion[Request, Message]):
    # what to distingish the message from
    # if None, it will pick the next message in the websocket, or if
    # the request is a app command, it will pick the message replying to the command.
    message_filter: MessageFilter | None

    # if no assert conditions are set, it will just assert the next message being sent next that matches these filters

    content_search_pattern: str | None
    mentions: list[str] | None  # list of user ids
    mention_roles: list[str] | None
    
    # each one has to be matched by at least one button on the message
    buttons: list[ButtonExpectation] = []
    # the labels of every button on the message, exactly and in order
    button_labels: list[str | None] | None = None
    # each one has to be matched by at least one select menu on the message
    dropdowns: list[DropdownExpectation] = []

    def _check(self, gateway_event: Message):
        content_search_pattern = self.content_search_pattern

        if content_search_pattern is not None and re.match(content_search_pattern, gateway_event.content) is None:
            raise AssertionError(
                f"Mismatch\nGot: {gateway_event.content}\nMust match: {content_search_pattern}")

        if self.mentions is not None and gateway_event.mentions != self.mentions:
            raise AssertionError(
                f"Mismatch\nGot: {gateway_event.mentions}\nMust match: {self.mentions}")

        if self.mention_roles is not None and gateway_event.mention_roles != self.mention_roles:
            raise AssertionError(
                f"Mismatch\nGot: {gateway_event.mention_roles}\nMust match: {self.mention_roles}")

        self._check_components(gateway_event)

    def _check_components(self, gateway_event: Message):
        components = list(walk_components(gateway_event.components or []))
        buttons = [component for component in components
                   if isinstance(component, ButtonComponent)]
        dropdowns = [component for component in components
                     if isinstance(component, SelectComponent)]

        for expectation in self.buttons:
            if not any(expectation.matches(button) for button in buttons):
                raise AssertionError(
                    f"Mismatch\nGot buttons: {[_describe_button(button) for button in buttons]}"
                    f"\nMust include a button: {expectation}")

        if self.button_labels is not None:
            labels = [button.label for button in buttons]
            if labels != self.button_labels:
                raise AssertionError(
                    f"Mismatch\nGot: {labels}\nMust match: {self.button_labels}")

        for expectation in self.dropdowns:
            if not any(expectation.matches(dropdown) for dropdown in dropdowns):
                raise AssertionError(
                    f"Mismatch\nGot dropdowns: {[_describe_dropdown(dropdown) for dropdown in dropdowns]}"
                    f"\nMust include a dropdown: {expectation}")

    async def assert_request(self, bot : Bot, req : Request, deadline: int = 5) -> Message:
        if self.message_filter is None:
            self.message_filter = MessageFilter(
                author_id=None,
                channel_id=None,
                nonce_id=req.nonce if isinstance(
                    req, Interaction) else None
            )
        elif self.message_filter.is_followup and isinstance(req, Interaction):
            self.message_filter.nonce_id = req.nonce
        
        bot._gateway._assert_filter = self.message_filter
        
        await req.send(bot)
        
        gateway_event = await bot.get_next_gateway_event(deadline)
        
        if not isinstance(gateway_event, Message):
            raise TypeError("Expected message, got: " +
                                type(gateway_event).__name__)
                
        self._check(gateway_event)
        
        return gateway_event

    async def assert_gateway(self, bot : Bot, deadline: int = 5) -> Message:
        if self.message_filter is None:
            raise TypeError("MessageAssertion must have a message_filter for assert_gateway")
        
        bot._gateway._assert_filter = self.message_filter
        
        gateway_event = await bot.get_next_gateway_event(deadline)
        
        if not isinstance(gateway_event, Message):
            raise TypeError("Expected message, got: " +
                                type(gateway_event).__name__)
                
        self._check(gateway_event)
        
        return gateway_event

class MessageAssertionBuilder:
    data: MessageAssertion

    def __init__(self):
        self.data = MessageAssertion(
            message_filter=None, content_search_pattern=None, mentions=None, mention_roles=None)

    def filter_by_author(self, author_id: int) -> Self:
        if self.data.message_filter is None:
            self.data.message_filter = MessageFilter(
                author_id=str(author_id), channel_id=None, nonce_id=None, message_flags=None)
            return self

        self.data.message_filter.author_id = str(author_id)
        return self

    def filter_by_channel(self, channel_id: int) -> Self:
        if self.data.message_filter is None:
            self.data.message_filter = MessageFilter(
                author_id=None, channel_id=str(channel_id), nonce_id=None, message_flags=None)
            return self

        self.data.message_filter.channel_id = str(channel_id)
        return self

    def filter_by_interaction_from_author(self) -> Self:
        if self.data.message_filter is None:
            self.data.message_filter = MessageFilter(
                author_id=None, channel_id=None, nonce_id=None, message_flags=None)
        self.data.message_filter.interaction_is_from_author = True
        return self

    
    # NOTE: use this if the command is deferred
    def filter_by_message_update(self) -> Self:
        if self.data.message_filter is None:
            self.data.message_filter = MessageFilter(
                author_id=None, channel_id=None, nonce_id=None, message_flags=None)
        self.data.message_filter.message_payload_type = "MESSAGE_UPDATE"
        return self

    def filter_by_followup_message(self) -> Self:
        if self.data.message_filter is None:
            self.data.message_filter = MessageFilter(
                author_id=None, channel_id=None, nonce_id=None, message_flags=None)
        self.data.message_filter.is_followup = True
        return self
    
    def filter_by_message_flags(self, flags: int) -> Self:
        if self.data.message_filter is None:
                self.data.message_filter = MessageFilter(
                    author_id=None, channel_id=None, nonce_id=None, message_flags=None)
        self.data.message_filter.message_flags = flags
        return self

    def assert_by_message_content(self, pattern: str) -> Self:
        self.data.content_search_pattern = pattern
        return self

    def assert_by_mentions(self, mentions: list[int]) -> Self:
        self.data.mentions = list(map(str, mentions))
        return self

    def assert_by_mention_roles(self, mention_roles: list[int]) -> Self:
        self.data.mention_roles = list(map(str, mention_roles))
        return self

    def assert_by_button(self, label: str | None = None, custom_id: str | None = None,
                         style: ButtonStyle | None = None,
                         disabled: bool | None = None) -> Self:
        """
        Asserts the message carries a button matching everything given.

        Call it more than once to assert several buttons.
        """
        if label is None and custom_id is None and style is None and disabled is None:
            raise TypeError(
                "assert_by_button needs at least one of label, custom_id, style or disabled")

        self.data.buttons.append(ButtonExpectation(
            label=label, custom_id=custom_id, style=style, disabled=disabled))
        return self

    def assert_by_button_labels(self, labels: list[str | None]) -> Self:
        """
        Asserts these are the labels of every button on the message, in order.
        """
        self.data.button_labels = labels
        return self

    def assert_by_dropdown(self, placeholder: str | None = None, custom_id: str | None = None,
                           option_labels: list[str] | None = None,
                           option_values: list[str] | None = None,
                           disabled: bool | None = None) -> Self:
        """
        Asserts the message carries a select menu matching everything given.

        `option_labels` and `option_values` have to match the menu's options exactly
        and in order.
        """
        if placeholder is None and custom_id is None and option_labels is None \
                and option_values is None and disabled is None:
            raise TypeError(
                "assert_by_dropdown needs at least one of placeholder, custom_id,"
                " option_labels, option_values or disabled")

        self.data.dropdowns.append(DropdownExpectation(
            placeholder=placeholder, custom_id=custom_id, option_labels=option_labels,
            option_values=option_values, disabled=disabled))
        return self

    def compile(self) -> MessageAssertion:
        return self.data