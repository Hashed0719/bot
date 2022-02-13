from __future__ import annotations

from enum import Enum, auto
from typing import Optional, Union

from discord import DMChannel, Embed, Message, TextChannel, Thread, User

from dataclasses import dataclass, field, replace


class Event(Enum):
    MESSAGE = auto()
    MESSAGE_EDIT = auto()


@dataclass
class FilterContext:
    # Input context
    event: Event  # The type of event
    author: User  # Who triggered the event
    channel: Union[TextChannel, Thread, DMChannel]  # The channel involved
    content: str  # What actually needs filtering
    message: Optional[Message]  # The message involved
    embeds: list = field(default_factory=list)  # Any embeds involved
    # Output context
    dm_content: str = field(default_factory=str)  # The content to DM the invoker
    dm_embed: Embed = field(default_factory=Embed)  # The embed to DM the invoker
    send_alert: bool = field(default=True)  # Whether to send an alert for the moderators
    alert_content: str = field(default_factory=str)  # The content of the alert
    alert_embeds: list = field(default_factory=list)  # Any embeds to add to the alert
    action_descriptions: list = field(default_factory=list)  # What actions were taken
    matches: list = field(default_factory=list)  # What exactly was found

    def replace(self, **changes) -> FilterContext:
        """Return a new context object replacing specified fields with new values."""
        return replace(self, **changes)
