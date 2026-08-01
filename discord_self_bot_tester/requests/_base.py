from ..bot import Bot

import aiohttp

from pydantic import BaseModel
from abc import abstractmethod, ABC

class Request(BaseModel, ABC):
    async def send(self, bot : Bot):
        headers = {"Authorization": bot.token,
                       "Content-Type": "application/json"}
        async with aiohttp.ClientSession(headers=headers) as session:
            await self.request(bot, session)
        
    @abstractmethod
    async def request(self, bot: Bot, session: aiohttp.ClientSession):
        raise NotImplementedError

class SelfBotRequestError(Exception):
    def __init__(self, message : str, code : int):
        self.message = message
        self.code = code
    
    def __repr__(self):
        return f"SelfBotRequestError: {self.message} (code : {self.code})"

class SelfBotRequestSetupError(Exception):
    def __init__(self, message : str):
        self.message = message
    
    def __repr__(self):
        return f"SelfBotRequestSetupError: {self.message}"