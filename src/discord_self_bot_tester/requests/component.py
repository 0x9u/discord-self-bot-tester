from ..gateway.component import (
    ButtonComponent,
    SelectComponent,
    StringSelectComponent,
    walk_components,
)
from ..gateway.message import Message

from .commands import (
    ComponentType,
    Interaction,
    InteractionType,
    MessageComponent,
    build_interaction,
)


def buttons_of(message: Message) -> list[ButtonComponent]:
    """
    Every button on the message, in the order discord laid them out.
    """
    return [component for component in walk_components(message.components or [])
            if isinstance(component, ButtonComponent)]

def dropdowns_of(message: Message) -> list[SelectComponent]:
    """
    Every select menu on the message, in the order discord laid them out.
    """
    return [component for component in walk_components(message.components or [])
            if isinstance(component, SelectComponent)]


def _describe_buttons(message: Message) -> list[str]:
    return [button.label if button.label is not None else f"<{button.custom_id}>"
            for button in buttons_of(message)]

def _describe_dropdowns(message: Message) -> list[str]:
    return [dropdown.placeholder if dropdown.placeholder is not None else dropdown.custom_id
            for dropdown in dropdowns_of(message)]

def _resolve_ids(message: Message, guild_id: int | None,
                 application_id: int | None) -> tuple[int, int]:
    """
    Fills in the ids the interaction needs off the message that carried the component.
    """
    if guild_id is None:
        if message.guild_id is None:
            raise AssertionError(
                f"Message {message.id} carried no guild_id, pass one explicitly")
        guild_id = int(message.guild_id)

    if application_id is None:
        # a bot's user id is its application id, so the message author will do when
        # discord did not hand us an application_id outright
        resolved = message.application_id
        if resolved is None and message.author is not None:
            resolved = message.author.id
        if resolved is None:
            raise AssertionError(
                f"Message {message.id} carried no application_id, pass one explicitly")
        application_id = int(resolved)

    return guild_id, application_id

def _build(message: Message, data: MessageComponent, guild_id: int | None,
           application_id: int | None) -> Interaction:
    guild_id, application_id = _resolve_ids(message, guild_id, application_id)

    return build_interaction(
        InteractionType.MESSAGE_COMPONENT,
        application_id,
        guild_id,
        int(message.channel_id),
        data,
        message_id=message.id,
        message_flags=message.flags
    )


def find_button(message: Message, label: str | None = None,
                custom_id: str | None = None) -> ButtonComponent:
    """
    The first button on the message matching `label` and/or `custom_id`.

    Raises if nothing matches, or if the button could not be pressed anyway.
    """
    if label is None and custom_id is None:
        raise AssertionError("find_button needs a label or a custom_id")

    matched = [button for button in buttons_of(message)
               if (label is None or button.label == label)
               and (custom_id is None or button.custom_id == custom_id)]

    if len(matched) == 0:
        wanted = label if label is not None else custom_id
        raise AssertionError(
            f"Message {message.id} has no button {wanted!r}"
            f"\nAvailable buttons: {_describe_buttons(message)}")

    button = matched[0]

    if button.disabled:
        raise AssertionError(f"Button {button.label!r} is disabled")
    if button.custom_id is None:
        raise AssertionError(
            f"Button {button.label!r} is a {button.style.name} button,"
            " it sends no interaction")

    return button

