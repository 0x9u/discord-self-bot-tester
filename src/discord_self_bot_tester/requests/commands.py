"""
Interactions: the payload discord's client sends when a user uses a command or touches
a component.

All four interaction types share the one `Interaction` request and differ in what goes
in `data`:

* APP_COMMAND / APPLICATION_COMMAND_AUTOCOMPLETE carry an `ApplicationCommand`, and need
  the target command's id and version, which is why `Bot.index_application_commands` has
  to have been run first
* MESSAGE_COMPONENT carries a `MessageComponent` plus the message being acted on
* MODAL_SUBMIT carries a `ModalSubmitData` mirroring the modal's own layout

Sending an interaction is a three step affair: post it, ack the channel, then wait for
the gateway to report INTERACTION_SUCCESS or INTERACTION_FAILURE. The last step is what
makes a rejected interaction fail the test instead of quietly producing no message.
"""

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
    """
    What kind of command was invoked: a slash command, or a context menu entry.
    """

    CHAT_INPUT = 1
    USER = 2
    MESSAGE = 3
    PRIMARY_ENTRY_POINT = 4


class InteractionType(Enum):
    """
    Which of discord's interaction flows a request belongs to.
    """

    APP_COMMAND = 2
    MESSAGE_COMPONENT = 3
    APPLICATION_COMMAND_AUTOCOMPLETE = 4
    MODAL_SUBMIT = 5

ApplicationCommandArgValueType : TypeAlias = bool | int | float | str

class ApplicationCommand(BaseModel):
    """
    A command invocation, and recursively its subcommands and arguments.

    The same model serves all three tiers of discord's option tree: the command itself
    has `options` and no `value`, a leaf argument has a `value` and no `options`, and a
    subcommand sits in between. `id` and `version` are only set on the outermost one,
    and are filled in from the bot's command index just before sending.

    `focused` marks the argument the caret is in, which is the one an autocomplete
    interaction is asking about.
    """

    model_config = ConfigDict(use_enum_values=True)

    type: ApplicationCommandType
    name: str
    options: list["ApplicationCommand"] | None = None
    value: ApplicationCommandArgValueType | None = None
    id : str | None = None
    version: str | None = None
    focused: bool | None = None

class ComponentType(Enum):
	"""
	Discord's component type numbers, as sent back in an interaction payload.

	Mirrors the wire `type` on the `..gateway.component` models, so a received
	component can be echoed back with `ComponentType(component.type)`.
	"""

	ACTION_ROW = 1
	BUTTON = 2
	STRING_SELECT = 3
	TEXT_INPUT = 4
	USER_SELECT = 5
	ROLE_SELECT = 6
	MENTIONABLE_SELECT = 7
	CHANNEL_SELECT = 8
	TEXT_DISPLAY = 10
	LABEL = 18
	FILE_UPLOAD = 19
	RADIO_GROUP = 21
	CHECKBOX_GROUP = 22
	CHECKBOX = 23


class MessageComponent(BaseModel):
	"""
	The `data` of a MESSAGE_COMPONENT interaction: which component was touched.

	`values` is left None for a button and holds the chosen values for a select menu.
	Built by the helpers in `.component` rather than by hand.
	"""

	custom_id: str
	component_type: ComponentType
	values: list[str] | None = None

# https://docs.discord.food/interactions/receiving-and-responding#modal-submit-component-data-structure
class ModalSubmitComponentData(BaseModel):
	"""
	One node of a submitted modal, echoing the shape of the component it answers.

	Which of `value`, `values`, `component` and `components` is populated depends
	entirely on `type`; the comments on each field say which types use it. Built by
	`ModalResponseBuilder`, which keeps the nesting consistent with the modal discord
	actually sent.
	"""

	type: ComponentType
	id: int | None = None
	# absent on ACTION_ROW and LABEL
	custom_id: str | None = None
	# TEXT_INPUT, RADIO_GROUP, CHECKBOX
	value: str | bool | None = None
	# the select menus, FILE_UPLOAD and CHECKBOX_GROUP
	values: list[str] | None = None
	# LABEL
	component: "ModalSubmitComponentData | None" = None
	# ACTION_ROW
	components: list["ModalSubmitComponentData"] | None = None

# https://docs.discord.food/interactions/receiving-and-responding#modal-submit-data-structure
class ModalSubmitData(BaseModel):
	"""
	The `data` of a MODAL_SUBMIT interaction: the modal's own ids plus the answers.
	"""

	# the id of the modal discord sent us, echoed back
	id: str | None = None
	custom_id: str
	components: list[ModalSubmitComponentData]

InteractionDataType : TypeAlias = ApplicationCommand | MessageComponent | ModalSubmitData

class InteractionFailed(Exception):
    """
    Discord accepted the HTTP request but the gateway reported INTERACTION_FAILURE.

    Usually means the receiving bot raised, timed out, or refused the interaction - the
    HTTP call succeeding only means discord took delivery of it.
    """

    pass

