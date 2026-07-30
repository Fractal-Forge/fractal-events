import datetime
import json
from dataclasses import asdict

from fractal_core import EnhancedEncoder

from fractal_events.event import SendingEvent
from fractal_events.event_projector import EventProjector
from fractal_events.message import Message


class PrintEventProjector(EventProjector):
    # Narrower than the base on purpose — see EventProjector.project.
    def project(self, id: str, event: SendingEvent):  # type: ignore[override]
        message = Message(
            id=id,
            occurred_on=datetime.datetime.now(tz=datetime.timezone.utc),
            event=event.__class__.__name__,
            data=event,
            object_id=str(event.object_id),
            aggregate_root_id=str(event.aggregate_root_id),
        )
        print(json.dumps(asdict(message), cls=EnhancedEncoder))
