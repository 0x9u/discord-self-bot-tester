from ..bot import Bot

import aiohttp

from pydantic import BaseModel
from abc import abstractmethod, ABC

class Request(BaseModel, ABC):
    """
    Something that can be sent to discord as the account the bot is logged in as.

    Subclasses implement :meth:`request` and inherit :meth:`send`, which supplies the authorised
    session. Every request is a pydantic model so that it can be built up, inspected
    and dumped straight to JSON.
    """

    async def send(self, bot : Bot):
        """
        Sends this request on its own session.

        Prefer handing the request to an assertion instead when a reply is expected:
        sending here first would race the gateway filter being installed.

        :param bot: The account to send it as.
        :raises SelfBotRequestError: If discord rejects it.
        """
        headers = {"Authorization": bot.token,
                       "Content-Type": "application/json"}
        async with aiohttp.ClientSession(headers=headers) as session:
            await self.request(bot, session)
        
    @abstractmethod
    async def request(self, bot: Bot, session: aiohttp.ClientSession):
        """
        Performs the actual call.

        :param bot: The account it is sent as.
        :param session: A session already authorised as ``bot``.
        :raises SelfBotRequestError: Expected when discord rejects it.
        """
        raise NotImplementedError

class SelfBotRequestError(Exception):
    """
    Discord refused the request.

    :ivar message: What went wrong, including discord's response body.
    :ivar code: The HTTP status discord answered with.
    """

    def __init__(self, message : str, code : int):
        super().__init__(f"{message} (code: {code})")
        self.message = message
        self.code = code

async def _check_status(res: aiohttp.ClientResponse, expected: int):
    """
    Checks a response came back with the status discord sends on success.

    :param res: The response to check.
    :param expected: The status it should have.
    :raises SelfBotRequestError: Carrying discord's response body, if the status differs.
    """
    if res.status != expected:
        raise SelfBotRequestError("Request failed: " + await res.text(), res.status)

class SelfBotRequestSetupError(Exception):
    """
    The request could not be built from what the bot knows yet.

    Raised before anything is sent - typically because the application's commands were
    never indexed, so the command id and version are unavailable.
    """

    def __init__(self, message : str):
        super().__init__(message)
        self.message = message