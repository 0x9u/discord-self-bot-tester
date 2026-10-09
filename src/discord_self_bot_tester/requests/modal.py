from types import UnionType

from ..gateway.component import (
    ActionRowComponent,
    Checkbox,
    CheckboxGroup,
    Component,
    FileUpload,
    LabelComponent,
    RadioGroup,
    SelectComponent,
    StringSelectComponent,
    TextInputComponent,
    child_components,
    walk_components,
)
from ..gateway.modal import Modal

from .commands import (
    ComponentType,
    Interaction,
    ModalSubmitComponentData,
    ModalSubmitData,
    InteractionType,
    _build_interaction
)

from typing import Self, TypeAlias, cast, get_args

# components the user can put an answer into
AnswerComponent: TypeAlias = (
    TextInputComponent
    | SelectComponent
    | FileUpload
    | RadioGroup
    | CheckboxGroup
    | Checkbox
)

def _label_paths(components: list[Component], prefix: tuple[str, ...] = ()) -> list[str]:
    """
    Lists every label in the modal, for error messages.

    :returns: The labels, nested ones written as ``outer > inner``.
    """
    paths: list[str] = []
    for component in components:
        if isinstance(component, LabelComponent):
            path = prefix + (component.label,)
            paths.append(" > ".join(path))
            paths.extend(_label_paths(child_components(component), path))
        else:
            paths.extend(_label_paths(child_components(component), prefix))
    return paths


