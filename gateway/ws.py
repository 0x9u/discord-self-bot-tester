from .message import Message
from ._base import (
    MessageFilter,
    GatewayEvent
)
from .autocomplete import CommandAutoCompleteResponse

import aiohttp
import random
import asyncio
import logging

from typing import cast, Optional, Any, TYPE_CHECKING

# avoids cyclic import
if TYPE_CHECKING:
    from ..bot import Bot

PROPERTIES = {  # please don't steal my data - oliver
    "os": "Windows",
    "browser": "Firefox",
    "device": "",
    "system_locale": "en-US",
    "has_client_mods": False,
    "browser_USER_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
    "browser_version": "150.0",
    "os_version": "10",
    "referrer": "https://www.google.com/",
    "referring_domain": "www.google.com",
    "search_engine": "google",
    "referrer_current": "",
    "referring_domain_current": "",
    "release_channel": "stable",
    "client_build_number": 546605,
    "client_event_source": None,
    "client_launch_id": "203c3bc2-e787-4df9-9c3c-39a0617c12e5",
    "is_fast_connect": True,
    "installation_id": "1472435156357877996.NPzylawn6sQb7uQQxXe6GKH_H4Q"
}

WEBSOCKET_URL = "wss://gateway.discord.gg/?encoding=json&v=9"

class Gateway:    
    _assert_msg: Optional[MessageFilter] = None
    _sleep_delay_max: int = 2  # in secs
    _gateway_queue: asyncio.Queue[GatewayEvent]
    _ready_cond: asyncio.Condition
    
    bot: "Bot"
    
    def __init__(self, bot: "Bot"):        
        self._gateway_queue = asyncio.Queue()
        self._ready_cond = asyncio.Condition()
        self.bot = bot

    # Required to await for session_id, etc from READY payload
    async def wait_ready(self):
        async with self._ready_cond:
            await self._ready_cond.wait_for(lambda: self.bot.ready)

    async def __heartbeat_task(self):
        _ws = cast(aiohttp.ClientWebSocketResponse, self._ws)

        while True:

            await asyncio.sleep(random.randint(1, self._sleep_delay_max))

            await _ws.send_json({
                "op": 40,
                "d": {
                    "seq": 15,
                    "qos": {
                        "active": False,
                        "ver": 27,
                        "reasons": []
                    }
                }
            })
    
    async def get_next_gateway_event(self, deadline: int) -> GatewayEvent:
        gateway_event = await asyncio.wait_for(self._gateway_queue.get(), timeout=deadline)
        self._gateway_queue.task_done()
        return gateway_event
    
    async def init_ws(self):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.ws_connect(WEBSOCKET_URL) as _ws:
                    logging.debug("Websocket connected")
                    self._ws = _ws

                    init_data = {
                        "op": 2,  # auth type
                        "d": {
                            "token": self.bot.token,
                            "capabilities": 1734653,
                            "properties": PROPERTIES
                        }
                    }

                    await _ws.send_json(init_data)
                    # https://docs.discord.food/gateway/opcodes-and-close-codes

                    async for gateway_event in _ws:
                        if gateway_event.type == aiohttp.WSMsgType.TEXT:
                            data: dict[str, Any] = gateway_event.json()
                            logging.debug(f"Gateway event: {data}")
                            opcode: int = data["op"]
                            if opcode == 9:  # invalid session
                                # todo: capture error, make sure its not silent
                                raise RuntimeError(
                                    "Websocket closed by discord - invalid session")
                            elif opcode == 10:  # hello
                                self._sleep_delay_max = data["d"]["heartbeat_interval"] // 1000
                                logging.debug("Adding heartbeat task")
                                self.bot._tasks.add(asyncio.create_task(
                                    self.__heartbeat_task()))
                                logging.debug("Heartbeat task added")

                            elif opcode == 0:
                                t: str = data["t"]
                                match t:
                                    case "MESSAGE_CREATE" | "MESSAGE_UPDATE":
                                        data = data["d"]

                                        msg_match = self._assert_msg is not None and \
                                            self._assert_msg.matches(
                                                self.bot.user_id,
                                                t,
                                                data
                                            )
                                        if msg_match:
                                            self._assert_msg = None
                                            gateway_event = Message.model_validate(
                                                data)
                                            await self._gateway_queue.put(gateway_event)
                                        else:
                                            logging.debug(
                                                "Unknown data: " + str(data))

                                    case "READY":
                                        data = data["d"]
                                        self.bot.user_id = data["user"]["id"]
                                        self.bot.session_id = data["session_id"]

                                        async with self._ready_cond:
                                            self.bot.ready = True
                                            self._ready_cond.notify_all()
                                        
                                    case "APPLICATION_COMMAND_AUTOCOMPLETE_RESPONSE":
                                        data = data["d"]
                                        gateway_event = CommandAutoCompleteResponse.model_validate(
                                            data)
                                        await self._gateway_queue.put(gateway_event)
                                    case _:
                                        logging.debug(
                                            "Unknown data: " + str(data))
                    
                    if _ws.close_code != 1000: # occurs when token is invalid
                        raise RuntimeError(
                            "Websocket closed by discord - " + str(_ws.close_code))
            finally:
                if self._ws is not None:
                    await self._ws.close()
                
                await session.close()
    
    async def stop_ws(self):
        if self._ws is not None:
            await self._ws.close()
