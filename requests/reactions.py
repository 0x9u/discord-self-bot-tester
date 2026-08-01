from ._base import Request, SelfBotRequestError

from aiohttp import ClientSession

from discordselftests.bot import Bot

from urllib.parse import quote

# first param is channel_id, second is message_id, third is emoji (urlencoded)
REACTION_URL = "https://discord.com/api/v9/channels/{}/messages/{}/reactions/{}/@me"

class Reaction(Request):
    emoji: str
    message_id: str
    channel_id: str
    
    async def request(self, bot: Bot, session: ClientSession):
        res = await session.put(REACTION_URL.format(self.channel_id, self.message_id, quote(self.emoji)))
        if res.status != 204:
            res_data = await res.text()
            raise SelfBotRequestError("Request failed: " + str(res_data), res.status)

def build_reaction(emoji: str, message_id: int, channel_id: int) -> Reaction:
    return Reaction(emoji=emoji, message_id=str(message_id), channel_id=str(channel_id))