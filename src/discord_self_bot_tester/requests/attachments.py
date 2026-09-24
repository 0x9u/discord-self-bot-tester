"""
Upload an attachment, as the logged in account.
"""

from ..bot import Bot

from ._base import Request, SelfBotRequestError

from aiohttp import ClientSession, FormData

from collections.abc import Buffer
import filetype
import json

# first param is channel_id
ATTACHMENT_URL = "https://discord.com/api/v9/channels/{}/attachments"

class Attachment(Request):
    """
    Upload an attachment. 
    """

    file: Buffer
    filename: str
    channel_id: str
    
    attachment_id: str | None = None
    attachment_filename: str | None = None
    
    async def request(self, bot: Bot, session: ClientSession):
        
        type_guess = filetype.guess(self.file)
        content_type = type_guess.mime if type_guess is not None else None
        
        data = FormData()
        data.add_field(
            "files[0]",
            self.file,
            content_type=content_type,
            filename=self.filename
        )
        data.add_field(
            "payload_json",
            value=json.dumps({
                "files" : [ {
                    "file_size" : memoryview(self.file).nbytes,
                    "filename" : self.filename
                }]
            })
        )
        
        res = await session.post(ATTACHMENT_URL.format(self.channel_id), data=data)
        if res.status != 200:
            res_data = await res.text()
            raise SelfBotRequestError("Request failed: " + str(res_data), res.status)
        else:
            res_data = await res.json()
            attachment: dict[str, str] = res_data["attachments"][0]
            self.attachment_id = attachment["id"]
            self.upload_filename = attachment["upload_filename"]
    
    def get_attachment_id(self) -> str:
        if self.attachment_id is None:
            raise AssertionError("Attachment ID not found. Please run the request first.")
        return self.attachment_id

    def get_upload_filename(self) -> str:
        if self.upload_filename is None:
            raise AssertionError("Upload Filename not found. Please run the request first.")
        return self.upload_filename

def build_attachment(file : Buffer, filename: str, channel_id: str) -> Attachment:
    return Attachment(file=file, filename=filename, channel_id=channel_id)
