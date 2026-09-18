"""
The `Assertion` contract, generic over the request sent and the event expected.
"""

from ..requests._base import Request
from ..gateway._base import GatewayEvent
from ..bot import Bot

from pydantic import BaseModel
from abc import abstractmethod, ABC
from typing import Generic, TypeVar

R = TypeVar('R', bound=Request)
E = TypeVar('E', bound=GatewayEvent)

class Assertion(BaseModel, Generic[R, E], ABC):
    """
    An expectation about the event a request produces.

    `R` is the request type it can be used with and `E` the event it returns, so a
    satisfied assertion hands back the parsed payload for a test to carry on with.
    """

    @abstractmethod
    def _check(self, gateway_event: E):
        """
        Raises `AssertionError` if the matched event fails the expectations.

        Separate from the filtering: by the time this runs the event has already been
        claimed as the right one, so anything wrong here is a real failure rather than
        a reason to keep waiting.
        """
        raise NotImplementedError

    @abstractmethod
    async def assert_request(self, bot : Bot, req : R, deadline: int = 5) -> E:
        """
        Installs the filter, sends `req`, and returns the event it produced.

        Raises `TimeoutError` if nothing matched within `deadline` seconds.
        """
        raise NotImplementedError

    @abstractmethod
    async def assert_gateway(self, bot : Bot, deadline: int = 5) -> E:
        """
        Waits for a matching event without sending anything.

        For the follow-ups of an exchange already set off by an earlier request.
        """
        raise NotImplementedError