import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Type

from fractal_commands import Command

from fractal_events.causation import current_cause

if TYPE_CHECKING:
    # Type-only: process mappers are an optional feature and fractal-processes
    # is an optional dependency, so this must never become a runtime import.
    from fractal_processes.process import Process


@dataclass
class Event(object):
    pass


def ensure_identity(event: Any) -> Any:
    """Give `event` its identity if it has none yet, and return it.

    A fresh event gets a new ``event_id``; inside the handling of another event
    (see `fractal_events.causation`) it continues that event's chain, otherwise
    it is its own source. An event that already has an identity, because it was
    read back from an event store, keeps it untouched. Idempotent.
    """
    if not getattr(event, "event_id", ""):
        event.event_id = str(uuid.uuid4())
    if not getattr(event, "correlation_id", ""):
        cause = current_cause()
        if cause is not None:
            event.correlation_id = cause.correlation_id
            event.causation_id = (
                getattr(event, "causation_id", "") or cause.causation_id
            )
            event.depth = cause.depth
        else:
            event.correlation_id = event.event_id
    return event


@dataclass
class BasicSendingEvent(Event, ABC):
    """An event an aggregate sends.

    The four identity fields are keyword-only with defaults, so the event
    classes an application declares on top keep their own positional fields
    unchanged. They are left out of equality: two events that say the same thing
    compare equal, as they did before events had an identity. See
    `fractal_events.causation` for what they mean.
    """

    event_id: str = field(default="", kw_only=True, compare=False)
    correlation_id: str = field(default="", kw_only=True, compare=False)
    causation_id: str = field(default="", kw_only=True, compare=False)
    depth: int = field(default=0, kw_only=True, compare=False)

    def __post_init__(self):
        ensure_identity(self)

    @property
    @abstractmethod
    def object_id(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def aggregate_root_id(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def aggregate_root_type(self):
        raise NotImplementedError


@dataclass
class SendingEvent(BasicSendingEvent, ABC):
    command: Command

    @staticmethod
    def to_event(event: Any):
        return event


@dataclass
class ReceivingEvent(Event):
    def to_command(self):
        raise NotImplementedError


class EventCommandMapper(ABC):
    @abstractmethod
    def mappers(self) -> Dict[Type[Event], List[Callable[[Event], List[Command]]]]:
        raise NotImplementedError


class EventProcessMapper(ABC):
    """Maps events to Process workflows for complex orchestration with state."""

    @abstractmethod
    def mappers(self) -> Dict[Type[Event], List[Callable[[Event], "Process"]]]:
        """
        Returns mapping of Event types to Process factory functions.

        The Process factory receives an Event and returns a Process instance
        that will be executed with a ProcessContext containing fractal.context.

        Example:
            {
                HouseAddedEvent: [lambda event: create_house_workflow(event)],
                UserRegisteredEvent: [lambda event: create_user_workflow(event)],
            }

        Returns:
            Dictionary mapping Event types to lists of Process factory callables
        """
        raise NotImplementedError
