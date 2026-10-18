from ..bot import Bot

from ..gateway._base import MessageFilter
from ..gateway.component import (
    ButtonComponent,
    ButtonStyle,
    SelectComponent,
    StringSelectComponent,
    walk_components,
)
from ..gateway.message import Message
from ..requests._base import Request
from ..requests.commands import Interaction

from ._base import Assertion

from pydantic import BaseModel
from typing import Self
import re

# NOTE: Expectation postfix is used for assertion for children (e.g. components)

class ButtonExpectation(BaseModel):
    """
    A button the message has to carry, matched on whichever fields are set.
    """
    label: str | None = None
    custom_id: str | None = None
    style: ButtonStyle | None = None
    disabled: bool | None = None

    def matches(self, button: ButtonComponent) -> bool:
        """
        :param button: A button on the message.
        :returns: Whether it meets every field that is set.
        """
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

    :ivar option_labels: Have to match the menu's option labels exactly, in order, so a
        reordered or padded out menu is caught.
    :ivar option_values: Like ``option_labels``, for the option values.
    """
    custom_id: str | None = None
    placeholder: str | None = None
    option_labels: list[str] | None = None
    option_values: list[str] | None = None
    disabled: bool | None = None

    def matches(self, dropdown: SelectComponent) -> bool:
        """
        :param dropdown: A select menu on the message.
        :returns: Whether it meets every field that is set.
        """
        if self.custom_id is not None and self.custom_id != dropdown.custom_id:
            return False
        if self.placeholder is not None and self.placeholder != dropdown.placeholder:
            return False
        if self.option_labels is not None and \
                isinstance(dropdown, StringSelectComponent) and \
                self.option_labels != [option.label for option in dropdown.options]:
            return False
        if self.option_values is not None and \
                isinstance(dropdown, StringSelectComponent) and \
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
            "option_labels": [option.label for option in dropdown.options]
                if isinstance(dropdown, StringSelectComponent) else [],
            "disabled": bool(dropdown.disabled)}

class MessageAssertion(Assertion[Request, Message]):
    """
    Waits for one message and checks it. Build one with :class:`MessageAssertionBuilder`.

    :ivar message_filter: Which message to wait for. When ``None``, the reply to the
        request if it is an interaction, otherwise the next message on the gateway.
    :ivar content_search_pattern: A regex the content has to match.
    :ivar mentions: The user ids the message has to mention, in order.
    :ivar mention_roles: The role ids the message has to mention, in order.
    :ivar buttons: Buttons the message has to carry.
    :ivar button_labels: The labels of every button on the message, in order.
    :ivar dropdowns: Select menus the message has to carry.
    """

    message_filter: MessageFilter | None

    content_search_pattern: str | None
    mentions: list[str] | None
    mention_roles: list[str] | None
    
    # COMPONENTS
        
    buttons: list[ButtonExpectation] = []
    button_labels: list[str | None] | None = None
    dropdowns: list[DropdownExpectation] = []

    def _check(self, gateway_event: Message):
        content_search_pattern = self.content_search_pattern

        if content_search_pattern is not None and re.match(content_search_pattern, gateway_event.content) is None:
            raise AssertionError(
                f"Mismatch\nGot: {gateway_event.content}\nMust match: {content_search_pattern}")

        if self.mentions is not None and [mention.id for mention in gateway_event.mentions] != self.mentions:
            raise AssertionError(
                f"Mismatch\nGot: {gateway_event.mentions}\nMust match: {self.mentions}")

        if self.mention_roles is not None and gateway_event.mention_roles != self.mention_roles:
            raise AssertionError(
                f"Mismatch\nGot: {gateway_event.mention_roles}\nMust match: {self.mention_roles}")

        self._check_components(gateway_event)

    def _check_components(self, gateway_event: Message):
        """
        Checks the message's view against the button and dropdown expectations.

        The whole component tree is flattened first, so a button nested in an action
        row counts the same as a top level one.

        :raises AssertionError: If an expectation is not met.
        """
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
                nonce_id=req.nonce if isinstance(req, Interaction) else None)
        elif self.message_filter.is_followup and isinstance(req, Interaction):
            self.message_filter.nonce_id = req.nonce

        bot._gateway._assert_filter = self.message_filter

        await req.send(bot)

        return await self._receive(bot, deadline)

    async def assert_gateway(self, bot : Bot, deadline: int = 5) -> Message:
        """
        See :meth:`Assertion.assert_gateway <discord_self_bot_tester.assertions._base.Assertion.assert_gateway>`.

        :raises TypeError: If no filter was set, since without a request there is no
            reply to wait for.
        """
        if self.message_filter is None:
            raise TypeError("MessageAssertion must have a message_filter for assert_gateway")

        bot._gateway._assert_filter = self.message_filter

        return await self._receive(bot, deadline)

    async def _receive(self, bot: Bot, deadline: int) -> Message:
        """
        Waits for the message the installed filter claims, and checks it.

        :returns: The message.
        :raises TypeError: If the gateway handed back something other than a message.
        """
        gateway_event = await bot.get_next_gateway_event(deadline)

        if not isinstance(gateway_event, Message):
            raise TypeError("Expected message, got: " +
                                type(gateway_event).__name__)
                
        self._check(gateway_event)
        
        return gateway_event

class MessageAssertionBuilder:
    """
    Assembles a :class:`MessageAssertion`.

    ``filter_by_*`` narrows which message counts, ``assert_by_*`` states what has to be
    true of it. Calling neither means "the reply to the request I am about to send".
    Every method returns this builder. Example::

        await MessageAssertionBuilder()\\
            .filter_by_author(BOT_USER_ID)\\
            .assert_by_button("Confirm")\\
            .compile().assert_request(bot, interaction)
    """

    data: MessageAssertion

    def __init__(self):
        self.data = MessageAssertion(
            message_filter=None, content_search_pattern=None, mentions=None, mention_roles=None)

    def _filter(self) -> MessageFilter:
        if self.data.message_filter is None:
            self.data.message_filter = MessageFilter()
        return self.data.message_filter

    def filter_by_author(self, author_id: int) -> Self:
        """
        Only matches messages sent by one user.

        :param author_id: The user, normally the bot under test.
        """
        self._filter().author_id = str(author_id)
        return self

    def filter_by_channel(self, channel_id: int) -> Self:
        """
        Only matches messages in one channel.

        :param channel_id: The channel.
        """
        self._filter().channel_id = str(channel_id)
        return self

    def filter_by_interaction_from_author(self) -> Self:
        """
        Only matches messages produced by an interaction this account triggered.

        Useful on a busy channel where other people are using the same command.
        """
        self._filter().interaction_is_from_author = True
        return self

    def filter_by_message_update(self) -> Self:
        """
        Only matches messages being edited, rather than created.

        Useful when a command defers the response.
        """
        self._filter().message_payload_type = "MESSAGE_UPDATE"
        return self

    def filter_by_followup_message(self) -> Self:
        """
        Ties an explicitly filtered assertion back to the request's own nonce.

        Only needed when a ``filter_by_*`` has already been set, since the nonce is
        picked up automatically when no filter was given at all.
        """
        self._filter().is_followup = True
        return self

    def filter_by_message_flags(self, flags: int) -> Self:
        """
        Only matches messages with exactly these flags.

        :param flags: The message flags, e.g. 64 for an ephemeral reply.
        """
        self._filter().message_flags = flags
        return self

    def assert_by_message_content(self, pattern: str) -> Self:
        """
        :param pattern: A regex the content has to match, anchored at the start
            (:func:`re.match`).
        """
        self.data.content_search_pattern = pattern
        return self

    def assert_by_mentions(self, mentions: list[int]) -> Self:
        """
        :param mentions: Exactly the user ids the message has to mention, in order.
        """
        self.data.mentions = list(map(str, mentions))
        return self

    def assert_by_mention_roles(self, mention_roles: list[int]) -> Self:
        """
        :param mention_roles: Exactly the role ids the message has to mention, in order.
        """
        self.data.mention_roles = list(map(str, mention_roles))
        return self

    def assert_by_button(self, label: str | None = None, custom_id: str | None = None,
                         style: ButtonStyle | None = None,
                         disabled: bool | None = None) -> Self:
        """
        Asserts the message carries a button matching everything given.

        Call it more than once to assert several buttons.

        :param label: The text rendered on the button.
        :param custom_id: The button's developer defined id.
        :param style: How the button is rendered.
        :param disabled: Whether the button is greyed out.
        :raises TypeError: If nothing is given.
        """
        if label is None and custom_id is None and style is None and disabled is None:
            raise TypeError(
                "assert_by_button needs at least one of label, custom_id, style or disabled")

        self.data.buttons.append(ButtonExpectation(
            label=label, custom_id=custom_id, style=style, disabled=disabled))
        return self

    def assert_by_button_labels(self, labels: list[str | None]) -> Self:
        """
        :param labels: Exactly the labels of every button on the message, in order.
            ``None`` stands for a button with no label.
        """
        self.data.button_labels = labels
        return self

    def assert_by_dropdown(self, placeholder: str | None = None, custom_id: str | None = None,
                           option_labels: list[str] | None = None,
                           option_values: list[str] | None = None,
                           disabled: bool | None = None) -> Self:
        """
        Asserts the message carries a select menu matching everything given.

        :param placeholder: The text shown before anything is picked.
        :param custom_id: The menu's developer defined id.
        :param option_labels: Exactly the menu's option labels, in order.
        :param option_values: Exactly the menu's option values, in order.
        :param disabled: Whether the menu is greyed out.
        :raises TypeError: If nothing is given.
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
        """
        :returns: The finished assertion.
        """
        return self.data
