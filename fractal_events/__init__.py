"""
Fractal Events

Event sourcing for the Fractal stack: events, the publisher that fans them out
to projectors, an event store to keep them in, and the projectors that print
them, persist them, or turn them back into commands.

Sits on fractal-core and fractal-commands and imports nothing above itself.
Process mappers need fractal-processes, which is optional and imported only
when one actually fires.
"""

from fractal_events.event import (
    BasicSendingEvent,
    Event,
    EventCommandMapper,
    EventProcessMapper,
    ReceivingEvent,
    SendingEvent,
)
from fractal_events.event_projector import EventProjector
from fractal_events.event_publisher import EventPublisher
from fractal_events.event_store import (
    BasicEventStore,
    DictEventStore,
    EventNotMappedError,
    EventStore,
    EventStoreRepository,
    InMemoryEventStoreRepository,
    JsonEventStore,
    ObjectEventStore,
    PickleEventStore,
)
from fractal_events.event_stream import EventStream
from fractal_events.message import Message
from fractal_events.projectors.command_bus_projector import CommandBusProjector
from fractal_events.projectors.event_store_projector import EventStoreProjector
from fractal_events.projectors.print_projector import PrintEventProjector

__version__ = "1.1.0"

__all__ = [
    "BasicEventStore",
    "BasicSendingEvent",
    "CommandBusProjector",
    "DictEventStore",
    "Event",
    "EventCommandMapper",
    "EventNotMappedError",
    "EventProcessMapper",
    "EventProjector",
    "EventPublisher",
    "EventStore",
    "EventStoreProjector",
    "EventStoreRepository",
    "EventStream",
    "InMemoryEventStoreRepository",
    "JsonEventStore",
    "Message",
    "ObjectEventStore",
    "PickleEventStore",
    "PrintEventProjector",
    "ReceivingEvent",
    "SendingEvent",
]
