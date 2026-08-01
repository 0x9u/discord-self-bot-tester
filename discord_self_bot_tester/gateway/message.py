from ._base import GatewayEvent

from typing import List

class Message(GatewayEvent):
    id: str
    channel_id: str
    content: str
    mentions: List[str]
    mention_roles: List[str]