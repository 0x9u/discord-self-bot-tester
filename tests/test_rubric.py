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
    RadioGroup,
    TextInputComponent,
    walk_components
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

def _text_input_id(modal: Modal, label: str) -> str | None:
    """
    The custom_id of the text input captioned `label`, or None if there is none.

    RubricCog adds its TextInputs straight to the modal rather than wrapping them in a
    discord `Label`, so the caption sits on the input itself, which
    `ModalResponseBuilder.select` does not look at. discord.py also randomises the
    custom_ids, so they have to be read back off the modal.
    """
    for component in walk_components(modal.components):
        if isinstance(component, TextInputComponent) and component.label == label:
            return component.custom_id
    return None

def _fill(modal: Modal, answers: dict[str, str]) -> ModalResponseBuilder:
    """
    Answers text inputs with their text, and anything wrapped in a `Label` (the radio
    and checkbox groups) with the option label to pick.
    """
    builder = ModalResponseBuilder(modal)
    for label, value in answers.items():
        text_input_id = _text_input_id(modal, label)
        if text_input_id is not None:
            builder.select_by_custom_id(text_input_id).set_text(value)
        else:
            builder.select(label).choose(value)
    return builder

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

async def _submit_details(bot: Bot, book: Message, answers: dict[str, str]) -> Message:
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
            _fill(modal, answers).compile(GUILD_ID, HELLO_THERE_CHANNEL_ID, TEST_BOT_USER_ID)
        )

async def _submit_tickets(bot: Bot, book: Message, answers: dict[str, str]):
    modal = await ModalAssertionBuilder()\
        .assert_by_modal_title(re.escape("Rubric event: ticket sales"))\
        .compile()\
        .assert_request(bot, press_button(book, TICKETS_BUTTON))

    await MessageAssertionBuilder()\
        .assert_by_message_content(re.escape("Ticket-sale details saved."))\
        .compile()\
        .assert_request(
            bot,
            _fill(modal, answers).compile(GUILD_ID, HELLO_THERE_CHANNEL_ID, TEST_BOT_USER_ID)
        )

def _details(**overrides: str) -> dict[str, str]:
    details = {
        "Event name": "selfbot rubric test",
        "Description": "created by discord-self-bot-tester",
        "Is this event online?": "Yes",
        "Event starts": "2030-01-01 18:00",
        "Event ends": "2030-01-01 21:00",
    }
    details.update(overrides)
    return details

def _tickets(**overrides: str) -> dict[str, str]:
    tickets = {
        "Ticket sales start": "2029-12-01 09:00",
        "Ticket sales end": "2030-01-01 17:00",
    }
    tickets.update(overrides)
    return tickets

def test_rubric_details_page_matches_form(token: str):
    """
    The details page has the fields of the form, in order: event name, description,
    the "Is this event online?" radio defaulting to No, then the start and end times.
    """
    async def main():
        bot = Bot(token)
        bot.run()

        try:
            await bot.wait_ready()
            await bot.index_application_commands(GUILD_ID)

            book = await _open_rubric_book(bot, DUMMY_RUBRIC_TOKEN, DUMMY_SOCIETY_ID)
            modal = await _open_details(bot, book)

            text_inputs = {component.label: component
                           for component in walk_components(modal.components)
                           if isinstance(component, TextInputComponent)}
            assert list(text_inputs) == ["Event name", "Description", "Event starts", "Event ends"]
            for label in ("Event starts", "Event ends"):
                assert text_inputs[label].placeholder == "YYYY-MM-DD HH:MM (e.g. 2026-03-15 19:00)"

            # fails here if the radio group is missing, or its options were renamed
            ModalResponseBuilder(modal).select("Is this event online?").choose("No")

            online = [component for component in walk_components(modal.components)
                      if isinstance(component, RadioGroup)]
            assert len(online) == 1
            assert [option.label for option in online[0].options] == ["Yes", "No"]
            assert [option.label for option in online[0].options if option.default] == ["No"]

        finally:
            await bot.stop()

    _run(main)

