"""
Discord Self Bot Tester: drive a discord bot from a real user account and assert on
what it sends back.

The library is in three layers, and a test normally reaches for the third:

* `gateway` receives - the websocket, and the models for the payloads that arrive
* `requests` sends - interactions, scheduled events, reactions
* `assertions` pairs the two - send this, expect that, hand back the parsed reply

Everything hangs off one `Bot`, which owns the connection and the command index.

    bot = Bot(token)
    bot.run()
    await bot.wait_ready()
    await bot.index_application_commands(GUILD_ID)

    msg = await MessageAssertionBuilder()\
        .filter_by_author(BOT_USER_ID)\
        .assert_by_button("Confirm")\
        .compile().assert_request(bot, interaction)

    await MessageAssertionBuilder().filter_by_message_update().compile()\
        .assert_request(bot, press_button(msg, "Confirm"))

This automates a user account, which discord's terms of service prohibit. Use a throwaway
account on a guild you control.
"""

from .bot import Bot

__all__ = [ "Bot" ]