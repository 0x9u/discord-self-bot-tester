from ..bot import Bot
from ..gateway.autocomplete import (
    CommandAutoCompleteResponse,
    CommandAutoCompleteChoice,
    CommandAutoCompleteChoiceValueType
)
from ..requests._base import Request

from ._base import Assertion

from typing import Self

class AutoCompleteAssertion(Assertion[Request, CommandAutoCompleteResponse]):
    """
    Waits for an autocomplete response and checks its choices.

    Build one with :class:`AutoCompleteAssertionBuilder`.

    :ivar choice_exact_match: Whether the response has to offer exactly ``choices`` in
        order, rather than merely containing them.
    :ivar choices: The suggestions the response has to offer.
    """

    choice_exact_match: bool
    choices: list[CommandAutoCompleteChoice]

    def _check(self, gateway_event: CommandAutoCompleteResponse):
        if self.choice_exact_match:
            if self.choices != gateway_event.choices:
                raise AssertionError(
                    f"Mismatch\nGot: {gateway_event.choices}\nMust match: {self.choices}")
        else:
            if not set(self.choices) <= set(gateway_event.choices):  # checks if not subset
                raise AssertionError(
                    f"Mismatch\nGot: {gateway_event.choices}\nMust include: {self.choices}")

    async def assert_gateway(self, bot: Bot, deadline: int = 5) -> CommandAutoCompleteResponse:
        gateway_event = await bot.get_next_gateway_event(deadline)
        
        if not isinstance(gateway_event, CommandAutoCompleteResponse):
            raise TypeError("Expected autocomplete response, got: " +
                            type(gateway_event).__name__)

        self._check(gateway_event)

        return gateway_event

    async def assert_request(self, bot: Bot, req : Request, deadline: int = 5) -> CommandAutoCompleteResponse:
        await req.send(bot)
        return await self.assert_gateway(bot, deadline)

class AutoCompleteAssertionBuilder:
    """
    Assembles an :class:`AutoCompleteAssertion`.

    The request it is given should be an ``APPLICATION_COMMAND_AUTOCOMPLETE``
    interaction with one argument marked ``focused=True``. Example::

        await AutoCompleteAssertionBuilder()\\
            .add_choice("standup", "standup-uuid")\\
            .compile().assert_request(bot, interaction, deadline=60)
    """

    data: AutoCompleteAssertion

    def __init__(self):
        self.data = AutoCompleteAssertion(choice_exact_match=False, choices=[])

    def set_choice_exact_match(self, choice_exact_match: bool) -> Self:
        """
        :param choice_exact_match: ``True`` if the choices have to match exactly and in
            order, rather than the response merely containing them.
        :returns: This builder.
        """
        self.data.choice_exact_match = choice_exact_match
        return self

    def add_choice(self, name: str, value: CommandAutoCompleteChoiceValueType) -> Self:
        """
        Adds a suggestion the response has to offer.

        :param name: The text rendered in the client.
        :param value: What gets submitted when it is picked.
        :returns: This builder.
        """
        self.data.choices.append(
            CommandAutoCompleteChoice(name=name, value=value))
        return self

    def compile(self) -> AutoCompleteAssertion:
        """
        :returns: The finished assertion.
        """
        return self.data