def test_rubric_pages_unlock_in_order(token: str):
    """
    Only the details page is open to begin with; submitting it unlocks the ticket
    details, while ticket types and "Create Event" stay locked.
    """
    async def main():
        bot = Bot(token)
        bot.run()

        try:
            await bot.wait_ready()
            await bot.index_application_commands(GUILD_ID)

            book = await _open_rubric_book(bot, DUMMY_RUBRIC_TOKEN, DUMMY_SOCIETY_ID)

            for label in (TICKETS_BUTTON, TICKET_TYPES_BUTTON, CREATE_BUTTON):
                with pytest.raises(AssertionError, match="disabled"):
                    press_button(book, label)

            book = await _submit_details(bot, book, _details())

            for label in (TICKET_TYPES_BUTTON, CREATE_BUTTON):
                with pytest.raises(AssertionError, match="disabled"):
                    press_button(book, label)

        finally:
            await bot.stop()

    _run(main)

def test_rubric_details_rejects_bad_dates(token: str):
    async def main():
        bot = Bot(token)
        bot.run()

        try:
            await bot.wait_ready()
            await bot.index_application_commands(GUILD_ID)

            book = await _open_rubric_book(bot, DUMMY_RUBRIC_TOKEN, DUMMY_SOCIETY_ID)
            modal = await _open_details(bot, book)

            await MessageAssertionBuilder()\
                .filter_by_author(TEST_BOT_USER_ID)\
                .assert_by_message_content(re.escape("Invalid times, please try again"))\
                .compile()\
                .assert_request(
                    bot,
                    _fill(modal, _details(**{"Event starts": "next friday"}))\
                        .compile(GUILD_ID, HELLO_THERE_CHANNEL_ID, TEST_BOT_USER_ID)
                )

        finally:
            await bot.stop()

    _run(main)

def test_rubric_modal_resubmit_overwrites_page(token: str):
    """
    Reopening a page and submitting it again has to replace what was saved, so a
    corrected bad date lets the event through validation.
    """
    async def main():
        bot = Bot(token)
        bot.run()

        try:
            await bot.wait_ready()
            await bot.index_application_commands(GUILD_ID)

            book = await _open_rubric_book(bot, DUMMY_RUBRIC_TOKEN, DUMMY_SOCIETY_ID)

            book = await _submit_details(bot, book, _details(**{"Event ends": "whenever"}))
            await _submit_tickets(bot, book, _tickets())

            await MessageAssertionBuilder()\
                .assert_by_message_content(re.escape("Dates must use"))\
                .compile()\
                .assert_request(bot, press_button(book, CREATE_BUTTON))

            book = await _submit_details(bot, book, _details())

            # past validation now, so the bot defers and answers with a followup
            # editing the "thinking" message; the dummy token means Rubric's answer is
            # not asserted on, only that the dates error is gone
            msg = await MessageAssertionBuilder()\
                .filter_by_author(TEST_BOT_USER_ID)\
                .filter_by_message_update()\
                .compile()\
                .assert_request(bot, press_button(book, CREATE_BUTTON), deadline=30)

            assert not msg.content.startswith("Dates must use"), msg.content

        finally:
            await bot.stop()

    _run(main)

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

            book = await _submit_details(bot, book, _details())
            await _submit_tickets(bot, book, _tickets(**{
                "Banner image URL (optional)": "https://example.com/event-banner.png"
            }))

            await MessageAssertionBuilder()\
                .filter_by_author(TEST_BOT_USER_ID)\
                .filter_by_message_update()\
                .assert_by_message_content(re.escape("Created **selfbot rubric test** on Rubric."))\
                .compile()\
                .assert_request(bot, press_button(book, CREATE_BUTTON), deadline=30)

        finally:
            await bot.stop()

    _run(main)