class Interaction(Request):
    """
    Any of discord's four interaction types, built by the helpers rather than by hand.

    `nonce` is chosen by us and is the thread tying everything together: discord echoes
    it on the message the interaction produces, on the modal it opens, and on the
    INTERACTION_SUCCESS dispatch, which is how the assertions know which reply is
    theirs.
    """

    type: InteractionType
    application_id: str
    guild_id: str
    channel_id: str
    nonce: str
    data: InteractionDataType
    session_id: str | None = None
    # only applicable to MESSAGE_COMPONENT interactions
    message_id: str | None = None
    message_flags: int | None = None
    
    async def request(self, bot: Bot, session: ClientSession):
        """
        Posts the interaction, acks it, then waits for the gateway's verdict.

        Raises `SelfBotRequestError` if discord rejects the call outright, and
        `InteractionFailed` if it accepts it but the receiving application errors.
        """
        # dispatch depending on type
        
        if self.type == InteractionType.APP_COMMAND or self.type == InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE:
            await self._prepare_app_command(bot, session)
        elif self.type == InteractionType.MESSAGE_COMPONENT or self.type == InteractionType.MODAL_SUBMIT:
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

        await asyncio.wait_for(asyncio.shield(bot._gateway._interaction_status_events[self.nonce].wait()), timeout=INTERACTION_TIMEOUT)
        
        print("WOW")
        
        del bot._gateway._interaction_status_events[self.nonce]
        status = bot._gateway._interaction_status_data.pop(self.nonce)
        
        if not status:
            raise InteractionFailed
    
    async def _prepare_app_command(self, bot: Bot, session: ClientSession):
        """
        Stamps the command's id and version onto the payload from the bot's index.

        Discord rejects a command invocation that does not carry the exact version it
        currently has registered, so this cannot be skipped or guessed.
        """
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

def _build_interaction(type: InteractionType, application_id: int, guild_id: int, channel_id: int, data: InteractionDataType,
                      message_id: str | None = None, message_flags: int | None = None) -> Interaction:
    """
    An `Interaction` with a freshly chosen nonce, ids stringified for the wire.
    """
    return Interaction(
        type=type,
        application_id=str(application_id),
        guild_id=str(guild_id),
        channel_id=str(channel_id),
        nonce=str(random.randint(
            100_000_000_000_000_0000, 900_000_000_000_000_0000)),
        data=data,
        message_id=message_id,
        message_flags=message_flags)

InteractionTypeApplicationCommand : TypeAlias = Literal[
    InteractionType.APP_COMMAND,
    InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE
]

class ApplicationCommandBuilder:
    """
    Assembles a slash command invocation, or an autocomplete request for one.

    `set_main_command` descends into a subcommand and points the argument setters at
    it, so calls read in the order a user would type them.

    ApplicationCommandBuilder(InteractionType.APP_COMMAND, "attendance")\
        .set_main_command("click_for_attendance")\
        .set_arg("event", EVENT_UUID)\
        .compile(APPLICATION_ID, GUILD_ID, CHANNEL_ID)
    """

    Self: TypeAlias = 'ApplicationCommandBuilder'

    interaction_type: InteractionTypeApplicationCommand
    data: ApplicationCommand
    main_command: ApplicationCommand

    def __init__(self, interaction_type: InteractionTypeApplicationCommand, name: str):
        self.interaction_type = interaction_type
        self.data = ApplicationCommand(type=ApplicationCommandType.CHAT_INPUT, name=name, options=None, value=None, version=None)
        self.main_command = self.data

    def set_main_command(self, name: str) -> Self:
        """
        Nests a subcommand under the command, and aims `set_arg` at it.
        """
        self.main_command = ApplicationCommand(
            type=ApplicationCommandType.CHAT_INPUT, name=name, options=None, value=None)
        self.data.options = [self.main_command]
        return self

    def set_arg(self, name: str, value: ApplicationCommandArgValueType, focused: bool | None = None) -> Self:
        """
        Adds an argument to whichever command is currently being built.

        `focused=True` marks this as the argument an autocomplete request is about;
        exactly one argument should be focused on an
        APPLICATION_COMMAND_AUTOCOMPLETE interaction, and none on an APP_COMMAND.
        """
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

    def compile(
        self,
        application_id: int,
        guild_id: int,
        channel_id: int
        ) -> Interaction:
        """
        The finished interaction, ready to send or to hand to an assertion.

        `application_id` is the id of the bot being tested, and has to be the same one
        passed to `Bot.index_application_commands`.
        """
        return _build_interaction(
            self.interaction_type,
            application_id,
            guild_id,
            channel_id,
            self.main_command
        )

def submit_modal(application_id: int, guild_id: int, channel_id: int, data: ModalSubmitData) -> Interaction:
    return 