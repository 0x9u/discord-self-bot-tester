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
    _build_interaction,
)

def _build(message: Message, data: MessageComponent) -> Interaction:
    """
    Builds a ``MESSAGE_COMPONENT`` interaction aimed at ``message``, with its ids filled in.

    :raises AssertionError: If the message says nothing about which application sent it.
    """
    # if guild_id is None then its DM
    guild_id = int(message.guild_id) if message.guild_id is not None else None

    application_id : str
    if message.application_id is not None:
        application_id = message.application_id
    elif message.author is not None:
        application_id = message.author.id
    else:
        raise AssertionError("Message has neither an author nor an application_id")

    return _build_interaction(
        InteractionType.MESSAGE_COMPONENT,
        int(application_id),
        guild_id,
        int(message.channel_id),
        data,
        message_id=message.id,
        message_flags=message.flags
    )

def find_button(message: Message, label: str | None = None,
                custom_id: str | None = None) -> ButtonComponent:
    """
    Finds a pressable button on a message.

    :param message: The message carrying the button.
    :param label: The text discord renders on the button.
    :param custom_id: The button's developer defined id, if the label is not enough.
    :returns: The first button matching every one of ``label`` and ``custom_id`` given.
    :raises AssertionError: If neither is given, nothing matches, or the button could
        not be pressed anyway.
    """
    if label is None and custom_id is None:
        raise AssertionError("find_button needs a label or a custom_id")

    buttons = [component for component in walk_components(message.components or [])
                if isinstance(component, ButtonComponent)]

    matched = [button for button in buttons
               if (label is None or button.label == label)
               and (custom_id is None or button.custom_id == custom_id)]

    if len(matched) == 0:
        wanted = label if label is not None else custom_id
        
        repr_buttons = [button.label or f"<{button.custom_id}>" for button in buttons]
        
        raise AssertionError(
            f"Message {message.id} has no button {wanted!r}"
            f"\nAvailable buttons: {repr_buttons}")

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
    Finds a usable select menu on a message.

    :param message: The message carrying the select menu.
    :param dropdown: The menu's placeholder or custom_id. May be left out when the
        message only carries one.
    :returns: The matching select menu.
    :raises AssertionError: If nothing matches, ``dropdown`` is ambiguous, or the menu is
        disabled.
    """
    dropdowns = [component for component in walk_components(message.components or [])
            if isinstance(component, SelectComponent)]

    if len(dropdowns) == 0:
        raise AssertionError(f"Message {message.id} has no dropdowns")
    
    repr_dropdowns = [dropdown.placeholder or dropdown.custom_id for dropdown in dropdowns]

    if dropdown is None:
        if len(dropdowns) != 1:
            raise AssertionError(
                f"Message {message.id} has {len(dropdowns)} dropdowns, say which one"
                f"\nAvailable dropdowns: {repr_dropdowns}")
        matched = dropdowns
    else:
        matched = [candidate for candidate in dropdowns
                   if dropdown in (candidate.placeholder, candidate.custom_id)]

    if len(matched) == 0:
        raise AssertionError(
            f"Message {message.id} has no dropdown {dropdown!r}"
            f"\nAvailable dropdowns: {repr_dropdowns}")

    selected = matched[0]

    if selected.disabled:
        raise AssertionError(f"Dropdown {dropdown or selected.custom_id!r} is disabled")

    return selected

def press_button(message: Message, label: str | None = None, custom_id: str | None = None) -> Interaction:
    """
    Presses a button on a message by the label discord renders on it.

    The channel, guild and application the interaction needs are taken off the
    message, so only the label is normally needed. Example::

        msg = await MessageAssertionBuilder().compile().assert_request(bot, cmd)
        await MessageAssertionBuilder().filter_by_message_update().compile()\\
            .assert_request(bot, press_button(msg, "Confirm"))

    :param message: The message carrying the button.
    :param label: The text discord renders on the button.
    :param custom_id: The button's developer defined id, if the label is not enough.
    :returns: The interaction, ready to send or to hand to an assertion.
    :raises AssertionError: See :func:`find_button`.
    """
    button = find_button(message, label, custom_id)
    
    assert button.custom_id is not None

    return _build(
        message,
        MessageComponent(
            custom_id=button.custom_id,
            component_type=ComponentType.BUTTON
        )
    )

def select_dropdown(message: Message, *option_labels: str, dropdown: str | None = None) -> Interaction:
    """
    Picks options out of a string select by the labels it renders.

    :param message: The message carrying the select menu.
    :param option_labels: The labels of the options to pick.
    :param dropdown: The menu's placeholder or custom_id. May be left out when the
        message only carries one.
    :returns: The interaction, ready to send or to hand to an assertion.
    :raises AssertionError: If the menu is not a string select, an option label does
        not exist, or too few or many are picked.
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
        message, *values, dropdown=dropdown)

def select_dropdown_values(message: Message, *values: str, dropdown: str | None = None) -> Interaction:
    """
    Picks raw values out of a select menu.

    Needed for the user, role, mentionable and channel selects, whose values are
    snowflakes picked out of discord's own pickers rather than labelled options.

    :param message: The message carrying the select menu.
    :param values: The values to pick.
    :param dropdown: The menu's placeholder or custom_id. May be left out when the
        message only carries one.
    :returns: The interaction, ready to send or to hand to an assertion.
    :raises AssertionError: If a value is not one of a string select's options, or too
        few or many are picked.
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
        )
    )
