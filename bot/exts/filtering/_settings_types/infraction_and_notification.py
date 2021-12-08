from enum import auto, Enum
from datetime import timedelta
from typing import Any, Optional

import arrow
from discord import Colour
from discord.errors import Forbidden

import bot
from bot.constants import Channels
from bot.exts.filtering._filter_context import FilterContext
from bot.exts.filtering._settings_types.settings_entry import ActionEntry


class Infraction(Enum):
    """An enumeration of infraction types. The lower the value, the higher it is on the hierarchy."""
    BAN = auto()
    KICK = auto()
    MUTE = auto()
    VOICE_BAN = auto()
    WARNING = auto()
    WATCH = auto()
    SUPERSTAR = auto()
    NOTE = auto()
    NONE = auto()  # Allows making operations on an entry with no infraction without checking for None.

    def __bool__(self) -> bool:
        """
        Make the NONE value false-y.

        This is useful for Settings.create to evaluate whether the entry contains anything.
        """
        return self != Infraction.NONE


class InfractionAndNotification(ActionEntry):
    """
    A setting entry which specifies what infraction to issue and the notification to DM the user.

    Since a DM cannot be sent when a user is banned or kicked, these two functions need to be grouped together.
    """

    name = "infraction_and_notification"

    def __init__(self, entry_data: Any):
        super().__init__(entry_data)
        if entry_data["infraction_type"]:
            self.infraction_type = Infraction[entry_data["infraction_type"].replace(" ", "_").upper()]
        else:
            self.infraction_type = Infraction.NONE
        self.infraction_reason = entry_data["infraction_reason"]
        if entry_data["infraction_duration"] is not None:
            self.infraction_duration = float(entry_data["infraction_duration"])
        else:
            self.infraction_duration = None
        self.dm_content = entry_data["dm_content"]
        self.dm_embed = entry_data["dm_embed"]

        self._superstar = entry_data.get("superstar", None)

    async def action(self, ctx: FilterContext) -> None:
        """Add the stored pings to the alert message content."""
        dm_content = self._merge_messages(ctx.dm_content, self.dm_content)
        dm_embed = self._merge_messages(ctx.dm_embed.description, self.dm_embed)
        if dm_content or dm_embed:
            dm_content = f"Hey {ctx.author.mention}!\n{dm_content}"
            ctx.dm_embed.description = dm_embed
            if not ctx.dm_embed.colour:
                ctx.dm_embed.colour = Colour.og_blurple()

            try:
                await ctx.author.send(dm_content, embed=ctx.dm_embed)
            except Forbidden:
                await ctx.channel.send(ctx.dm_content, embed=ctx.dm_embed)
            ctx.action_descriptions.append("notified")

        msg_ctx = await bot.instance.get_context(ctx.message)
        if self._superstar:
            await msg_ctx.invoke(
                "superstar",
                ctx.author,
                arrow.utcnow() + timedelta(seconds=self._superstar[1]),
                reason=self._superstar[0]
            )
            ctx.action_descriptions.append("superstarred")

        if self.infraction_type != Infraction.NONE:
            if self.infraction_type == Infraction.BAN or not ctx.channel.guild:
                msg_ctx.channel = bot.instance.get_channel(Channels.mod_alerts)
            await msg_ctx.invoke(
                self.infraction_type.name,
                ctx.author,
                arrow.utcnow() + timedelta(seconds=self.infraction_duration),
                reason=self.infraction_reason
            )
            ctx.action_descriptions.append(self.infraction_type.name.lower())

    def __or__(self, other: ActionEntry):
        """Combines two actions of the same type. Each type of action is executed once per filter."""
        if not isinstance(other, InfractionAndNotification):
            return NotImplemented

        if self.infraction_type == Infraction.NONE:
            return other
        elif other.infraction_type == Infraction.NONE:
            return self

        entry_data = {}
        # There are two different infractions, and one of them is a superstarify
        if (
                self.infraction_type != other.infraction_type
                and (self.infraction_type.name == "SUPERSTAR" or other.infraction_type.name == "SUPERSTAR")
        ):
            superstar = self._superstar if self.infraction_type.name == "SUPERSTAR" else other._superstar
            # The non-superstar infraction might hold an additional superstar
            other_superstar = self._superstar if self._superstar else other._superstar
            other_type = self if self.infraction_type.name != "SUPERSTAR" else other
            entry_data = other_type.to_dict()
            if other_superstar:  # If there are two superstars, merge them
                entry_data["superstar"] = (
                    self._merge_messages(superstar[0], other_superstar[0]),
                    self._merge_durations(superstar[1], other_superstar[1])
                )
            else:
                entry_data["superstar"] = (superstar.infraction_reason, superstar.infraction_duration)
        else:
            if self.infraction_type != other.infraction_type:
                higher = self
                lower = other
                # Higher value is lower in the hierarchy
                if higher.infraction_type.value > lower.infraction_type.value:
                    higher, lower = lower, higher
                entry_data["infraction_type"] = higher.infraction_type.name
                entry_data["infraction_duration"] = higher.infraction_duration
            else:
                entry_data["infraction_type"] = self.infraction_type
                entry_data["infraction_duration"] = self._merge_durations(
                    self.infraction_duration, other.infraction_duration
                )
            entry_data["infraction_reason"] = self._merge_messages(self.infraction_reason, other.infraction_reason)
            entry_data["dm_content"] = self._merge_messages(self.dm_content, other.dm_content)
            entry_data["dm_embed"] = self._merge_messages(self.dm_embed, other.dm_embed)
            if self._superstar is None:
                entry_data["superstar"] = other._superstar
            elif other._superstar is None:
                entry_data["superstar"] = self._superstar
            else:
                entry_data["superstar"] = (
                    self._merge_messages(self._superstar[0], other._superstar[1]),
                    self._merge_durations(self._superstar[1], other._superstar[1])
                )

        return InfractionAndNotification(entry_data)

    @staticmethod
    def _merge_messages(message1: Optional[str], message2: Optional[str]) -> str:
        """Combine two messages into bullet points of a single message."""
        if not message1 and not message2:
            return ""
        elif not message1 or message1 == message2:
            return message2
        elif not message2:
            return message1

        if not message1.startswith("•"):
            message1 = "• " + message1
        if not message2.startswith("•"):
            message2 = "• " + message2
        return f"{message1}\n\n{message2}"

    @staticmethod
    def _merge_durations(duration1: Optional[timedelta], duration2: Optional[timedelta]) -> Optional[timedelta]:
        """Return the larger of the two durations. A None duration is interpreted as permanent."""
        if duration1 is None or duration2 is None:
            return None
        return max(duration1, duration2)
