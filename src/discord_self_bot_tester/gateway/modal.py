"""
The INTERACTION_MODAL_CREATE payload: a form discord opened in response to one of our
interactions.
"""

from ._base import GatewayEvent
from .component import Component

class Modal(GatewayEvent):
    """
    A modal discord asked us to fill in.

    `custom_id` and `id` are echoed back verbatim when submitting, and `components`
    describes the fields. `..requests.modal.ModalResponseBuilder` consumes this to
    build the matching MODAL_SUBMIT interaction.
    """

    id: str
    nonce: str
    custom_id: str
    title: str
    # not always sent by discord, used as a fallback by ModalResponseBuilder
    application_id: str | None = None
    components: list[Component]
