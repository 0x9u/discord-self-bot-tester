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

    ``R`` is the request type it can be used with and ``E`` the event it returns, so a
    satisfied assertion hands back the parsed payload for a test to carry on with.
    """

    @abstractmethod
    def _check(self, gateway_event: E):
        """
        Checks the matched event against every expectation.

        This is separate from filtering: the filter picks which event to look at, this
        checks that event meets all the asserted conditions.

        :param gateway_event: The event the filter matched.
        :raises AssertionError: If it fails an expectation.
        """
        raise NotImplementedError

    @abstractmethod
    async def assert_request(self, bot : Bot, req : R, deadline: int = 5) -> E:
        """
        Installs the filter, sends the request, and checks the event it produced.

        :param bot: The account to send the request as.
        :param req: The request expected to produce the event.
        :param deadline: How many seconds to wait for the event.
        :returns: The event, for the test to carry on with.
        :raises AssertionError: If the event fails an expectation.
        :raises TimeoutError: If nothing matched in time.
        """
        raise NotImplementedError

    @abstractmethod
    async def assert_gateway(self, bot : Bot, deadline: int = 5) -> E:
        """
        Waits for a matching event without sending anything.

        For the follow-ups of an exchange already set off by an earlier request.

        :param bot: The account listening for the event.
        :param deadline: How many seconds to wait for the event.
        :returns: The event, for the test to carry on with.
        :raises AssertionError: If the event fails an expectation.
        :raises TimeoutError: If nothing matched in time.
        """
        raise NotImplementedError
