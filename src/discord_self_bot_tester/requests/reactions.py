"""
Adding a reaction to an existing message, as the logged in account.
"""

from ..bot import Bot

from ._base import Request, SelfBotRequestError

from aiohttp import ClientSession

from urllib.parse import quote

# first param is channel_id, second is message_id, third is emoji (urlencoded)
REACTION_URL = "https://discord.com/api/v9/channels/{}/messages/{}/reactions/{}/@me"

class Reaction(Request):
    """
    Reacts to a message with a single emoji.

    `emoji` is the literal character for a unicode emoji, or `name:id` for a custom
    one; it is url-encoded on the way out.
    """

    emoji: str
    message_id: str
    channel_id: str
    
    async def request(self, bot: Bot, session: ClientSession):
        res = await session.put(REACTION_URL.format(self.channel_id, self.message_id, quote(self.emoji)))
        if res.status != 204:
            res_data = await res.text()
            raise SelfBotRequestError("Request failed: " + str(res_data), res.status)

def build_reaction(emoji: str, message_id: int, channel_id: int) -> Reaction:
    """
    A `Reaction`, taking the ids as the ints they are read as everywhere else.
    """
    return Reaction(emoji=emoji, message_id=str(message_id), channel_id=str(channel_id))