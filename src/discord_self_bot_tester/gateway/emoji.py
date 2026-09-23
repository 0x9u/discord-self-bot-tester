"""
Discord's emoji object, as it appears nested in components and reactions.
"""

from .user import User

from pydantic import BaseModel

class Emoji(BaseModel):
    id: str | None
    name: str
    roles: list[str] = []
    user: User = []
    animated: bool | None = None