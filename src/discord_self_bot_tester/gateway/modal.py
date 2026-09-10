from ._base import GatewayEvent
from .component import Component

class Modal(GatewayEvent):
    id: str
    nonce: str
    custom_id: str
    title: str
    # not always sent by discord, used as a fallback by ModalResponseBuilder
    application_id: str | None = None
    components: list[Component]
