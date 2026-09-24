"""
Upload an attachment, as the logged in account.
"""

from ..bot import Bot

from ._base import Request, SelfBotRequestError

from aiohttp import ClientSession

from urllib.parse import quote
from collections.abc import Buffer
import os

# first param is channel_id (urlencoded)
ATTACHMENT_URL = "https://discord.com/api/v9/channels/{}/attachments"

class Attachment(Request):
    """
    Upload an attachment. 
    """

    file: Buffer
    filename: str
    channel_id: str
    # TODO: get the file id somehow
    async def request(self, bot: Bot, session: ClientSession):
        
        res = await session.post(ATTACHMENT_URL.format(self.channel_id),
                                 json={
                                     "files" : [ {
                                         "file_size" : len(self.file),
                                         "filename" : self.filename
                                     }]
                                 })
        if res.status != 204:
            res_data = await res.text()
            raise SelfBotRequestError("Request failed: " + str(res_data), res.status)

