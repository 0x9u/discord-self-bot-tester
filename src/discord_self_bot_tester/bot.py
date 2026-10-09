from .gateway import GatewayEvent, Gateway, GatewayException

import aiohttp

from typing import Dict, Set, Tuple

import asyncio
import logging

GUILD_APPLICATION_COMMANDS_URL = "https://discord.com/api/v9/guilds/{}/application-command-index"

class Bot:
    """
    A logged in user account, driven from tests.
    
    Construct it with a user token, :meth:`run` it on an already running event loop, then
    :meth:`wait_ready` before doing anything else (we need to retrieve ``user_id`` and
    ``session_id`` from the ``READY`` payload).

    Any command whose interactions are to be sent also has to be indexed first, with
    :meth:`index_application_commands`.

    Every method here surfaces a dead websocket as a ``RuntimeError`` chained onto the
    original failure, so a connection lost mid-run fails the test rather than hanging
    it.

    :ivar token: The user token the account logs in with.
    :ivar session_id: The gateway session id, known once :meth:`wait_ready` returns.
    :ivar user_id: The account's own user id, known once :meth:`wait_ready` returns.
    :ivar ready: Whether the ``READY`` payload has been handled, or the socket died.
    """

    token: str
    session_id: str = ""
    user_id: str = ""
    
    # application_id to dict
    # dict contains name to (id, version)
    _command_version: Dict[str, Dict[str, Tuple[str, str]]]
    
    ready: bool = False
    
    _tasks : Set[asyncio.Task]
    _gateway : Gateway
    _ws_error : BaseException | None
    
    def __init__(self, token : str):
        """
        :param token: A discord user token, not a bot token.
        """
        self.token = token
        self._command_version = {}
        # tasks that last for Bot lifetime
        self._tasks = set()
        
        self._gateway = Gateway(self)
        self._ws_error = None

    def run(self):  # needs to run before anything and be global
        """
        Runs the self bot.

        .. note:: Needs a running event loop, and every test has to use that same loop.
        """
        logging.debug("Running bot")
        loop = asyncio.get_running_loop()
        self._tasks.add(loop.create_task(self._gateway.init_ws()))
    
    async def stop(self):
        """
        Cancels the gateway and heartbeat tasks and closes the socket.

        Call it from a ``finally`` so a failed assertion still tears the connection down.
        """
        for task in self._tasks:
            task.cancel()
        try:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass # meh we ballin

    def _check_ws_failed(self):
        """
        Re-raises a websocket failure on the caller's own stack.

        The socket runs in its own task, so without this its errors would surface only
        as an assertion mysteriously timing out.

        :raises RuntimeError: If the websocket has died.
        """
        if self._ws_error is not None:
            raise RuntimeError(f"Websocket died") from self._ws_error

    async def wait_ready(self):
        """
        Waits until discord's ``READY`` payload has been handled.

        :raises RuntimeError: If the socket died first, which is what an invalid token
            looks like.
        """
        await self._gateway.wait_ready()
        self._check_ws_failed()

    async def index_application_commands(self, guild_id: int):
        """
        Learns the id and version of every application command in a guild.

        Discord rejects a command invocation that does not carry the exact version it
        currently has registered, so this has to be run before any commands sent in ANY guilds.

        Commands already indexed are left alone, so re-running this will not pick up a
        redeployed bot's new versions; build a fresh :class:`Bot` for that.

        :param guild_id: The guild whose commands to index.
        :raises RuntimeError: If discord refuses the request.
        """
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": self.token,
                       "Content-Type": "application/json"}
            res = await session.get(GUILD_APPLICATION_COMMANDS_URL.format(guild_id), headers=headers)
            if res.status != 200:
                res_data = await res.text()
                raise RuntimeError("Request failed: " + str(res_data))

            data = await res.json()

            application_commands = data["application_commands"]
            for command in application_commands:
                self._command_version.setdefault(command["application_id"], {})\
                    .setdefault(command["name"], (command["id"], command["version"]))
    
    async def get_next_gateway_event(self, deadline: int) -> GatewayEvent:
        """
        Waits for the next event a filter claimed. Used by the assertions rather than
        directly.

        :param deadline: How many seconds to wait at most.
        :returns: The claimed event.
        :raises TimeoutError: If nothing matched in time.
        :raises RuntimeError: If the socket died while waiting.
        """
        self._check_ws_failed()
        
        event = await self._gateway.get_next_gateway_event(deadline)
        if isinstance(event, GatewayException):
            self._check_ws_failed()
        
        return event
