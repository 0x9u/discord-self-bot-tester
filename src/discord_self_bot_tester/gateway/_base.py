"""
The gateway types that both `ws` and the event modules need.

Kept in its own module purely to break the import cycle: `ws` imports the filters,
while each filter has to import the concrete event model it builds (done lazily,
inside `matches`).
"""

from pydantic import BaseModel

from abc import ABC, abstractmethod
from typing import Literal, Any

# NOTE: ONLY HERE TO AVOID CIRCULAR IMPORT

class GatewayEvent(BaseModel):
    """
    Base class for anything the gateway hands back to a test.

    Subclassed by the payload models (`Message`, `Modal`,
    `CommandAutoCompleteResponse`) and by `GatewayException`, which is queued in place
    of an event when the socket dies so a waiting assertion fails instead of hanging.
    """
    pass

class Filter(BaseModel, ABC):
    """
    Decides which gateway payload an assertion is waiting for.

    `Gateway` holds at most one filter at a time and offers it every dispatch it does
    not handle itself. The filter doubles as the parser: returning a `GatewayEvent`
    both claims the payload and produces the model, returning None lets it pass.
    """

    @abstractmethod
    def matches(self, user_id: str, data: dict[str, Any]) -> GatewayEvent | None:
        """
        The event built out of `data`, or None when this payload is not the one.

        `user_id` is the self-bot's own id, needed by filters that care who triggered
        the interaction behind the message. `data` is the whole dispatch envelope, so
        implementations read the event name off `data["t"]` and the body off
        `data["d"]`.
        """
        raise NotImplementedError

class MessageFilter(Filter):
    """
    Picks a message out of the gateway on whichever fields are set.

    Every field left None is simply not checked, so a filter with nothing set claims
    the next message of `message_payload_type` that arrives.
    """

    author_id: str | None
    channel_id: str | None
    nonce_id: str | None # only used if message_filter is None
    # used to check whether to set nonce_id or not, when message_filter is None this is default to True
    is_followup: bool = False

    interaction_is_from_author : bool = False
    
    message_flags: int | None
    
    message_payload_type : Literal["MESSAGE_CREATE", "MESSAGE_UPDATE"] = "MESSAGE_CREATE"

    def matches(self, user_id : str, data: dict[str, Any]) -> GatewayEvent | None:
        from .message import Message

        message_payload_type = data["t"]
        
        # checked first so unrelated gateway events don't get indexed as messages
        if self.message_payload_type != message_payload_type:
            return None
        
        msg_data = data["d"]
        
        if self.author_id is not None and self.author_id != msg_data["author"]["id"]:
            return None
        if self.channel_id is not None and self.channel_id != msg_data["channel_id"]:
            return None
        if self.nonce_id is not None and self.nonce_id != msg_data.get("nonce"):
            return None
        if self.interaction_is_from_author and \
            ("interaction_metadata" not in data or \
                user_id != msg_data["interaction_metadata"]["user"]["id"]):
            return None
        if self.message_flags is not None and self.message_flags != msg_data.get("flags", 0):
            return None
        return Message.model_validate(msg_data)

class ModalFilter(Filter):
    """
    Picks the modal discord opened in response to one particular interaction.

    Modals are only ever a reply to an interaction we sent, so the nonce we chose for
    that interaction is enough to identify it. `ModalAssertion.assert_request`
    overwrites `nonce` with the request's own just before sending.
    """

    nonce: str
    
    def matches(self, user_id : str, data: dict[str, Any]) -> GatewayEvent | None:
        from .modal import Modal

        modal_data = data["d"]
        if data["t"] == "INTERACTION_MODAL_CREATE" and self.nonce == modal_data["nonce"]:
            return Modal.model_validate(modal_data)
        else:
            return None
