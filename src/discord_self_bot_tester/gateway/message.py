from ._base import GatewayEvent
from .component import Component

from pydantic import BaseModel

# not ..shared.User, message payloads carry a trimmed down author object
class MessageAuthor(BaseModel):
    id: str
    username: str | None = None
    bot: bool | None = None

class Message(GatewayEvent):
    id: str
    channel_id: str
    guild_id: str | None = None
    author: MessageAuthor | None = None
    # only sent on messages discord's own interactions produced
    application_id: str | None = None
    flags: int | None = None
    content: str
    mentions: list[str]
    mention_roles: list[str]
    components: list[Component] | None = None