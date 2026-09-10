from ..bot import Bot

from ._base import Request, SelfBotRequestError, SelfBotRequestSetupError

from aiohttp import ClientSession
from pydantic import BaseModel, ConfigDict
import random
import asyncio
from enum import Enum
from typing import TypeAlias, Literal

INTERACTION_TIMEOUT = 5000

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
    options: list["ApplicationCommand"] | None = None
    value: ApplicationCommandArgValueType | None = None
    id : str | None = None
    version: str | None = None
    focused: bool | None = None

class ComponentType(Enum):
	BUTTON = 2
	STRING_SELECT = 3
	TEXT_INPUT = 4
	USER_SELECT = 5
	ROLE_SELECT = 6
	MENTIONABLE_SELECT = 7
	CHANNEL_SELECT = 8
	FILE_UPLOAD = 19
	RADIO_GROUP = 21
	CHECKBOX_GROUP = 22
	CHECKBOX = 23


class MessageComponent(BaseModel):
	custom_id: str
	component_type: ComponentType
	values: list[str]

InteractionDataType : TypeAlias = ApplicationCommand | MessageComponent

class InteractionFailed(Exception):
    pass

class Interaction(Request):
    type: InteractionType
    application_id: str
    guild_id: str
    channel_id: str
    nonce: str
    data: InteractionDataType
    session_id: str | None = None
    
    async def request(self, bot: Bot, session: ClientSession):
        # dispatch depending on type
        
        if self.type == Interaction.APP_COMMAND or self.type == InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE:
            await self._prepare_app_command(bot, session)
         
        json = self.model_dump(mode="json", exclude_none=True)
         
        res = await session.post(INTERACTIONS_URL, json=json)
        if res.status != 204:
            res_data = await res.text()
            raise SelfBotRequestError("Request failed: " + str(res_data), res.status)

        res = await session.post(ACK_URL.format(self.channel_id, self.nonce), json=ACK_BODY)
        if res.status != 200:
            res_data = await res.text()
            raise SelfBotRequestError("Request failed: " + str(res_data), res.status)

        await asyncio.wait_for(asyncio.shield(bot._gateway._interaction_status_events[self.nonce].wait()), timeout=INTERACTION_TIMEOUT)
        
        del bot._gateway._interaction_status_events[self.nonce]
        status = bot._gateway._interaction_status_data.pop(self.nonce)
        
        if not status:
            raise InteractionFailed
    
    async def _prepare_app_command(self, bot: Bot, session: ClientSession):
        assert isinstance(self.data, ApplicationCommand)
         
        app_commands = bot._command_version.get(self.application_id)
        
        if app_commands is None:
            raise SelfBotRequestSetupError(
                f"No application commands associated with application id {self.application_id}, hint: try running index_application_commands")
        command_data = app_commands.get(self.data.name)
        if command_data is None:
                raise SelfBotRequestSetupError(
                    f"No command with name {self.data.name} associated with application id {self.application_id}")
         
        command_id, command_version = command_data
        
        self.data.version = command_version
        self.data.id = command_id
        self.session_id = bot.session_id       

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

    def set_arg(self, name: str, value: ApplicationCommandArgValueType, focused: bool | None = None) -> Self:
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

def build_interaction(type: InteractionType, application_id: int, guild_id: int, channel_id: int, data: InteractionDataType) -> Interaction:
    return Interaction(
        type=type,
        application_id=str(application_id),
        guild_id=str(guild_id),
        channel_id=str(channel_id),
        nonce=str(random.randint(
            100_000_000_000_000_0000, 900_000_000_000_000_0000)),
        data=data)


def build_app_command(type: Literal[InteractionType.APP_COMMAND, InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE],
                      application_id: int,
                      guild_id: int,
                      channel_id: int,
                      data: ApplicationCommand
                    ) -> Interaction:
    return build_interaction(type, application_id, guild_id, channel_id, data)

def press_button(application_id: int, guild_id: int, channel_id: int, custom_id: str) -> Interaction:
    return build_interaction(
        InteractionType.MESSAGE_COMPONENT,
        application_id,
        guild_id,
        channel_id,
        MessageComponent(custom_id=custom_id, component_type=ComponentType.BUTTON)    
    )

class SelectType(Enum):
    STRING_SELECT = 3
    USER_SELECT = 5
    ROLE_SELECT = 6
    MENTIONABLE_SELECT = 7
    CHANNEL_SELECT = 8

SelectType : TypeAlias = Literal[
    ComponentType.STRING_SELECT,
    ComponentType.USER_SELECT,
    ComponentType.ROLE_SELECT,
	ComponentType.MENTIONABLE_SELECT,
	ComponentType.CHANNEL_SELECT
]

def select_dropdown(application_id: int, guild_id: int, channel_id: int, select_type: SelectType, custom_id: str, value: str) -> Interaction:
    return build_interaction(
        InteractionType.MESSAGE_COMPONENT,
        application_id,
        guild_id,
        channel_id,
        MessageComponent(custom_id=custom_id, component_type=select_type, values=[value])    
    )
