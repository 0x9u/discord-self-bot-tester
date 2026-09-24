"""
The websocket connection to discord's user gateway.

`Gateway` logs in with the account token, keeps the socket alive, and dispatches what
comes back. Three kinds of payload are handled directly:

* READY, which carries the session id and user id the interaction endpoints need
* INTERACTION_SUCCESS / INTERACTION_FAILURE, the acknowledgement `Interaction.request`
  waits on to learn whether discord accepted the interaction
* APPLICATION_COMMAND_AUTOCOMPLETE_RESPONSE, queued unconditionally

Everything else is offered to the single installed `Filter`, and dropped when no filter
claims it. There is deliberately no reconnect: a test run that loses its socket should
fail loudly, so the error is stashed on the bot and a `GatewayException` is queued to
wake whichever assertion is waiting.
"""

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

    Lets a waiting `get_next_gateway_event` return immediately rather than sit on its
    deadline; the caller then re-checks `Bot._ws_error` for the underlying cause.
    """
    pass

class Gateway:
    """
    Owns the websocket and the queue of events the assertions read from.

    One per `Bot`, created in its constructor and started by `Bot.run`.
    """

    _ws: aiohttp.ClientWebSocketResponse | None = None
    _assert_filter: Filter | None = None
    _sleep_delay_max: int = 2  # in secs
    _gateway_queue: asyncio.Queue[GatewayEvent]
    _ready_cond: asyncio.Condition
    
    bot: "Bot"
    
    # Registered by `Interaction.request` before it posts, and discarded by it in a
    # `finally` - so an entry existing here means someone is still waiting on it.
    _interaction_status_events: dict[str, asyncio.Event]
    _interaction_status_data: dict[str, bool]

    def __init__(self, bot: "Bot"):
        self._gateway_queue = asyncio.Queue()
        self._ready_cond = asyncio.Condition()
        self.bot = bot
        self._interaction_status_events = {}
        self._interaction_status_data = {}

    # Required to await for session_id, etc from READY payload
    async def wait_ready(self):
        """
        Waits until READY has been handled, so `session_id` and `user_id` are known.

        Also returns when the socket dies, because `init_ws` flips `ready` in its
        `finally` to release anyone waiting here; callers are expected to check
        `Bot._ws_error` afterwards.
        """
        async with self._ready_cond:
            await self._ready_cond.wait_for(lambda: self.bot.ready)

    async def __heartbeat_task(self):
        """
        Keeps the socket alive for as long as it is open.

        The interval upper bound comes from the HELLO payload; each wait is jittered
        inside it so we never sit exactly on discord's timeout.
        """
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
        """
        The next event a filter claimed, waiting at most `deadline` seconds.

        Raises `TimeoutError` if nothing matched in time, which is how an assertion
        reports that the expected message never arrived.
        """
        gateway_event = await asyncio.wait_for(self._gateway_queue.get(), timeout=deadline)
        self._gateway_queue.task_done()
        return gateway_event
    
    async def init_ws(self):
        """
        Connects, identifies, then dispatches payloads until the socket closes.

        Runs for the lifetime of the bot as a task owned by `Bot._tasks`. Any error is
        recorded on `Bot._ws_error` and re-raised, so `Bot._check_ws_failed` can
        surface it on the test's own thread of control.
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
                                        if self._assert_filter is None:
                                            logging.debug(
                                                "Unknown data: " + str(data))
                                            continue
                                        matched = self._assert_filter.matches(
                                            self.bot.user_id, data)
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
                if self._ws is not None:
                    await self._ws.close()
                
                await session.close()
                # to propgate error to wait_ready
                async with self._ready_cond:
                    self.bot.ready = True
                    self._ready_cond.notify_all()
