from pydantic import BaseModel

from abc import ABC, abstractmethod
from typing import Literal, Any

# NOTE: ONLY HERE TO AVOID CIRCULAR IMPORT

class GatewayEvent(BaseModel):
    """
    Base class for anything the gateway hands back to a test.
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
        
        `user_id` is the self-bot's own id
        `data` is the whole gateway event.
        https://docs.discord.com/developers/events/gateway
        """
        raise NotImplementedError

class MessageFilter(Filter):
    """
    Picks a message out of the gateway on whichever fields are set.

    Note that one can retrieve the next message received in the gateway if every field is left None.
    """

    author_id: str | None
    channel_id: str | None
    # only used if message_filter is None
    nonce_id: str | None
    # used to check whether to set nonce_id or not, when message_filter is None this is default to True
    is_followup: bool = False

    interaction_is_from_author : bool = False
    
    message_flags: int | None
    
    message_payload_type : Literal["MESSAGE_CREATE", "MESSAGE_UPDATE"] = "MESSAGE_CREATE"

    def matches(self, user_id : str, data: dict[str, Any]) -> GatewayEvent | None:
        from .message import Message

        message_payload_type : str = data["t"]
        
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
    """    
    nonce: str
    
    def matches(self, user_id : str, data: dict[str, Any]) -> GatewayEvent | None:
        from .modal import Modal

        modal_data = data["d"]
        if data["t"] == "INTERACTION_MODAL_CREATE" and self.nonce == modal_data["nonce"]:
            return Modal.model_validate(modal_data)
        else:
            return None
