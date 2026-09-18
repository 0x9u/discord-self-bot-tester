"""
Creating guild scheduled events.

Not an interaction, but a convenient way to provoke a bot that listens for them, which
is what the library's own tests use it for.
"""

from ..bot import Bot
from ._base import Request, SelfBotRequestError

from aiohttp import ClientSession

from pydantic import BaseModel, Field
from enum import Enum

from datetime import datetime

from typing import TypeAlias

# ENDPOINT URLS

SCHEDULED_EVENTS_URL = "https://discord.com/api/v9/guilds/{}/scheduled-events"

class PrivacyLevel(Enum):
    """
    Who can see a scheduled event.
    """

    PUBLIC = 1
    GUILD_ONLY = 2

class GuildScheduledEventEntityType(Enum):
    """
    Where an event takes place.

    STAGE_INSTANCE and VOICE need a `channel_id`; EXTERNAL needs a location.
    """

    STAGE_INSTANCE = 1
    VOICE = 2
    EXTERNAL = 3
    PRIME_TIME = 4


class RecurrenceRuleFrequency(Enum):
    """
    How often a recurring event repeats. Dictates which `RecurrenceRule` fields apply.
    """

    YEARLY = 0
    MONTHLY = 1
    WEEKLY = 2
    DAILY = 3


class RecurrenceRuleWeekday(Enum):
    """
    Day of the week, numbered from Monday as discord numbers them.
    """

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class RecurrenceRuleMonth(Enum):
    """
    Month of the year, numbered from one.
    """

    JANUARY = 1
    FEBRUARY = 2
    MARCH = 3
    APRIL = 4
    MAY = 5
    JUNE = 6
    JULY = 7
    AUGUST = 8
    SEPTEMBER = 9
    OCTOBER = 10
    NOVEMBER = 11
    DECEMBER = 12


class RecurrenceRuleNWeekday(BaseModel):
    """
    An nth weekday of the month, e.g. the second Tuesday.
    """

    n: int  # week to reoccur on 1-5
    day: RecurrenceRuleWeekday

# https://docs.discord.food/resources/guild-scheduled-event#guild-scheduled-event-recurrence-rule-object

# RecurrenceRule uses dateutils but it means it only
# a subset behaviour for it in the backend.

# So unfortunately, we still need to send the same request body
# to the backend.

class RecurrenceRule(BaseModel):
    """
    How a scheduled event repeats.

    Which fields may be combined is dictated by `frequency`, so prefer the
    `ScheduledEventBuilder.set_recurrence_rule_*` helpers, which only produce
    combinations discord's backend accepts.
    """

    start: datetime
    frequency: RecurrenceRuleFrequency
    interval: int
    by_weekday: list[RecurrenceRuleWeekday] | None
    by_n_weekday: list[RecurrenceRuleNWeekday] | None
    # NOTE: doesn't have by_n_weekday
    by_month: list[RecurrenceRuleMonth] | None
    by_month_day: list[int] | None


class GuildScheduledEventEntity(BaseModel):
    """
    The free text location of an EXTERNAL event.
    """

    location: str | None

# https://docs.discord.food/resources/guild-scheduled-event


class ScheduledEvent(Request):
    """
    A scheduled event to create. Build one with `ScheduledEventBuilder`.

    `guild_id` is excluded from the dump because it belongs in the URL rather than the
    body. An event is either in a voice channel (`channel_id`) or somewhere external
    (`entity_metadata.location`), never both.
    """

    guild_id : str = Field(exclude=True)
    
    name: str
    description: str
    privacy_level: PrivacyLevel
    scheduled_start_time: datetime
    scheduled_end_time: datetime | None
    entity_type: GuildScheduledEventEntityType
    recurrence_rule: RecurrenceRule | None
    channel_id: str | None
    entity_metadata: GuildScheduledEventEntity | None
    
    async def request(self, bot: Bot, session: ClientSession):        
        json = self.model_dump(mode="json", exclude_none=True)
        
        res = await session.post(SCHEDULED_EVENTS_URL.format(self.guild_id), json=json)
        if res.status != 200:
            res_data = await res.text()
            raise SelfBotRequestError("Request failed: " + str(res_data), res.status)
        

