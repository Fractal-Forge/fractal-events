from typing import List

from fractal_events.event import BasicSendingEvent, ensure_identity
from fractal_events.event_projector import EventProjector
from fractal_events.event_stream import EventStream


class EventPublisher:
    def __init__(self, projectors: List[EventProjector]):
        self.projectors = projectors

    def publish_event(self, event: BasicSendingEvent):
        self._publish(
            EventStream(
                events=[
                    event,
                ]
            )
        )

    def publish_events(self, events: List[BasicSendingEvent]):
        self._publish(
            EventStream(
                events=events,
            )
        )

    def _publish(self, event_stream: EventStream):
        for event in event_stream.events:
            # Normally done when the event was built; repeated here for an event
            # class whose own __post_init__ does not call the base one.
            ensure_identity(event)
            for projector in self.projectors:
                projector.project(event_stream.id, event)
