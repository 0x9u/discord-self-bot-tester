from ..requests._base import Request
from ..gateway._base import GatewayEvent
from ..bot import Bot

from pydantic import BaseModel
from abc import abstractmethod, ABC
from typing import Generic, TypeVar

E = TypeVar('E', bound=GatewayEvent)

class Assertion(BaseModel, Generic[E], ABC):
    @abstractmethod
    def _check(self, gateway_event: E):
        raise NotImplementedError
    @abstractmethod
    async def assert_request(self, bot : Bot, req : Request, deadline: int = 5) -> E:
        raise NotImplementedError
    @abstractmethod
    async def assert_gateway(self, bot : Bot, deadline: int = 5) -> E:
        raise NotImplementedError