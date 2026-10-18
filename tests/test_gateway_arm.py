from discord_self_bot_tester import Bot
from discord_self_bot_tester.assertions import MessageAssertionBuilder
from discord_self_bot_tester.gateway import GatewayException

import asyncio
import pytest


class FailingRequest:
    async def send(self, bot):
        raise RuntimeError("send failed")


def test_failed_send_disarms_filter_and_drops_stale_events():
    async def main():
        bot = Bot("token")
        gateway = bot._gateway
        gateway._gateway_queue.put_nowait(GatewayException())  # leftover from an earlier assertion

        with pytest.raises(RuntimeError, match="send failed"):
            await MessageAssertionBuilder().compile().assert_request(bot, FailingRequest())

        assert gateway._assert_filter is None
        assert gateway._gateway_queue.empty()

    asyncio.run(main())
