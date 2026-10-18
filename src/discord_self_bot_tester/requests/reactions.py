from ..bot import Bot

from ._base import Request, _check_status

from aiohttp import ClientSession

from urllib.parse import quote

# first param is channel_id, second is message_id, third is emoji (urlencoded)
REACTION_URL = "https://discord.com/api/v9/channels/{}/messages/{}/reactions/{}/@me"

class Reaction(Request):
    """
    Reacts to a message with a single emoji.

    :ivar emoji: The literal character for a unicode emoji, or ``name:id`` for a custom
        one. It is url-encoded on the way out.
    :ivar message_id: The message to react to.
    :ivar channel_id: The channel the message is in.
    """

    emoji: str
    message_id: str
    channel_id: str
    
    async def request(self, bot: Bot, session: ClientSession):
        res = await session.put(REACTION_URL.format(self.channel_id, self.message_id, quote(self.emoji)))
        await _check_status(res, 204)

def build_reaction(emoji: str, message_id: int, channel_id: int) -> Reaction:
    """
    Builds a :class:`Reaction`, taking the ids as the ints they are read as everywhere else.

    :param emoji: The literal character for a unicode emoji, or ``name:id`` for a
        custom one.
    :param message_id: The message to react to.
    :param channel_id: The channel the message is in.
    :returns: The request, ready to send.
    """
    return Reaction(emoji=emoji, message_id=str(message_id), channel_id=str(channel_id))