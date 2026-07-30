from abc import ABC, abstractmethod

from fractal_events.event import Event


class EventProjector(ABC):
    @abstractmethod
    def project(self, id: str, event: Event):
        """Project the event, usually onto/into something defined in the constructor.

        Typed as ``Event`` rather than ``BasicSendingEvent`` because
        CommandBusProjector genuinely receives ``ReceivingEvent``s, which are
        not sending events at all — the narrower annotation was simply wrong
        about what reaches a projector.

        Projectors that handle only a narrower kind of event say so in their own
        signature. That narrowing is a Liskov violation: a PrintEventProjector
        cannot stand in everywhere an EventProjector is expected, because it
        reads ``object_id`` and a receiving event has none. It is marked at each
        site rather than papered over here — fixing it properly means splitting
        the projector hierarchy, which is worth doing but not while lifting this
        code out of fractal-toolkit otherwise unchanged.
        """
