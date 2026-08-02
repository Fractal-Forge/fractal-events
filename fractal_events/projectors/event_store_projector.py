import uuid
from typing import cast

from fractal_events.event import BasicSendingEvent, Event
from fractal_events.event_projector import EventProjector
from fractal_events.event_store import EventStore
from fractal_events.event_stream import EventStream
from fractal_events.projectors._protocols import RecordableEvent


class EventStoreProjector(EventProjector):
    def __init__(self, event_store: EventStore):
        self.event_store = event_store

    def project(self, id: str, event: Event):
        if not isinstance(event, RecordableEvent):
            # What this projector cannot do is record an event with no object
            # id — say so here rather than fail on a missing attribute
            # somewhere further in.
            raise TypeError(
                f"{type(self).__name__} projects sending events; "
                f"{type(event).__name__} has no object id to record"
            )

        self.event_store.commit(
            # EventStream annotates its events nominally, as BasicSendingEvent,
            # while the stores have always accepted anything of the right
            # shape. The check above established that shape; the cast says so
            # without narrowing this method's parameter, which is what the
            # Liskov violation was.
            EventStream(id=str(uuid.uuid4()), events=[cast(BasicSendingEvent, event)]),
            aggregate="",
            version=1,
        )
