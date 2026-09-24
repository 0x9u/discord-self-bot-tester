"""
Expectations about a modal an interaction opens.

Modals only ever arrive in response to an interaction we sent, so there is nothing to
filter on beyond that interaction's nonce, which `assert_request` fills in itself.
"""

from ..bot import Bot

from ..gateway.modal import Modal
from ..gateway._base import ModalFilter
from ..requests.commands import Interaction

from ._base import Assertion

from typing import Self
import re

class ModalAssertion(Assertion[Interaction, Modal]):
    """
    Waits for the modal an interaction opens. Build one with `ModalAssertionBuilder`.
    """

    modal_filter: ModalFilter | None
    
    title_search_pattern: str | None

    def _check(self, gateway_event: Modal):
        title_search_pattern = self.title_search_pattern
        
        if title_search_pattern is not None and re.match(title_search_pattern, gateway_event.title) is None:
            raise AssertionError(
                f"Mismatch\nGot: {gateway_event.title}\nMust match: {title_search_pattern}")

    
    async def assert_request(self, bot: Bot, req: Interaction, deadline: int = 5) -> Modal:
        if self.modal_filter is None:
            self.modal_filter = ModalFilter(
                nonce = req.nonce
            )
        else:
            self.modal_filter.nonce = req.nonce
        
        bot._gateway._assert_filter = self.modal_filter
        
        await req.send(bot)
        
        gateway_event = await bot.get_next_gateway_event(deadline)
        
        if not isinstance(gateway_event, Modal):
            raise TypeError("Expected message, got: " +
                                type(gateway_event).__name__)
                
        self._check(gateway_event)
        
        return gateway_event

    async def assert_gateway(self, bot : Bot, deadline: int = 5) -> Modal:
        """
        Redundant method, modals have to be triggered by an interaction to occur.
        """
        raise NotImplementedError

class ModalAssertionBuilder:
    """
    Assembles a `ModalAssertion`.

    modal = await ModalAssertionBuilder()\
        .assert_by_modal_title("Register.*")\
        .compile().assert_request(bot, press_button(msg, "Sign up"))
    """

    # nonce in assertion is to be overwritten by `assert_request`
    data: ModalAssertion

    def __init__(self):
        self.data = ModalAssertion(
            modal_filter=ModalFilter(nonce=""),
            title_search_pattern=None,
        )

    def assert_by_modal_title(self, pattern: str) -> Self:
        """
        The title has to match this regex, anchored at the start (`re.match`).
        """
        self.data.title_search_pattern = pattern
        return self

    def compile(self) -> ModalAssertion:
        """
        The finished assertion.
        """
        return self.data
