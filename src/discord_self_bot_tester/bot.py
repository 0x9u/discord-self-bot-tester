from discord_self_bot_tester.gateway import GatewayException

from .gateway import GatewayEvent, Gateway

import aiohttp

from typing import Dict, Set, Tuple

import asyncio
import logging

GUILD_APPLICATION_COMMANDS_URL = "https://discord.com/api/v9/guilds/{}/application-command-index"

class Bot:
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
        self.token = token
        self._command_version = {}
        # tasks that last for Bot lifetime
        self._tasks = set()
        
        self._gateway = Gateway(self)
        self._ws_error = None

    def run(self):  # needs to run before anything and be global
        """
        Runs the self bot.
        
        @precond event loop exists and tests use same event loop
        """
        logging.debug("Running bot")
        loop = asyncio.get_running_loop()
        self._tasks.add(loop.create_task(self._gateway.init_ws()))
    
    async def stop(self):
        await self.__stop_tasks()

    async def __stop_tasks(self):
        for task in self._tasks:
            task.cancel()
        try:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass # meh we ballin

    def _check_ws_failed(self):
        print("WS_ERROR", self._ws_error)
        if self._ws_error is not None:
            raise RuntimeError(f"Websocket died") from self._ws_error

    async def wait_ready(self):
        await self._gateway.wait_ready()
        self._check_ws_failed()

    async def index_application_commands(self, guild_id: int):
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
        self._check_ws_failed()
        
        event = await self._gateway.get_next_gateway_event(deadline)
        if isinstance(event, GatewayException):
            self._check_ws_failed()
        
        return event
