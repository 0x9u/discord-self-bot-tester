from .message import Message
from .modal import Modal

from pydantic import BaseModel

from abc import ABC, abstractmethod
from typing import Literal, Any

# NOTE: ONLY HERE TO AVOID CIRCULAR IMPORT

class GatewayEvent(BaseModel):
    pass

class Filter(BaseModel, ABC):
    @abstractmethod
    def matches(self, user_id: str, data: dict[str, Any]) -> GatewayEvent | None:
        raise NotImplementedError

class MessageFilter(Filter):
    author_id: str | None
    channel_id: str | None
    nonce_id: str | None # only used if message_filter is None
    # used to check whether to set nonce_id or not, when message_filter is None this is default to True
    is_followup: bool = False

    interaction_is_from_author : bool = False
    
    message_payload_type : Literal["MESSAGE_CREATE", "MESSAGE_UPDATE"] = "MESSAGE_CREATE"

    def matches(self, user_id : str, data: dict[str, Any]) -> GatewayEvent | None:
        message_payload_type = data["t"]
        msg_data = data["d"]
        
        if self.author_id is not None and self.author_id != msg_data["author"]["id"]:
            return None
        if self.channel_id is not None and self.channel_id != msg_data["channel_id"]:
            return None
        if self.nonce_id is not None and self.nonce_id != msg_data["nonce"]:
            return None
        if self.interaction_is_from_author and \
            ("interaction_metadata" in data or \
                user_id != msg_data["interaction_metadata"]["user"]["id"]):
            return None
        if self.message_payload_type != message_payload_type:
            return None
        return Message.model_validate(msg_data)

class ModalFilter(Filter):
    nonce: str
    
    def matches(self, user_id : str, data: dict[str, Any]) -> bool:        
        modal_data = data["d"]
        if data["t"] == "INTERACTION_MODAL_CREATE" and self.nonce == modal_data["nonce"]:
            return Modal.model_validate(modal_data)
        else:
            return None

PROPERTIES = {  # please don't steal my data - oliver
    "os": "Windows",
    "browser": "Firefox",
    "device": "",
    "system_locale": "en-US",
    "has_client_mods": False,
    "browser_USER_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
    "browser_version": "150.0",
    "os_version": "10",
    "referrer": "https://www.google.com/",
    "referring_domain": "www.google.com",
    "search_engine": "google",
    "referrer_current": "",
    "referring_domain_current": "",
    "release_channel": "stable",
    "client_build_number": 546605,
    "client_event_source": None,
    "client_launch_id": "203c3bc2-e787-4df9-9c3c-39a0617c12e5",
    "is_fast_connect": True,
    "installation_id": "1472435156357877996.NPzylawn6sQb7uQQxXe6GKH_H4Q"
}

WEBSOCKET_URL = "wss://gateway.discord.gg/?encoding=json&v=9"