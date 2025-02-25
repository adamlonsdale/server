"""Model(s) for PlayerQueue."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from mashumaro import DataClassDictMixin

from music_assistant.common.models.media_items import MediaItemType  # noqa: TCH001

from .enums import PlayerState, RepeatMode
from .queue_item import QueueItem  # noqa: TCH001


@dataclass
class PlayerQueue(DataClassDictMixin):
    """Representation of a PlayerQueue within Music Assistant."""

    queue_id: str
    active: bool
    display_name: str
    available: bool
    items: int

    shuffle_enabled: bool = False
    repeat_mode: RepeatMode = RepeatMode.OFF
    # current_index: index that is active (e.g. being played) by the player
    current_index: int | None = None
    # index_in_buffer: index that has been preloaded/buffered by the player
    index_in_buffer: int | None = None
    elapsed_time: float = 0
    elapsed_time_last_updated: float = time.time()
    state: PlayerState = PlayerState.IDLE
    current_item: QueueItem | None = None
    next_item: QueueItem | None = None
    radio_source: list[MediaItemType] = field(default_factory=list)
    announcement_in_progress: bool = False
    flow_mode: bool = False
    # flow_mode_start_index: index of the first item of the flow stream
    flow_mode_start_index: int = 0

    @property
    def corrected_elapsed_time(self) -> float:
        """Return the corrected/realtime elapsed time."""
        return self.elapsed_time + (time.time() - self.elapsed_time_last_updated)
