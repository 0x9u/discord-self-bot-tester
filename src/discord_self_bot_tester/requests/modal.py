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
)
from ..gateway.modal import Modal

from .commands import (
    ComponentType,
    Interaction,
    ModalSubmitComponentData,
    ModalSubmitData,
    submit_modal,
)

from typing import Self, TypeAlias

# components the user can put an answer into
AnswerComponent: TypeAlias = (
    TextInputComponent
    | SelectComponent
    | FileUpload
    | RadioGroup
    | CheckboxGroup
    | Checkbox
)


def _find_label(components: list[Component], label: str) -> LabelComponent | None:
    for component in components:
        if isinstance(component, LabelComponent) and component.label == label:
            return component
        found = _find_label(child_components(component), label)
        if found is not None:
            return found
    return None

def _find_custom_id(components: list[Component], custom_id: str) -> Component | None:
    for component in components:
        if getattr(component, "custom_id", None) == custom_id:
            return component
        found = _find_custom_id(child_components(component), custom_id)
        if found is not None:
            return found
    return None

def _label_paths(components: list[Component], prefix: tuple[str, ...] = ()) -> list[str]:
    """
    Every label in the modal, nested ones written as `outer > inner`.
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

def _custom_ids(components: list[Component]) -> list[str]:
    ids: list[str] = []
    for component in components:
        custom_id = getattr(component, "custom_id", None)
        if custom_id is not None:
            ids.append(custom_id)
        ids.extend(_custom_ids(child_components(component)))
    return ids


class ModalResponseBuilder:
    """
    Builds the submit data for a modal that was received off the gateway.

    Components are picked by the label discord renders above them, which is what a
    user would click on. Every selection and every value is asserted against the
    modal we were actually given, so a renamed field or a changed component type
    fails here instead of silently submitting the wrong payload.

    modal = await ModalAssertionBuilder().compile().assert_request(bot, req)
    req = ModalResponseBuilder(modal)\
        .select("Your name").set_text("oliver")\
        .select("Favourite colour").choose("Green")\
        .compile_request(GUILD_ID, CHANNEL_ID)
    """

    modal: Modal

    # custom_id -> answer, compile walks the modal tree so insertion order is irrelevant
    _answers: dict[str, ModalSubmitComponentData]
    _selected: AnswerComponent | None
    # how the selection was written, only used for error messages
    _selected_as: str

    def __init__(self, modal: Modal):
        self.modal = modal
        self._answers = {}
        self._selected = None
        self._selected_as = ""

    def select(self, *labels: str) -> Self:
        """
        Selects the component sitting under `labels`.

        Passing more than one label walks into nested components, e.g.
        `select("Address", "Postcode")` finds the label "Address" and then looks for
        the label "Postcode" inside it.
        """
        if len(labels) == 0:
            raise AssertionError("select needs at least one label")

        scope = self.modal.components
        found: LabelComponent | None = None

        for depth, label in enumerate(labels):
            found = _find_label(scope, label)
            if found is None:
                where = "" if depth == 0 else f" under {' > '.join(labels[:depth])!r}"
                raise AssertionError(
                    f"Modal {self.modal.custom_id!r} has no component labelled {label!r}{where}"
                    f"\nAvailable labels: {_label_paths(scope)}")
            scope = child_components(found)

        assert found is not None
        self._selected_as = " > ".join(labels)
        self._select_component(found.component)
        return self

    def select_by_custom_id(self, custom_id: str) -> Self:
        """
        Selects a component by its developer defined id instead of its label.
        """
        found = _find_custom_id(self.modal.components, custom_id)
        if found is None:
            raise AssertionError(
                f"Modal {self.modal.custom_id!r} has no component with custom_id {custom_id!r}"
                f"\nAvailable custom ids: {_custom_ids(self.modal.components)}")

        self._selected_as = custom_id
        self._select_component(found)
        return self

    def set_text(self, value: str) -> Self:
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
        """
        component = self._require(RadioGroup)

        allowed = [option.value for option in component.options]
        if value not in allowed:
            raise AssertionError(
                f"Component {self._selected_as!r} has no option {value!r}"
                f"\nAvailable values: {allowed}")

        return self._answer(component, value=value)

    def set_checked(self, checked: bool = True) -> Self:
        component = self._require(Checkbox)
        return self._answer(component, value=checked)

    def choose(self, *option_labels: str) -> Self:
        """
        Answers an option bearing component by the labels discord renders for its
        options, rather than by their underlying values.
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

    def compile(self) -> ModalSubmitData:
        missing = self._missing_required()
        if len(missing) != 0:
            raise AssertionError(
                f"Modal {self.modal.custom_id!r} has required component(s) left"
                f" unanswered: {missing}")

        components = [compiled for compiled
                      in (self._compile_component(component)
                          for component in self.modal.components)
                      if compiled is not None]

        return ModalSubmitData(
            id=self.modal.id,
            custom_id=self.modal.custom_id,
            components=components
        )

    def compile_request(self, guild_id: int, channel_id: int, application_id: int | None = None) -> Interaction:
        """
        Compiles into a MODAL_SUBMIT interaction, ready to be sent or asserted on.

        `application_id` is taken off the modal payload when discord included it.
        """
        if application_id is None:
            if self.modal.application_id is None:
                raise AssertionError(
                    "Modal payload carried no application_id, pass one explicitly")
            application_id = int(self.modal.application_id)

        return submit_modal(application_id, guild_id, channel_id, self.compile())

    def _select_component(self, component: Component):
        if not isinstance(component, AnswerComponent):
            raise AssertionError(
                f"Component {self._selected_as!r} is a {type(component).__name__},"
                " which holds no value")
        self._selected = component

    def _require(self, *types: type) -> AnswerComponent:
        if self._selected is None:
            raise AssertionError("No component selected, call select() first")
        if not isinstance(self._selected, types):
            raise AssertionError(
                f"Component {self._selected_as!r} is a {type(self._selected).__name__},"
                f" expected one of: {[expected.__name__ for expected in types]}")
        return self._selected

    def _answer(self, component: AnswerComponent, value: str | bool | None = None,
                values: list[str] | None = None) -> Self:
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
        Labels of the components discord told us are required but were never answered.

        Only components explicitly marked required are checked, an absent `required`
        is treated as optional even though discord defaults it to true.
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