def find_dropdown(message: Message, dropdown: str | None = None) -> SelectComponent:
    """
    The select menu on the message, picked out by its placeholder or its custom_id.

    `dropdown` may be left out when the message only carries one.
    """
    dropdowns = dropdowns_of(message)

    if len(dropdowns) == 0:
        raise AssertionError(f"Message {message.id} has no dropdowns")

    if dropdown is None:
        if len(dropdowns) != 1:
            raise AssertionError(
                f"Message {message.id} has {len(dropdowns)} dropdowns, say which one"
                f"\nAvailable dropdowns: {_describe_dropdowns(message)}")
        matched = dropdowns
    else:
        matched = [candidate for candidate in dropdowns
                   if dropdown in (candidate.placeholder, candidate.custom_id)]

    if len(matched) == 0:
        raise AssertionError(
            f"Message {message.id} has no dropdown {dropdown!r}"
            f"\nAvailable dropdowns: {_describe_dropdowns(message)}")

    selected = matched[0]

    if selected.disabled:
        raise AssertionError(f"Dropdown {dropdown or selected.custom_id!r} is disabled")

    return selected


def press_button(message: Message, label: str | None = None, custom_id: str | None = None,
                 guild_id: int | None = None, application_id: int | None = None) -> Interaction:
    """
    Presses a button on `message` by the label discord renders on it.

    The channel, guild and application the interaction needs are taken off the
    message, so only the label is normally needed.

    msg = await MessageAssertionBuilder().compile().assert_request(bot, cmd)
    await MessageAssertionBuilder().filter_by_message_update().compile()\\
        .assert_request(bot, press_button(msg, "Confirm"))
    """
    button = find_button(message, label, custom_id)

    return _build(
        message,
        MessageComponent(
            custom_id=button.custom_id,
            component_type=ComponentType.BUTTON
        ),
        guild_id,
        application_id
    )

def select_dropdown(message: Message, *option_labels: str, dropdown: str | None = None,
                    guild_id: int | None = None, application_id: int | None = None) -> Interaction:
    """
    Picks options out of a string select on `message` by the labels it renders.

    `dropdown` names which select menu to use, by placeholder or custom_id, and can be
    left out when the message only carries one.
    """
    selected = find_dropdown(message, dropdown)
    named = dropdown if dropdown is not None else selected.custom_id

    if not isinstance(selected, StringSelectComponent):
        raise AssertionError(
            f"Dropdown {named!r} is a {type(selected).__name__}, its values are"
            " snowflakes rather than labelled options, use select_dropdown_values")

    values: list[str] = []
    for option_label in option_labels:
        matched = [option.value for option in selected.options
                   if option.label == option_label]
        if len(matched) == 0:
            raise AssertionError(
                f"Dropdown {named!r} has no option labelled {option_label!r}"
                f"\nAvailable option labels: {[option.label for option in selected.options]}")
        values.append(matched[0])

    return select_dropdown_values(
        message, *values, dropdown=dropdown, guild_id=guild_id, application_id=application_id)

def select_dropdown_values(message: Message, *values: str, dropdown: str | None = None,
                           guild_id: int | None = None, application_id: int | None = None) -> Interaction:
    """
    Picks raw values out of a select menu on `message`.

    Needed for the user, role, mentionable and channel selects, whose values are
    snowflakes picked out of discord's own pickers rather than labelled options.
    """
    selected = find_dropdown(message, dropdown)
    named = dropdown if dropdown is not None else selected.custom_id

    if isinstance(selected, StringSelectComponent):
        allowed = [option.value for option in selected.options]
        unknown = [value for value in values if value not in allowed]
        if len(unknown) != 0:
            raise AssertionError(
                f"Dropdown {named!r} has no option(s) {unknown}"
                f"\nAvailable values: {allowed}")

    # discord defaults both to 1 when it leaves them out
    min_values = selected.min_values if selected.min_values is not None else 1
    max_values = selected.max_values if selected.max_values is not None else 1

    if len(values) < min_values:
        raise AssertionError(
            f"Dropdown {named!r} needs at least {min_values} value(s), got {len(values)}")
    if len(values) > max_values:
        raise AssertionError(
            f"Dropdown {named!r} allows at most {max_values} value(s), got {len(values)}")

    return _build(
        message,
        MessageComponent(
            custom_id=selected.custom_id,
            component_type=ComponentType(selected.type),
            values=list(values)
        ),
        guild_id,
        application_id
    )