class ModalResponseBuilder:
    """
    Builds the submit data for a modal that was received off the gateway.

    Components are picked by the label discord renders above them, which is what a
    user would click on. Every selection and every value is asserted against the
    modal we were actually given, so a renamed field or a changed component type
    fails here instead of silently submitting the wrong payload. Example::

        modal = await ModalAssertionBuilder().compile().assert_request(bot, req)
        req = ModalResponseBuilder(modal)\\
            .select("Your name").set_text("oliver")\\
            .select("Favourite colour").choose("Green")\\
            .compile(GUILD_ID, CHANNEL_ID)

    Every setter raises :class:`AssertionError` if no component is selected, the
    selected component is the wrong kind for it, or the value would not be accepted.
    """

    modal: Modal

    # custom_id -> answer
    _answers: dict[str, ModalSubmitComponentData]
    _selected: AnswerComponent | None
    # how the selection was written, only used for error messages
    _selected_as: str

    def __init__(self, modal: Modal):
        """
        :param modal: The modal to answer, as returned by
            :meth:`ModalAssertion.assert_request <discord_self_bot_tester.assertions.modal.ModalAssertion.assert_request>`.
        """
        self.modal = modal
        self._answers = {}
        self._selected = None
        self._selected_as = ""

    def select(self, *labels: str) -> Self:
        """
        Selects a component by its label, and aims the setters at it.

        :param labels: The label's caption. Passing more than one walks into nested
            components, e.g. ``select("Address", "Postcode")`` finds the label
            "Address" and then looks for the label "Postcode" inside it.
        :returns: This builder.
        :raises AssertionError: If a label does not exist, or the component under it
            holds no value.
        """
        if len(labels) == 0:
            raise AssertionError("select needs at least one label")

        scope = self.modal.components
        found: LabelComponent | TextInputComponent | None = None

        for depth, label in enumerate(labels):
            found = next((component for component in walk_components(scope)
                          if isinstance(component, (LabelComponent, TextInputComponent))
                          and component.label == label), None)
            if found is None:
                where = "" if depth == 0 else f" under {' > '.join(labels[:depth])!r}"
                raise AssertionError(
                    f"Modal {self.modal.custom_id!r} has no component labelled {label!r}{where}"
                    f"\nAvailable labels: {_label_paths(scope)}")
            scope = child_components(found)

        assert found is not None
        self._selected_as = " > ".join(labels)
        self._select_component(found if isinstance(found, TextInputComponent) else found.component)
        return self
    
    def select_by_custom_id(self, custom_id: str) -> Self:
        """
        Selects a component by its developer defined id instead of its label.

        :param custom_id: The component's custom_id.
        :returns: This builder.
        :raises AssertionError: If no component has that id, or it holds no value.
        """
        components = list(walk_components(self.modal.components))
        custom_ids = [getattr(component, "custom_id", None) for component in components]
        if custom_id not in custom_ids:
            raise AssertionError(
                f"Modal {self.modal.custom_id!r} has no component with custom_id {custom_id!r}"
                f"\nAvailable custom ids: {[id for id in custom_ids if id is not None]}")
        found = components[custom_ids.index(custom_id)]

        self._selected_as = custom_id
        self._select_component(found)
        return self

    def set_text(self, value: str) -> Self:
        """
        Answers a text input.

        :param value: The text to enter, within the input's length limits.
        :returns: This builder.
        """
        component = self._require(TextInputComponent)
        
        if component.min_length is not None and len(value) < component.min_length:
            raise AssertionError(
                f"Component {self._selected_as!r} needs at least {component.min_length}"
                f" characters, got {len(value)}")
        if component.max_length is not None and len(value) > component.max_length:
            raise AssertionError(
                f"Component {self._selected_as!r} allows at most {component.max_length}"
                f" characters, got {len(value)}")

        return self._answer(component, value=value)

    def set_values(self, *values: str) -> Self:
        """
        Answers a select menu, a checkbox group or a file upload with raw values.

        .. note:: To attach files to a
            :class:`~discord_self_bot_tester.gateway.component.FileUpload`, upload
            each one first with an
            :class:`~discord_self_bot_tester.requests.attachments.Attachment` and pass
            its
            :meth:`~discord_self_bot_tester.requests.attachments.Attachment.get_attachment_id`
            as the value.

        :param values: The values to submit, within the component's min and max.
        :returns: This builder.
        """
        component = self._require(SelectComponent, CheckboxGroup, FileUpload)

        if isinstance(component, (StringSelectComponent, CheckboxGroup)):
            allowed = [option.value for option in component.options]
            unknown = [value for value in values if value not in allowed]
            if len(unknown) != 0:
                raise AssertionError(
                    f"Component {self._selected_as!r} has no option(s) {unknown}"
                    f"\nAvailable values: {allowed}")

        if component.min_values is not None and len(values) < component.min_values:
            raise AssertionError(
                f"Component {self._selected_as!r} needs at least {component.min_values}"
                f" value(s), got {len(values)}")
        if component.max_values is not None and len(values) > component.max_values:
            raise AssertionError(
                f"Component {self._selected_as!r} allows at most {component.max_values}"
                f" value(s), got {len(values)}")

        return self._answer(component, values=list(values))

    def set_option(self, value: str) -> Self:
        """
        Answers a radio group with a raw option value.

        :param value: The value of the option to pick.
        :returns: This builder.
        """
        component = self._require(RadioGroup)

        allowed = [option.value for option in component.options]
        if value not in allowed:
            raise AssertionError(
                f"Component {self._selected_as!r} has no option {value!r}"
                f"\nAvailable values: {allowed}")

        return self._answer(component, value=value)

    def set_checked(self, checked: bool = True) -> Self:
        """
        Answers a single checkbox.

        :param checked: Whether to tick it.
        :returns: This builder.
        """
        component = self._require(Checkbox)
        return self._answer(component, value=checked)

    def choose(self, *option_labels: str) -> Self:
        """
        Answers a string select, radio group or checkbox group by the labels discord
        renders for its options, rather than by their underlying values.

        :param option_labels: The labels of the options to pick. Exactly one for a
            radio group.
        :returns: This builder.
        """
        component = self._require(StringSelectComponent, RadioGroup, CheckboxGroup)

        values: list[str] = []
        for option_label in option_labels:
            matched = [option.value for option in component.options
                       if option.label == option_label]
            if len(matched) == 0:
                raise AssertionError(
                    f"Component {self._selected_as!r} has no option labelled {option_label!r}"
                    f"\nAvailable option labels: {[option.label for option in component.options]}")
            values.append(matched[0])

        if isinstance(component, RadioGroup):
            if len(values) != 1:
                raise AssertionError(
                    f"Component {self._selected_as!r} is a radio group and takes exactly"
                    f" one option, got {len(values)}")
            return self.set_option(values[0])

        return self.set_values(*values)

    def compile(self, guild_id: int, channel_id: int, application_id: int | None = None) -> Interaction:
        """
        Compiles into a ``MODAL_SUBMIT`` interaction.

        :param guild_id: The guild the modal was opened in.
        :param channel_id: The channel the modal was opened in.
        :param application_id: Taken off the modal payload when discord included it,
            and has to be passed explicitly when it did not.
        :returns: The interaction, ready to send or to hand to an assertion.
        :raises AssertionError: If no application id is known, or any component
            discord marked required was never answered, so a modal that gained a field
            fails here rather than being submitted incomplete.
        """
        
        # https://docs.discord.food/interactions/receiving-and-responding#modal-submit-data-structure
        
        if application_id is None:
            if self.modal.application_id is None:
                raise AssertionError(
                    "Modal payload carried no application_id, pass one explicitly")
            application_id = int(self.modal.application_id)
        
        missing = self._missing_required()
        if len(missing) != 0:
            raise AssertionError(
                f"Modal {self.modal.custom_id!r} has required component(s) left"
                f" unanswered: {missing}")

        components = [compiled for compiled
                        in (self._compile_component(component)
                            for component in self.modal.components)
                        if compiled is not None]

        return _build_interaction(
            InteractionType.MODAL_SUBMIT,
            application_id,
            guild_id,
            channel_id,
            ModalSubmitData(
                id=self.modal.id,
                custom_id=self.modal.custom_id,
                components=components
            )
        )

    def _select_component(self, component: Component):
        """
        Points the setters at ``component``.

        :raises AssertionError: If it holds no value.
        """
        if not isinstance(component, AnswerComponent):
            raise AssertionError(
                f"Component {self._selected_as!r} is a {type(component).__name__},"
                " which holds no value")
        self._selected = component

    def _require[T](self, *types: type[T] | UnionType) -> T:
        """
        Checks the selected component is the right kind for a setter. This is what
        stops :meth:`set_text` being used on a dropdown, and so on.

        :param types: The component classes, or unions of them, the setter accepts.
        :returns: The selected component.
        :raises AssertionError: If nothing is selected, or it is none of ``types``.
        """
        if self._selected is None:
            raise AssertionError("No component selected, call select() first")
        
        flat_types = tuple(arg for t in types for arg in ((t,) if isinstance(t, type) else get_args(t)))

        if not isinstance(self._selected, flat_types):
            raise AssertionError(
                f"Component {self._selected_as!r} is a {type(self._selected).__name__},"
                f" expected one of: {[expected.__name__ for expected in flat_types]}")
        
        return cast(T, self._selected)

    def _answer(self, component: AnswerComponent, value: str | bool | None = None,
                values: list[str] | None = None) -> Self:
        """
        Records an answer against the component's custom_id.

        Answering the same component twice replaces the earlier answer.
        """
        self._answers[component.custom_id] = ModalSubmitComponentData(
            type=ComponentType(component.type),
            id=component.id,
            custom_id=component.custom_id,
            value=value,
            values=values
        )
        return self

    def _missing_required(self) -> list[str]:
        """
        Finds the components discord told us are required but were never answered.

        Only components explicitly marked required are checked, an absent ``required``
        is treated as optional even though discord defaults it to true.

        :returns: Their labels, or custom_ids where they have no label.
        """
        missing: list[str] = []

        def walk(components: list[Component], label: str):
            for component in components:
                if isinstance(component, LabelComponent):
                    label = component.label
                elif isinstance(component, AnswerComponent) \
                        and getattr(component, "required", None) is True \
                        and component.custom_id not in self._answers:
                    missing.append(label if label != "" else component.custom_id)
                walk(child_components(component), label)

        walk(self.modal.components, "")
        return missing

    def _compile_component(self, component: Component) -> ModalSubmitComponentData | None:
        """
        Mirrors the modal's own layout, dropping the branches holding no answer.
        """
        if isinstance(component, ActionRowComponent):
            inner = [compiled for compiled
                     in (self._compile_component(child)
                         for child in component.components)
                     if compiled is not None]
            if len(inner) == 0:
                return None
            return ModalSubmitComponentData(
                type=ComponentType.ACTION_ROW,
                id=component.id,
                components=inner
            )

        if isinstance(component, LabelComponent):
            inner = self._compile_component(component.component)
            if inner is None:
                return None
            return ModalSubmitComponentData(
                type=ComponentType.LABEL,
                id=component.id,
                component=inner
            )

        custom_id = getattr(component, "custom_id", None)
        if custom_id is None:
            return None

        return self._answers.get(custom_id)
