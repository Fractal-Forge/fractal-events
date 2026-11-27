"""Which event an event came from.

Every sending event carries four identity fields (see `BasicSendingEvent`):

- ``event_id``: its own id, a ``uuid4`` given when the event is created.
- ``correlation_id``: the ``event_id`` of the event the whole chain started
  from. An event nothing caused is its own source.
- ``causation_id``: the ``event_id`` of the event whose handling created this
  one; empty for a source. Following ``causation_id`` back walks the chain.
- ``depth``: how many links there are: 0 for a source, one more per link, so a
  chain that calls itself can be cut off at a maximum depth.

The cause travels in a context variable rather than through every call: the
`CommandBusProjector` sets it while it runs the mappers and Processes for an
event, and every event created in the meantime picks it up when it is built.
Work that leaves the current context (a background job) takes the cause with
it as a dict (`Cause.to_dict`) and restores it with `caused_by(Cause.from_dict(...))`.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import Any, Iterator, Optional


@dataclass(frozen=True)
class Cause:
    """What an event created now inherits: its chain, its parent, its depth."""

    correlation_id: str
    causation_id: str
    depth: int

    @classmethod
    def of(cls, event: Any) -> Optional["Cause"]:
        """The cause for events created while handling `event`.

        None for an event without an identity (a `ReceivingEvent`, or one from
        before identities existed): there is no chain to continue.
        """
        event_id = getattr(event, "event_id", "")
        if not event_id:
            return None
        return cls(
            correlation_id=getattr(event, "correlation_id", "") or event_id,
            causation_id=event_id,
            depth=int(getattr(event, "depth", 0) or 0) + 1,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Cause":
        return cls(
            correlation_id=str(data["correlation_id"]),
            causation_id=str(data["causation_id"]),
            depth=int(data["depth"]),
        )


_current: ContextVar[Optional[Cause]] = ContextVar("fractal_events_cause", default=None)


def current_cause() -> Optional[Cause]:
    """The cause in effect here, or None outside the handling of an event."""
    return _current.get()


@contextmanager
def caused_by(source: Any) -> Iterator[Optional[Cause]]:
    """Make events created inside this block descend from `source`.

    `source` is an event (its children continue its chain) or a `Cause`
    restored from elsewhere. An event without an identity sets nothing, and the
    block runs with whatever cause was already in effect.
    """
    cause = source if isinstance(source, Cause) else Cause.of(source)
    if cause is None:
        yield current_cause()
        return
    token = _current.set(cause)
    try:
        yield cause
    finally:
        _current.reset(token)
