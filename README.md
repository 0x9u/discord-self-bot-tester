# Discord Self Bot Tester (BSBT) Library
Package for testing commands using discord selfbot. Assertions (messages, and autocomplete) and requests (interactions, events, reactions) can be made using the bot.

## Features:
### Assertions
Assertions can be made on requests. Currently, the supported assertions are: `MessageAssertion`, and `AutoCompleteAssertion`. 
Each assertion has a respective builder class which are: `MessageAssertionBuilder`, and `AutoCompleteAssertionBuilder`.

Assertions creates the ability to expect a message after a request has been sent (e.g. creating an event), as well as retrieving the data of the asserted message. 

Assertions have a default deadline of 10 seconds, and if violated, will raise an TimeoutError. This can be changed by altering the deadline parameter. Below is an example.

```py
# NOTE: its actually called Bot class but I used an import alias for readability.
from discordselftests import Bot as SelfBotTester

load_dotenv()
bot = SelfBotTester(cast(str, getenv("TEST_DISCORD_TOKEN")))
bot.run()

await bot.wait_ready()

await bot.index_application_commands(APPLICATION_ID_HERE)

msg = await MessageAssertionBuilder().filter_by_author(USER_ID_HERE).compile().assert_request(
            bot,
            ScheduledEventBuilder(
                GuildScheduledEventEntityType.EXTERNAL,
                PrivacyLevel.GUILD_ONLY,
                APPLICATION_ID_HERE,
                "test event - selfbot",
                "test event description - selfbot",
                datetime.now()
            ).set_location("selfbot").set_end_time(datetime.now()).compile()
        )
print(msg)
```
Auto-complete assertion is similar. This also includes an example of the deadline parameter.
```py
res = await AutoCompleteAssertionBuilder()\
            .compile().assert_request(
            bot,
            build_interaction(
                InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE,
                TEST_BOT_USER_ID_HERE,
                APPLICATION_ID_HERE,
                CHANNEL_ID_HERE,
                ApplicationCommandBuilder(
                    "cull",
                )
                .set_arg("event", "", focused=True)
                .compile()
            ), deadline=60
        )
print(res)
 ```

### Requests
Currently, the supported requests are:  `Interaction` ,  `ScheduledEvents `, and `Reaction`. All of these classes have associated builder classes/functions: `build_interaction`, `ScheduledEventBuilder`, and `build_reaction`. Once the request is built, the `send` method just needs to be called with a `Bot` class used as a parameter (the selfbot itself).

Below is an example of how to send a request using a builder function.
```py
await build_reaction("🖥️", MSG_ID_HERE, CHANNEL_ID_HERE).send(bot)
```

Below is an example of how to sdend a request using a builder class.

```py
ScheduledEventBuilder(
                GuildScheduledEventEntityType.EXTERNAL,
                PrivacyLevel.GUILD_ONLY,
                APPLICATION_ID_HERE,
                "test event - selfbot",
                "test event description - selfbot",
                datetime.now()
            ).set_location("selfbot").set_end_time(datetime.now()).compile().send(bot)
```

NOTE: interactions of type `MESSAGE_COMPONENT` are untested, this type of interaction includes interacting with a message that has a view (e.g. pressing a button, or selecting an option). The package really only focuses on  `ApplicationCommand `.

## Setup

- Create a `Bot` instance with a provided user token.
- Run the bot by using `bot.run()`
- Index the application commands ( `await bot.index_application_commands(APPLICATION_ID_HERE) `) by providing the application id (the application id of the bot you want to test) 
- Make tests and have fun or pain, idk ur pick.