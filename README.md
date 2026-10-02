# Discord Self Bot Tester (BSBT) Library
Package for testing commands using discord selfbot. Assertions (messages, and autocomplete) and requests (interactions, events, reactions) can be made using the bot.

## Install

```bash
pip install discord-self-bot-tester
```

Needs python 3.11 or newer.

## Setup

- Create a `Bot` with a user token
- Run it with `bot.run()`
- Wait for it with `await bot.wait_ready()`
- Index the commands with `await bot.index_application_commands(GUILD_ID)` (has to happen before sending any command)
- Make tests and have fun or pain, idk ur pick
- Call `await bot.stop()` in a `finally` so a failed test still closes the socket

```py
from discord_self_bot_tester import Bot

bot = Bot(USER_TOKEN)
bot.run()
await bot.wait_ready()
await bot.index_application_commands(GUILD_ID)
```

## Commands

Build the command, then assert on the reply. `assert_request` sends it for you.

```py
from discord_self_bot_tester.requests import ApplicationCommandBuilder, InteractionType
from discord_self_bot_tester.assertions import MessageAssertionBuilder

cmd = ApplicationCommandBuilder(InteractionType.APP_COMMAND, "ping")\
    .set_arg("count", 3)\
    .compile(APPLICATION_ID, GUILD_ID, CHANNEL_ID)

msg = await MessageAssertionBuilder()\
    .assert_by_message_content("pong")\
    .compile()\
    .assert_request(bot, cmd)
```

`set_main_command("sub")` for subcommands. `await cmd.send(bot)` if u dont care about the reply.

### Filters

Which message to pick. Leave them all out and it picks the reply to the command.

- `filter_by_author(user_id)`
- `filter_by_channel(channel_id)`
- `filter_by_message_update()` for deferred or edited replies
- `filter_by_message_flags(64)` for ephemeral replies
- `filter_by_followup_message()` ties a filtered assertion back to the command

### Checks

- `assert_by_message_content(regex)`
- `assert_by_mentions([ids])`
- `assert_by_mention_roles([ids])`

Default deadline is 5 seconds, change it with `deadline=` on `assert_request`. Raises `TimeoutError` if nothing shows up.

## Views

Assert what buttons and dropdowns are on the message.

```py
from discord_self_bot_tester.gateway import ButtonStyle

msg = await MessageAssertionBuilder()\
    .assert_by_button("Confirm", style=ButtonStyle.SUCCESS)\
    .assert_by_button_labels(["Confirm", "Cancel"])\
    .assert_by_dropdown(placeholder="Pick one", option_labels=["A", "B"])\
    .compile()\
    .assert_request(bot, cmd)
```

Then click stuff. Ids get pulled off the message so u only need the label.

```py
from discord_self_bot_tester.requests import press_button, select_dropdown, select_dropdown_values

await MessageAssertionBuilder()\
    .filter_by_message_update()\
    .compile()\
    .assert_request(bot, press_button(msg, "Confirm"))

await select_dropdown(msg, "A", "B", dropdown="Pick one").send(bot)
await select_dropdown_values(msg, USER_ID, dropdown="pick_user").send(bot)
```

`dropdown` can be left out if the message only has one. User, role and channel selects take snowflakes, so use `select_dropdown_values` for those.

## Modals

Open it, fill it in by label, submit it.

```py
from discord_self_bot_tester.requests import ModalResponseBuilder
from discord_self_bot_tester.assertions import ModalAssertionBuilder

modal = await ModalAssertionBuilder()\
    .assert_by_modal_title("Sign up")\
    .compile()\
    .assert_request(bot, press_button(msg, "Register"))

submit = ModalResponseBuilder(modal)\
    .select("Name").set_text("oliver")\
    .select("Colour").choose("Green")\
    .select("Agree").set_checked()\
    .compile(GUILD_ID, CHANNEL_ID, APPLICATION_ID)

await MessageAssertionBuilder().compile().assert_request(bot, submit)
```

- `set_text(str)` for text inputs
- `choose(*labels)` for selects, radios and checkbox groups
- `set_values(*values)` and `set_option(value)` if u want raw values instead of labels
- `set_checked(bool)` for checkboxes
- `select_by_custom_id(id)` if the label is annoying

Nested labels work like `select("Address", "Postcode")`. Required fields left empty fail at `compile`, not on discord.

## Autocomplete

```py
from discord_self_bot_tester.assertions import AutoCompleteAssertionBuilder

res = await AutoCompleteAssertionBuilder().compile().assert_request(
    bot,
    ApplicationCommandBuilder(InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE, "search")
        .set_arg("query", "ab", focused=True)
        .compile(APPLICATION_ID, GUILD_ID, CHANNEL_ID)
)
```

## Other requests

Reactions, events and attachments all have builders. `.send(bot)` sends them.

```py
from discord_self_bot_tester.requests import build_reaction, build_attachment

await build_reaction("🖥️", MESSAGE_ID, CHANNEL_ID).send(bot)

file = build_attachment(data, "image.png", CHANNEL_ID)
await file.send(bot)
file.get_attachment_id()  # pass this to set_values on a modal file upload
```