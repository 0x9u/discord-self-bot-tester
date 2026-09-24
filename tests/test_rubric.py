"""
End to end tests for the eventsbot `lachlan/rubric-event-creation` branch.

That branch adds `/rubric set_rubric_token` and `/rubric create_event`, the latter
replying with a two page `ModalBook`: a button per modal page, then "Create event" to
submit everything to Rubric.

Needs the eventsbot running that branch as TEST_BOT_USER_ID, and the self-bot account
allowed to run `rubric create_event` by the bot's PermCog.

The happy path posts a real (private) event to Rubric, so it only runs when
RUBRIC_TOKEN is set; the other tests use a dummy token and never get as far as Rubric.
"""

from discord_self_bot_tester import Bot
from discord_self_bot_tester.gateway import (
    ButtonStyle,
    Message,
    Modal,
)
from discord_self_bot_tester.requests import (
    InteractionType,
    ApplicationCommandBuilder,
    ModalResponseBuilder,
    press_button
)

from discord_self_bot_tester.assertions import (
    MessageAssertionBuilder,
    ModalAssertionBuilder
)

import pytest
from os import getenv
import asyncio
import re

TEST_BOT_USER_ID = 1506514597237231687
HELLO_THERE_CHANNEL_ID = 886072688001560597
GUILD_ID = 886072611396796427

DUMMY_RUBRIC_TOKEN = "selfbot-dummy-token"
DUMMY_SOCIETY_ID = "12345"

DETAILS_BUTTON = "1. Event details"
TICKETS_BUTTON = "2. Ticket details"
TICKET_TYPES_BUTTON = "3. Ticket types"
CREATE_BUTTON = "Create Event"

def _run(test):
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test())

async def _open_rubric_book(bot: Bot, rubric_token: str, society_id: str) -> Message:
    """
    Sets the rubric token, then opens the event form, returning the message holding
    its buttons.
    """
    # deferred, so the reply edits the "thinking" message
    await MessageAssertionBuilder()\
        .filter_by_author(TEST_BOT_USER_ID)\
        .filter_by_message_update()\
        .compile()\
        .assert_request(
            bot,
            ApplicationCommandBuilder(InteractionType.APP_COMMAND, "rubric")\
                .set_main_command("set_rubric_settings")\
                .set_arg("rubric_token", rubric_token)\
                .set_arg("society_id", society_id)\
                .compile(TEST_BOT_USER_ID, GUILD_ID, HELLO_THERE_CHANNEL_ID)
        )

    return await MessageAssertionBuilder()\
        .filter_by_message_update()\
        .assert_by_button_labels([DETAILS_BUTTON, TICKETS_BUTTON, TICKET_TYPES_BUTTON, CREATE_BUTTON])\
        .compile()\
        .assert_request(
            bot,
            ApplicationCommandBuilder(InteractionType.APP_COMMAND, "rubric")\
                .set_main_command("create_event")\
                .compile(TEST_BOT_USER_ID, GUILD_ID, HELLO_THERE_CHANNEL_ID)
        )

async def _open_details(bot: Bot, book: Message) -> Modal:
    return await ModalAssertionBuilder()\
        .assert_by_modal_title(re.escape("Rubric event: details"))\
        .compile()\
        .assert_request(bot, press_button(book, DETAILS_BUTTON))

async def _submit_details(bot: Bot, book: Message) -> Message:
    """
    Fills in the details page, returning the book as the bot edited it.

    A valid page is not answered with a message, the bot edits the book instead: the
    details button goes green and the ticket details page unlocks.
    """
    modal = await _open_details(bot, book)

    return await MessageAssertionBuilder()\
        .filter_by_author(TEST_BOT_USER_ID)\
        .filter_by_message_update()\
        .assert_by_button(DETAILS_BUTTON, style=ButtonStyle.SUCCESS)\
        .assert_by_button(TICKETS_BUTTON, disabled=False)\
        .compile()\
        .assert_request(
            bot,
            ModalResponseBuilder(modal)
            .select("Event name")
            .set_text("selfbot rubric test")
            .select("Description")
            .set_text("created by discord-self-bot-tester")
            .select("Is this event online?")
            .choose("Yes")
            .select("Event starts")
            .set_text("2030-01-01 18:00")
            .select("Event ends")
            .set_text("2030-01-01 21:00")
            .compile(GUILD_ID, HELLO_THERE_CHANNEL_ID, TEST_BOT_USER_ID)
        )

async def _submit_tickets(bot: Bot, book: Message):
    modal = await ModalAssertionBuilder()\
        .assert_by_modal_title(re.escape("Rubric event: ticket details"))\
        .compile()\
        .assert_request(bot, press_button(book, TICKETS_BUTTON))

    await MessageAssertionBuilder()\
        .filter_by_message_update()\
        .compile()\
        .assert_request(
            bot,
            ModalResponseBuilder(modal)
            .select("Ticket sales start")
            .set_text("2026-09-24 12:45")
            .select("Ticket sales end")
            .set_text("2030-01-01 21:00")
            .select("Banner image (optional)")
            .set_values()
            .select("Ticket Types")
            .choose("Free Ticket")
            .compile(GUILD_ID, HELLO_THERE_CHANNEL_ID, TEST_BOT_USER_ID)
        )

@pytest.mark.skipif(getenv("RUBRIC_TOKEN") is None,
                    reason="creates a real Rubric event, set RUBRIC_TOKEN to run")
def test_rubric_create_event_submits(token: str):
    async def main():
        bot = Bot(token)
        bot.run()

        try:
            await bot.wait_ready()
            await bot.index_application_commands(GUILD_ID)

            book = await _open_rubric_book(bot, str(getenv("RUBRIC_TOKEN")), str(getenv("RUBRIC_ID")))

            book = await _submit_details(bot, book)
            
            await asyncio.sleep(5)
            
            await _submit_tickets(bot, book)

            await MessageAssertionBuilder()\
                .filter_by_author(TEST_BOT_USER_ID)\
                .filter_by_message_update()\
                .assert_by_message_content(re.escape("Created **selfbot rubric test** on Rubric."))\
                .compile()\
                .assert_request(bot, press_button(book, CREATE_BUTTON), deadline=30)

        finally:
            await bot.stop()

    _run(main)
