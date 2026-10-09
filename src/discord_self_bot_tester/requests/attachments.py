from ..bot import Bot

from ._base import Request, _check_status

from aiohttp import ClientSession, FormData
from pydantic import ConfigDict

from collections.abc import Buffer
import filetype
import json

# first param is channel_id
ATTACHMENT_URL = "https://discord.com/api/v9/channels/{}/attachments"

class Attachment(Request):
    """
    Uploads a file to a channel's attachment storage, without posting it.

    The resulting id is what a modal's file upload expects, see
    :meth:`ModalResponseBuilder.set_values <discord_self_bot_tester.requests.modal.ModalResponseBuilder.set_values>`.

    :ivar file: The file's contents.
    :ivar filename: The name to upload the file as.
    :ivar channel_id: The channel to upload into.
    :ivar attachment_id: Set by discord once the request has been sent.
    :ivar upload_filename: Set by discord once the request has been sent.
    """

    # pydantic has no schema for Buffer, this makes it fall back to an isinstance check
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file: Buffer
    filename: str
    channel_id: str
    
    attachment_id: str | None = None
    upload_filename: str | None = None
    
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
        await _check_status(res, 200)

        res_data = await res.json()
        attachment: dict[str, str] = res_data["attachments"][0]
        self.attachment_id = attachment["id"]
        self.upload_filename = attachment["upload_filename"]
    
    def get_attachment_id(self) -> str:
        """
        :returns: The id discord gave the uploaded file.
        :raises AssertionError: If the request has not been sent yet.
        """
        if self.attachment_id is None:
            raise AssertionError("Attachment ID not found. Please run the request first.")
        return self.attachment_id

    def get_upload_filename(self) -> str:
        """
        :returns: The filename discord stored the uploaded file under.
        :raises AssertionError: If the request has not been sent yet.
        """
        if self.upload_filename is None:
            raise AssertionError("Upload Filename not found. Please run the request first.")
        return self.upload_filename

def build_attachment(file : Buffer, filename: str, channel_id: str) -> Attachment:
    """
    Builds an :class:`Attachment` upload.

    :param file: The file's contents.
    :param filename: The name to upload the file as.
    :param channel_id: The channel to upload into.
    :returns: The request, ready to send.
    """
    return Attachment(file=file, filename=filename, channel_id=channel_id)
