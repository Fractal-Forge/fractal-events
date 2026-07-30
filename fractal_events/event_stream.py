import uuid
from dataclasses import dataclass, field
from typing import List

from fractal_events.event import BasicSendingEvent


@dataclass
class EventStream:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    events: List[BasicSendingEvent] = field(default_factory=list)
