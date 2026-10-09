from ..bot import Bot

from ..gateway.modal import Modal
from ..gateway._base import ModalFilter
from ..requests.commands import Interaction

from ._base import Assertion

from typing import Self
import re

class ModalAssertion(Assertion[Interaction, Modal]):
    """
    Waits for the modal an interaction opens. Build one with
    :class:`ModalAssertionBuilder`.

    :ivar title_search_pattern: A regex the modal's title has to match.
    """

    title_search_pattern: str | None

    def _check(self, gateway_event: Modal):
        title_search_pattern = self.title_search_pattern
        
        if title_search_pattern is not None and re.match(title_search_pattern, gateway_event.title) is None:
            raise AssertionError(
                f"Mismatch\nGot: {gateway_event.title}\nMust match: {title_search_pattern}")

    
    async def assert_request(self, bot: Bot, req: Interaction, deadline: int = 5) -> Modal:
        bot._gateway._assert_filter = ModalFilter(nonce=req.nonce)

        await req.send(bot)

        gateway_event = await bot.get_next_gateway_event(deadline)

        if not isinstance(gateway_event, Modal):
            raise TypeError("Expected modal, got: " +
                                type(gateway_event).__name__)
                
        self._check(gateway_event)
        
        return gateway_event

    async def assert_gateway(self, bot : Bot, deadline: int = 5) -> Modal:
        """
        Not supported: a modal only ever opens in response to an interaction, so use
        :meth:`assert_request`.

        :raises NotImplementedError: Always.
        """
        raise NotImplementedError

class ModalAssertionBuilder:
    """
    Assembles a :class:`ModalAssertion`. Example::

        modal = await ModalAssertionBuilder()\\
            .assert_by_modal_title("Register.*")\\
            .compile().assert_request(bot, press_button(msg, "Sign up"))
    """

    data: ModalAssertion

    def __init__(self):
        self.data = ModalAssertion(title_search_pattern=None)

    def assert_by_modal_title(self, pattern: str) -> Self:
        """
        :param pattern: A regex the title has to match, anchored at the start
            (:func:`re.match`).
        :returns: This builder.
        """
        self.data.title_search_pattern = pattern
        return self

    def compile(self) -> ModalAssertion:
        """
        :returns: The finished assertion.
        """
        return self.data
