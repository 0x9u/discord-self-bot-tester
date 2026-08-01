from pydantic import BaseModel

from typing import Optional, Literal, Any

# NOTE: ONLY HERE TO AVOID CIRCULAR IMPORT

class GatewayEvent(BaseModel):
    pass

class MessageFilter(BaseModel):
    author_id: Optional[str]
    channel_id: Optional[str]
    nonce_id: Optional[str]  # only used if message_filter is None
    # used to check whether to set nonce_id or not, when message_filter is None this is default to True
    is_followup: bool = False

    interaction_is_from_author : bool = False
    
    message_payload_type : Literal["MESSAGE_CREATE", "MESSAGE_UPDATE"] = "MESSAGE_CREATE"

    def matches(self, user_id : str, message_payload_type: str, data: dict[str, Any]) -> bool:
        if self.author_id is not None and self.author_id != data["author"]["id"]:
            return False
        if self.channel_id is not None and self.channel_id != data["channel_id"]:
            return False
        if self.nonce_id is not None and self.nonce_id != data["nonce"]:
            return False
        if self.interaction_is_from_author and \
            ("interaction_metadata" in data or \
                user_id != data["interaction_metadata"]["user"]["id"]):
            return False
        if self.message_payload_type != message_payload_type:
            return False
        return True

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