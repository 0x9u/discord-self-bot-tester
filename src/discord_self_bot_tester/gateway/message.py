"""
The slice of discord's MESSAGE_CREATE / MESSAGE_UPDATE payload the assertions read.

Deliberately partial: only the fields a test asserts on are modelled, and the rest of
the payload is ignored.
"""

from ._base import GatewayEvent
from .component import Component

from pydantic import BaseModel

# not ..shared.User, message payloads carry a trimmed down author object
class MessageAuthor(BaseModel):
    """
    Who sent a message, as message payloads describe them.

    Far smaller than `..shared.User`: only the fields the filters and assertions
    actually read are modelled.
    """

    id: str
    username: str | None = None
    bot: bool | None = None

class Message(GatewayEvent):
    """
    A message as it arrived over the gateway.

    `components` is the message's view, and is what `..requests.component` reads to
    build a button press or a dropdown selection out of it - which is why a message
    handed back by an assertion is enough on its own to interact with, with no ids to
    pass by hand.
    """

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