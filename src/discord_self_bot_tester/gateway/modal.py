from ._base import GatewayEvent
from .component import Component

from pydantic import Field

from typing import Annotated

class Modal(GatewayEvent):
    id: str
    nonce: str
    custom_id: str
    title: str
    components: list[Component] = list[Annotated[Component, Field(discriminator="type")]]