import datetime
import json
from dataclasses import asdict

from fractal_core import EnhancedEncoder

from fractal_events.event import Event
from fractal_events.event_projector import EventProjector
from fractal_events.message import Message
from fractal_events.projectors._protocols import RecordableEvent


class PrintEventProjector(EventProjector):
    def project(self, id: str, event: Event):
        if not isinstance(event, RecordableEvent):
            # What this projector cannot do is record an event with no object
            # id — say so here rather than fail on a missing attribute
            # somewhere further in.
            raise TypeError(
                f"{type(self).__name__} projects sending events; "
                f"{type(event).__name__} has no object id to record"
            )

        message = Message(
            id=id,
            occurred_on=datetime.datetime.now(tz=datetime.timezone.utc),
            event=event.__class__.__name__,
            data=event,
            object_id=str(event.object_id),
            aggregate_root_id=str(event.aggregate_root_id),
        )
        print(json.dumps(asdict(message), cls=EnhancedEncoder))
