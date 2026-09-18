"""
Discord's user object.

The full profile shape. Message payloads carry a trimmed down author instead, modelled
separately as `..gateway.message.MessageAuthor`.
"""

from pydantic import BaseModel

class User(BaseModel):
	id: str
	username: str
	discriminator: str
	global_name: str | None
	avatar: str | None
	bot: bool | None = None
	system: bool | None = None
	mfa_enabled: bool
	pronouns: str | None = None
	bio: str
	banner: str | None
	accent_color: int | None
