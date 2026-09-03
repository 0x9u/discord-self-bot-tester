from discord_self_bot_tester import Bot
from discord_self_bot_tester.requests import (
    build_reaction,
    GuildScheduledEventEntityType,
    PrivacyLevel,
    ScheduledEventBuilder,
)

from discord_self_bot_tester.assertions import (
    MessageAssertionBuilder
)

import pytest
from os import getenv
from datetime import datetime
import asyncio

def test_basic_bot(token : str):
    
    async def main():
        
        APPLICATION_ID = 886072611396796427
        TEST_BOT_USER_ID = 1115812941502087168
        HELLO_THERE_CHANNEL_ID = 886072688001560597

        bot = Bot(token)
        bot.run()

        try:
            await bot.wait_ready()

            await bot.index_application_commands(APPLICATION_ID)

            msg = await MessageAssertionBuilder().filter_by_author(TEST_BOT_USER_ID).compile().assert_request(
                bot,
                ScheduledEventBuilder(
                    GuildScheduledEventEntityType.EXTERNAL,
                    PrivacyLevel.GUILD_ONLY,
                    APPLICATION_ID,
                    "test event - selfbot",
                    "test event description - selfbot",
                    datetime.now()
                ).set_location("selfbot").set_end_time(datetime.now()).compile()
            )
            msg_id = int(msg.id)

            await asyncio.sleep(2)

            msg = await MessageAssertionBuilder().filter_by_author(TEST_BOT_USER_ID).compile().assert_request(
                bot,
                build_reaction("✅", msg_id, HELLO_THERE_CHANNEL_ID)
            )

            msg_id = int(msg.id)

            await asyncio.sleep(4)

            await build_reaction("🖥️", msg_id, HELLO_THERE_CHANNEL_ID).send(bot)

            await asyncio.sleep(2)

            await MessageAssertionBuilder().filter_by_author(TEST_BOT_USER_ID).filter_by_message_update().compile().assert_request(
                bot,
                build_reaction("✅", msg_id, HELLO_THERE_CHANNEL_ID)
            )

            await MessageAssertionBuilder()\
                .filter_by_author(TEST_BOT_USER_ID)\
                .filter_by_message_update()\
                .assert_by_message_content("Form created for .*\\n.*\\n.*")\
                .compile().assert_gateway(bot, deadline=60)

        finally:
            await bot.stop()
    
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())

def test_wrong_token(token: str):    
    
    async def main():
        bot = Bot("AAA")
        bot.run()
        
        try:
            with pytest.raises(RuntimeError):
                await bot.wait_ready()
        finally:    
            await bot.stop()
        
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
