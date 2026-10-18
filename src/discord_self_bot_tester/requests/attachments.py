from ..bot import Bot

from ._base import Request, SelfBotRequestError

from aiohttp import ClientSession, FormData

import json

# first param is channel_id
ATTACHMENT_URL = "https://discord.com/api/v9/channels/{}/attachments"

class Attachment(Request):
    """
    Upload an attachment. 
    """

    file: bytes
    filename: str
    channel_id: str
    
    attachment_id: str | None = None
    upload_filename: str | None = None
    
    async def request(self, bot: Bot, session: ClientSession):
        data = FormData()
        data.add_field("files[0]", self.file, filename=self.filename)
        data.add_field(
            "payload_json",
            value=json.dumps({
                "files" : [ {
                    "file_size" : len(self.file),
                    "filename" : self.filename
                }]
            })
        )
        
        res = await session.post(ATTACHMENT_URL.format(self.channel_id), data=data)
        if res.status != 200:
            res_data = await res.text()
            raise SelfBotRequestError("Request failed: " + str(res_data), res.status)

        attachment = (await res.json())["attachments"][0]
        self.attachment_id = attachment["id"]
        self.upload_filename = attachment["upload_filename"]
    
    def get_attachment_id(self) -> str:
        if self.attachment_id is None:
            raise AssertionError("Attachment ID not found. Please run the request first.")
        return self.attachment_id

def build_attachment(file: bytes, filename: str, channel_id: int) -> Attachment:
    return Attachment(file=file, filename=filename, channel_id=str(channel_id))
