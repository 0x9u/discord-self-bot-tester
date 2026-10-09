from ._base import (
    Filter,
    GatewayEvent
)
from .autocomplete import CommandAutoCompleteResponse

import aiohttp
import random
import asyncio
import logging

from typing import cast, Any, TYPE_CHECKING

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

class GatewayException(GatewayEvent):
    """
    Queued in place of a real event when the socket dies.

    Lets a waiting :meth:`Gateway.get_next_gateway_event` return immediately rather than
    waiting for its deadline.
    """
    pass

class Gateway:
    """
    Owns the websocket and the queue of events the assertions read from.

    Used by :class:`~discord_self_bot_tester.bot.Bot`, created in its constructor and
    started by :meth:`Bot.run <discord_self_bot_tester.bot.Bot.run>`.
    """

    _ws: aiohttp.ClientWebSocketResponse | None = None
    _assert_filter: Filter | None = None
    _sleep_delay_max: int = 2  # in secs
    _gateway_queue: asyncio.Queue[GatewayEvent]
    _ready_cond: asyncio.Condition
    
    bot: "Bot"
    
    # used by Interaction.request to await for its status data.
    _interaction_status_events: dict[str, asyncio.Event]
    _interaction_status_data: dict[str, bool]

    def __init__(self, bot: "Bot"):
        self._gateway_queue = asyncio.Queue()
        self._ready_cond = asyncio.Condition()
        self.bot = bot
        self._interaction_status_events = {}
        self._interaction_status_data = {}

    async def wait_ready(self):
        """
        Waits until ``READY`` has been handled, so ``session_id`` and ``user_id`` are known.

        .. note:: :meth:`init_ws` also sets ``ready`` when the socket dies, so callers are
            expected to check ``Bot._ws_error`` afterwards.
        """
        async with self._ready_cond:
            await self._ready_cond.wait_for(lambda: self.bot.ready)

    async def __heartbeat_task(self):
        """
        Keeps the socket alive for as long as it is open.
        """
        _ws = cast(aiohttp.ClientWebSocketResponse, self._ws)

        while True:
            # uses the given interval from the HELLO payload as its upper bound.
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
        """
        Waits for the next event a filter claimed.

        :param deadline: How many seconds to wait at most.
        :returns: The claimed event, or a :class:`GatewayException` if the socket died.
        :raises TimeoutError: If nothing matched in time.
        """
        gateway_event = await asyncio.wait_for(self._gateway_queue.get(), timeout=deadline)
        self._gateway_queue.task_done()
        return gateway_event
    
    async def init_ws(self):
        """
        Connects, identifies, then dispatches payloads until the socket closes.

        Runs for the lifetime of the bot as a task owned by ``Bot._tasks``. Any error is
        recorded on ``Bot._ws_error`` and re-raised, so ``Bot._check_ws_failed`` can
        surface it on the test's own thread of control.

        :raises RuntimeError: If discord invalidates the session or closes the socket
            abnormally, which is what an invalid token looks like.
        """
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
                                    case "INTERACTION_SUCCESS" | "INTERACTION_FAILURE":
                                        nonce = data["d"]["nonce"]
                                        status_event = self._interaction_status_events.get(nonce)
                                        if status_event is not None:
                                            self._interaction_status_data[nonce] = t == "INTERACTION_SUCCESS"
                                            status_event.set()
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
                                        # the filter decides which payload it wants and
                                        # builds the gateway event out of it
                                        matched = None if self._assert_filter is None \
                                            else self._assert_filter.matches(self.bot.user_id, data)
                                        if matched is None:
                                            logging.debug(
                                                "Unknown data: " + str(data))
                                            continue
                                        self._assert_filter = None
                                        await self._gateway_queue.put(matched)
                    
                    if _ws.close_code != 1000: # occurs when token is invalid
                        raise RuntimeError(
                            "Websocket closed by discord - " + str(_ws.close_code))
            except BaseException as e:
                self.bot._ws_error = e
                await self._gateway_queue.put(GatewayException())
                raise
            finally:
                # both `async with`s already close the socket and session
                # to propgate error to wait_ready
                async with self._ready_cond:
                    self.bot.ready = True
                    self._ready_cond.notify_all()
