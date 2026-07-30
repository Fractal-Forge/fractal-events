from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Type

from fractal_commands import Command

if TYPE_CHECKING:
    # Type-only: process mappers are an optional feature and fractal-processes
    # is an optional dependency, so this must never become a runtime import.
    from fractal_processes.process import Process


@dataclass
class Event(object):
    pass


@dataclass
class BasicSendingEvent(Event, ABC):
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
