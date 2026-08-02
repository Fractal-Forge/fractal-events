from abc import ABC, abstractmethod

from fractal_events.event import Event


class EventProjector(ABC):
    @abstractmethod
    def project(self, id: str, event: Event):
        """Project the event, usually onto/into something defined in the constructor.

        Takes any ``Event``, and every projector's signature says the same.
        That is deliberate: CommandBusProjector genuinely receives
        ``ReceivingEvent``s, which are not sending events at all, so a
        projector cannot promise to accept only the narrower kind and still
        stand in wherever an EventProjector is expected.

        Projectors that need more than a bare Event — an object id to record,
        say — check for it and raise, rather than narrowing their parameter.
        Narrowing merely moves the problem into the type system, where it reads
        as a Liskov violation and gets silenced with an ignore comment; the
        check says the same thing at the only moment it can be true or false.
        """
