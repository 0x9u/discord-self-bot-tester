from aiohttp import ClientSession

from discordselftests.bot import Bot

from ._base import Request, SelfBotRequestError, SelfBotRequestSetupError

from pydantic import BaseModel, ConfigDict
import random
from enum import Enum
from typing import TypeAlias, Optional, List

INTERACTIONS_URL = "https://discord.com/api/v9/interactions"
ACK_URL = "https://discord.com/api/v9/channels/{}/messages/{}/ack"

ACK_BODY = {"token": None, "last_viewed": 4158}


class ApplicationCommandType(Enum):
    CHAT_INPUT = 1
    USER = 2
    MESSAGE = 3
    PRIMARY_ENTRY_POINT = 4


class InteractionType(Enum):
    APP_COMMAND = 2
    MESSAGE_COMPONENT = 3
    APPLICATION_COMMAND_AUTOCOMPLETE = 4

ApplicationCommandArgValueType : TypeAlias = bool | int | float | str

class ApplicationCommand(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    type: ApplicationCommandType
    name: str
    options: Optional[List["ApplicationCommand"]] = None
    value: Optional[ApplicationCommandArgValueType] = None
    id : Optional[str] = None
    version: Optional[str] = None
    focused: Optional[bool] = None

class Interaction(Request):
    type: InteractionType
    application_id: str
    guild_id: str
    channel_id: str
    nonce: str
    data: ApplicationCommand
    session_id : Optional[str] = None
    
    async def request(self, bot: Bot, session: ClientSession):
        app_commands = bot._command_version.get(self.application_id)
        
        if app_commands is None:
            raise  SelfBotRequestSetupError(
                f"No application commands associated with application id {self.application_id}, hint: try running index_application_commands")
        command_data = app_commands.get(self.data.name)
        if command_data is None:
                raise SelfBotRequestSetupError(
                    f"No command with name {self.data.name} associated with application id {self.application_id}")
         
        command_id, command_version = command_data
        
        self.data.version = command_version
        self.data.id = command_id
        self.session_id = bot.session_id        
        json = self.model_dump(mode="json", exclude_none=True)
         
        res = await session.post(INTERACTIONS_URL, json=json)
        if res.status != 204:
            res_data = await res.text()
            raise SelfBotRequestError("Request failed: " + str(res_data), res.status)

        res = await session.post(ACK_URL.format(self.channel_id, self.nonce), json=ACK_BODY)
        if res.status != 200:
            res_data = await res.text()
            raise SelfBotRequestError("Request failed: " + str(res_data), res.status)

class ApplicationCommandBuilder:
    Self: TypeAlias = 'ApplicationCommandBuilder'

    data: ApplicationCommand
    main_command: ApplicationCommand

    def __init__(self, name: str):
        self.data = ApplicationCommand(type=ApplicationCommandType.CHAT_INPUT, name=name, options=None, value=None, version=None)
        self.main_command = self.data

    def set_main_command(self, name: str) -> Self:
        self.main_command = ApplicationCommand(
            type=ApplicationCommandType.CHAT_INPUT, name=name, options=None, value=None)
        self.data.options = [self.main_command]
        return self

    def set_arg(self, name: str, value: ApplicationCommandArgValueType, focused: Optional[bool] = None) -> Self:
        if self.main_command.options is None:
            self.main_command.options = []

        self.main_command.options.append(ApplicationCommand(
            type=ApplicationCommandType.MESSAGE,
            name=name,
            options=[],
            value=value,
            focused=focused
        ))

        return self

    def compile(self) -> ApplicationCommand:
        return self.data


def build_interaction(type: InteractionType, application_id: int, guild_id: int, channel_id: int, data: ApplicationCommand) -> Interaction:
    return Interaction(
        type=type,
        application_id=str(application_id),
        guild_id=str(guild_id),
        channel_id=str(channel_id),
        nonce=str(random.randint(
            100_000_000_000_000_0000, 900_000_000_000_000_0000)),
        data=data)