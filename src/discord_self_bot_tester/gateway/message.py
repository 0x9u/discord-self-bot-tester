from ._base import GatewayEvent
from .component import Component

class Message(GatewayEvent):
    id: str
    channel_id: str
    content: str
    mentions: list[str]
    mention_roles: list[str]
    components: list[Component] | None = None