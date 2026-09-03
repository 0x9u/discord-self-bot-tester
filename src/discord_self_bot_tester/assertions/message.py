from ..bot import Bot

from ..gateway._base import MessageFilter
from ..gateway.message import Message
from ..requests._base import Request
from ..requests.commands import Interaction

from ._base import Assertion

from typing import Optional, Self, List
import re

class MessageAssertion(Assertion[Message]):
    # what to distingish the message from
    # if None, it will pick the next message in the websocket, or if
    # the request is a app command, it will pick the message replying to the command.
    message_filter: Optional[MessageFilter]

    # if no assert conditions are set, it will just assert the next message being sent next that matches these filters

    content_search_pattern: Optional[str]
    mentions: Optional[List[str]]  # list of user ids
    mention_roles: Optional[List[str]]
    
    def _check(self, gateway_event: Message):
        content_search_pattern = self.content_search_pattern

        if content_search_pattern is not None and re.match(content_search_pattern, gateway_event.content) is None:
            raise AssertionError(
                f"Mismatch\nGot: {gateway_event.content}\nMust match: {content_search_pattern}")

        if self.mentions is not None and gateway_event.mentions != self.mentions:
            raise AssertionError(
                f"Mismatch\nGot: {gateway_event.mentions}\nMust match: {self.mentions}")

        if self.mention_roles is not None and gateway_event.mention_roles != self.mention_roles:
            raise AssertionError(
                f"Mismatch\nGot: {gateway_event.mention_roles}\nMust match: {self.mention_roles}")
    
    async def assert_request(self, bot : Bot, req : Request, deadline: int = 5) -> Message:
        if self.message_filter is None:
            self.message_filter = MessageFilter(
                author_id=None,
                channel_id=None,
                nonce_id=req.nonce if isinstance(
                    req, Interaction) else None
            )
        elif self.message_filter.is_followup and isinstance(req, Interaction):
            self.message_filter.nonce_id = req.nonce
        
        bot._gateway._assert_msg = self.message_filter
        
        await req.send(bot)
        
        gateway_event = await bot.get_next_gateway_event(deadline)
        
        if not isinstance(gateway_event, Message):
            raise TypeError("Expected message, got: " +
                                type(gateway_event).__name__)
                
        self._check(gateway_event)
        
        return gateway_event

    async def assert_gateway(self, bot : Bot, deadline: int = 5) -> Message:
        if self.message_filter is None:
            raise TypeError("MessageAssertion must have a message_filter for assert_gateway")
        
        bot._gateway._assert_msg = self.message_filter
        
        gateway_event = await bot.get_next_gateway_event(deadline)
        
        if not isinstance(gateway_event, Message):
            raise TypeError("Expected message, got: " +
                                type(gateway_event).__name__)
                
        self._check(gateway_event)
        
        return gateway_event

class MessageAssertionBuilder:
    data: MessageAssertion

    def __init__(self):
        self.data = MessageAssertion(
            message_filter=None, content_search_pattern=None, mentions=None, mention_roles=None)

    def filter_by_author(self, author_id: int) -> Self:
        if self.data.message_filter is None:
            self.data.message_filter = MessageFilter(
                author_id=str(author_id), channel_id=None, nonce_id=None)
            return self

        self.data.message_filter.author_id = str(author_id)
        return self

    def filter_by_channel(self, channel_id: int) -> Self:
        if self.data.message_filter is None:
            self.data.message_filter = MessageFilter(
                author_id=None, channel_id=str(channel_id), nonce_id=None)
            return self

        self.data.message_filter.channel_id = str(channel_id)
        return self

    def filter_by_interaction_from_author(self) -> Self:
        if self.data.message_filter is None:
            self.data.message_filter = MessageFilter(
                author_id=None, channel_id=None, nonce_id=None)
        self.data.message_filter.interaction_is_from_author = True
        return self

    
    # NOTE: use this if the command is deferred
    def filter_by_message_update(self) -> Self:
        if self.data.message_filter is None:
            self.data.message_filter = MessageFilter(
                author_id=None, channel_id=None, nonce_id=None)
        self.data.message_filter.message_payload_type = "MESSAGE_UPDATE"
        return self

    def filter_by_followup_message(self) -> Self:
        if self.data.message_filter is None:
            self.data.message_filter = MessageFilter(
                author_id=None, channel_id=None, nonce_id=None)
        self.data.message_filter.is_followup = True
        return self

    def assert_by_message_content(self, pattern: str) -> Self:
        self.data.content_search_pattern = pattern
        return self

    def assert_by_mentions(self, mentions: List[int]) -> Self:
        self.data.mentions = list(map(str, mentions))
        return self

    def assert_by_mention_roles(self, mention_roles: List[int]) -> Self:
        self.data.mention_roles = list(map(str, mention_roles))
        return self

    def compile(self) -> MessageAssertion:
        return self.data