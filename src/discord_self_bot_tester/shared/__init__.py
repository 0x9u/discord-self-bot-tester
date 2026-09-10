from .emoji import Emoji
from .user import User

# TODO: name this better, and try reorganise
"""
the purpose of this submodule is for shared schemas used
across gateway and requests (e.g. Emoji Object).
"""

__all__ = [
    "Emoji",
    "User"
]