class ScheduledEventBuilder:
    """
    Assembles a `ScheduledEvent`, one chained setter at a time.

    The location and channel setters are mutually exclusive and say so, and the
    recurrence setters refuse to overwrite each other, so a contradictory event fails
    here rather than as an opaque 400 from discord.

    ScheduledEventBuilder(GuildScheduledEventEntityType.EXTERNAL,
                          PrivacyLevel.GUILD_ONLY, GUILD_ID,
                          "standup", "the daily one", datetime.now())        .set_location("the kitchen").compile()
    """

    Self: TypeAlias = 'ScheduledEventBuilder'

    data: ScheduledEvent

    def __init__(self, entity_type: GuildScheduledEventEntityType, privacy_level: PrivacyLevel, guild_id : int, name: str, description: str, scheduled_start_time: datetime):
        self.data = ScheduledEvent(
            guild_id=str(guild_id),
            name=name,
            description=description,
            privacy_level=privacy_level,
            scheduled_start_time=scheduled_start_time,
            scheduled_end_time=None,
            entity_type=entity_type,
            recurrence_rule=None,
            channel_id=None,
            entity_metadata=None
        )

    # NOTE: must be voice channel id
    def set_channel_id(self, channel_id: int) -> Self:
        if self.data.entity_metadata is not None:
            raise RuntimeError("Cannot set channel_id after setting location")

        self.data.channel_id = str(channel_id)
        return self

    def set_location(self, location: str) -> Self:
        if self.data.channel_id is not None:
            raise RuntimeError("Cannot set location after setting channel_id")

        self.data.entity_metadata = GuildScheduledEventEntity(
            location=location)
        return self

    def set_recurrence_rule_yearly(self, month: RecurrenceRuleMonth, day: int) -> Self:
        if self.data.recurrence_rule is not None:
            raise RuntimeError("Recurrence rule already set")

        self.data.recurrence_rule = RecurrenceRule(
            start=self.data.scheduled_start_time,
            frequency=RecurrenceRuleFrequency.YEARLY,
            interval=1,
            by_weekday=None,
            by_n_weekday=None,
            by_month=[month],
            by_month_day=[day]
        )

        return self

    def set_recurrence_rule_monthly(self, n_week: int, day: RecurrenceRuleWeekday) -> Self:
        if self.data.recurrence_rule is not None:
            raise RuntimeError("Recurrence rule already set")

        self.data.recurrence_rule = RecurrenceRule(
            start=self.data.scheduled_start_time,
            frequency=RecurrenceRuleFrequency.MONTHLY,
            interval=1,
            by_weekday=None,
            by_n_weekday=[RecurrenceRuleNWeekday(n=n_week, day=day)],
            by_month=None,
            by_month_day=None
        )

        return self

    def set_recurrence_rule_weekly(self, day: RecurrenceRuleWeekday, every_other_week: bool = False) -> Self:
        if self.data.recurrence_rule is not None:
            raise RuntimeError("Recurrence rule already set")

        self.data.recurrence_rule = RecurrenceRule(
            start=self.data.scheduled_start_time,
            frequency=RecurrenceRuleFrequency.WEEKLY,
            interval=2 if every_other_week else 1,
            by_weekday=[day],
            by_n_weekday=None,
            by_month=None,
            by_month_day=None
        )

        return self

    def set_recurrence_rule_daily(self, days: list[RecurrenceRuleWeekday]) -> Self:
        if self.data.recurrence_rule is not None:
            raise RuntimeError("Recurrence rule already set")

        self.data.recurrence_rule = RecurrenceRule(
            start=self.data.scheduled_start_time,
            frequency=RecurrenceRuleFrequency.DAILY,
            interval=1,
            by_weekday=days,
            by_n_weekday=None,
            by_month=None,
            by_month_day=None
        )

        return self

    def set_end_time(self, end_time: datetime) -> Self:
        self.data.scheduled_end_time = end_time
        return self

    def compile(self) -> ScheduledEvent:
        """
        The finished request. Raises if neither a channel nor a location was set.
        """
        if self.data.channel_id is None and self.data.entity_metadata is None:
            raise RuntimeError("Must set channel_id or location")

        return self.data