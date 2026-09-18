"""
The `Request` contract and the errors requests raise.
"""

from ..bot import Bot

import aiohttp

from pydantic import BaseModel
from abc import abstractmethod, ABC

class Request(BaseModel, ABC):
    """
    Something that can be sent to discord as the account the bot is logged in as.

    Subclasses implement `request` and inherit `send`, which supplies the authorised
    session. Every request is a pydantic model so that it can be built up, inspected
    and dumped straight to JSON.
    """

    async def send(self, bot : Bot):
        """
        Sends this request on its own session, authorised as `bot`.

        Prefer handing the request to an assertion instead when a reply is expected:
        sending here first would race the gateway filter being installed.
        """
        headers = {"Authorization": bot.token,
                       "Content-Type": "application/json"}
        async with aiohttp.ClientSession(headers=headers) as session:
            await self.request(bot, session)
        
    @abstractmethod
    async def request(self, bot: Bot, session: aiohttp.ClientSession):
        """
        Performs the actual call on an already authorised `session`.

        Expected to raise `SelfBotRequestError` when discord rejects it.
        """
        raise NotImplementedError

class SelfBotRequestError(Exception):
    """
    Discord refused the request. `code` is the HTTP status it answered with.
    """

    def __init__(self, message : str, code : int):
        self.message = message
        self.code = code
    
    def __repr__(self):
        return f"SelfBotRequestError: {self.message} (code : {self.code})"

class SelfBotRequestSetupError(Exception):
    """
    The request could not be built from what the bot knows yet.

    Raised before anything is sent - typically because the application's commands were
    never indexed, so the command id and version are unavailable.
    """

    def __init__(self, message : str):
        self.message = message
    
    def __repr__(self):
        return f"SelfBotRequestSetupError: {self.message}"