import uuid

from fractal_events.event import SendingEvent
from fractal_events.event_projector import EventProjector
from fractal_events.event_store import EventStore
from fractal_events.event_stream import EventStream


class EventStoreProjector(EventProjector):
    def __init__(self, event_store: EventStore):
        self.event_store = event_store

    # Narrower than the base on purpose — see EventProjector.project.
    def project(self, id: str, event: SendingEvent):  # type: ignore[override]
        self.event_store.commit(
            EventStream(id=str(uuid.uuid4()), events=[event]), aggregate="", version=1
        )
