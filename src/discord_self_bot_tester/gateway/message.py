from ._base import GatewayEvent
from .component import Component

from pydantic import BaseModel

class MessageAuthor(BaseModel):
    """
    Who sent a message, as message payloads describe them.
    
    NOTE: `User` is not used for author in `Message` since it carries a smaller payload.
    """

    id: str
    username: str | None = None
    bot: bool | None = None

class Message(GatewayEvent):
    """
    A message as it arrived over the gateway.
    """

    id: str
    channel_id: str
    guild_id: str | None = None
    author: MessageAuthor | None = None
    # only sent on messages discord's own interactions produced
    application_id: str | None = None
    flags: int | None = None
    content: str = ""
    mentions: list[MessageAuthor] = []
    mention_roles: list[str] = []
    # `components` is the message's view, and is what `..requests.component` reads to
    # build a button press or a dropdown selection out of it.
    components: list[Component] | None = None