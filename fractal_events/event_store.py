import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime, timezone
from json import JSONEncoder
from typing import List, Optional, Type

from fractal_core import DomainException
from fractal_repositories.core.repositories import Repository
from fractal_repositories.mixins.inmemory_repository_mixin import (
    InMemoryRepositoryMixin,
)
from fractal_specifications.generic.specification import Specification

from fractal_events.event import BasicSendingEvent, ensure_identity
from fractal_events.event_stream import EventStream
from fractal_events.message import Message


class EventNotMappedError(DomainException):
    code = "EVENT_NOT_MAPPED_ERROR"
    status_code = 501

    def __init__(self, event: str):
        super(EventNotMappedError, self).__init__(
            f"Event '{event}' is not mapped to be loaded from the EventStore.",
        )


def _message_id(event) -> str:
    """The event's own id, so a message and the live event share one key."""
    return ensure_identity(event).event_id or str(uuid.uuid4())


def _with_identity(event_class, data: dict, message: Message) -> dict:
    """Stored event data, with an identity for events stored before they had one.

    Such an event gets its message id as its own id and is its own source, so it
    reads back the same on every replay instead of a fresh random id each time.
    Only for event classes that have the identity fields (`BasicSendingEvent`).
    """
    if not (
        is_dataclass(event_class)
        and "event_id" in {f.name for f in fields(event_class)}
    ):
        return data
    if not data.get("event_id"):
        data = {**data, "event_id": message.id}
    if not data.get("correlation_id"):
        data = {**data, "correlation_id": data["event_id"]}
    return data


def _restore_identity(event, message: Message):
    """The same, for an event object read back whole (object or pickle stores)."""
    if not getattr(event, "event_id", ""):
        event.event_id = message.id
    if not getattr(event, "correlation_id", ""):
        event.correlation_id = event.event_id
    if not hasattr(event, "causation_id"):
        event.causation_id = ""
    if not hasattr(event, "depth"):
        event.depth = 0
    return event


class EventStore(ABC):
    @abstractmethod
    def commit(self, event_stream: EventStream, aggregate: str, version: int):
        raise NotImplementedError

    @abstractmethod
    def get_event_stream(self) -> EventStream:
        raise NotImplementedError

    @abstractmethod
    def is_healthy(self) -> bool:
        raise NotImplementedError


class EventStoreRepository(Repository[Message], ABC):
    # fractal-repositories annotates `entity` as an instance while every
    # repository in practice assigns the class. Upstream annotation, not ours.
    entity = Message  # type: ignore[assignment]
    order_by = "occurred_on"


class InMemoryEventStoreRepository(
    EventStoreRepository, InMemoryRepositoryMixin[Message]
):
    pass


class BasicEventStore(EventStore, ABC):
    def __init__(self, event_store_repository: EventStoreRepository):
        self.event_store_repository = event_store_repository

    def is_healthy(self) -> bool:
        return self.event_store_repository.is_healthy()


class ObjectEventStore(BasicEventStore):
    def commit(self, event_stream: EventStream, aggregate: str, version: int):
        for event in event_stream.events:
            self.event_store_repository.add(
                Message(
                    id=_message_id(event),
                    occurred_on=datetime.now(timezone.utc),
                    event=event.__class__.__name__,
                    data=event,
                    object_id=event.object_id,
                    aggregate_root_id=event.aggregate_root_id,
                )
            )

    def get_event_stream(
        self, specification: Optional[Specification] = None
    ) -> EventStream:
        return EventStream(
            events=[
                _restore_identity(m.data, m)
                for m in self.event_store_repository.find(specification)
            ]
        )


class DictEventStore(BasicEventStore):
    def __init__(
        self,
        event_store_repository: EventStoreRepository,
        events: List[Type[BasicSendingEvent]],
    ):
        super(DictEventStore, self).__init__(event_store_repository)
        self.events = {e.__name__: e for e in events}

    def commit(self, event_stream: EventStream, aggregate: str, version: int):
        for event in event_stream.events:
            self.event_store_repository.add(
                Message(
                    id=_message_id(event),
                    occurred_on=datetime.now(timezone.utc),
                    event=event.__class__.__name__,
                    data=asdict(event),
                    object_id=event.object_id,
                    aggregate_root_id=event.aggregate_root_id,
                )
            )

    def get_event_stream(
        self, specification: Optional[Specification] = None
    ) -> EventStream:
        events = []
        for m in self.event_store_repository.find(specification):
            if event := self.events.get(m.event, None):
                events.append(event(**_with_identity(event, m.data, m)))
            else:
                raise EventNotMappedError(m.event)
        return EventStream(events=events)


class JsonEventStore(BasicEventStore):
    def __init__(
        self,
        event_store_repository: EventStoreRepository,
        events: List[Type[BasicSendingEvent]],
        json_encoder: Optional[Type[JSONEncoder]] = None,
    ):
        super(JsonEventStore, self).__init__(event_store_repository)
        self.events = {e.__name__: e for e in events}
        self.json_encoder = json_encoder

    def commit(self, event_stream: EventStream, aggregate: str, version: int):
        import json

        for event in event_stream.events:
            self.event_store_repository.add(
                Message(
                    id=_message_id(event),
                    occurred_on=datetime.now(timezone.utc),
                    event=event.__class__.__name__,
                    data=json.dumps(asdict(event), cls=self.json_encoder),
                    object_id=event.object_id,
                    aggregate_root_id=event.aggregate_root_id,
                )
            )

    def get_event_stream(
        self, specification: Optional[Specification] = None
    ) -> EventStream:
        import json

        events = []
        for m in self.event_store_repository.find(specification):
            if event := self.events.get(m.event, None):
                events.append(event(**_with_identity(event, json.loads(m.data), m)))
            else:
                raise EventNotMappedError(m.event)
        return EventStream(events=events)


class PickleEventStore(BasicEventStore):
    def __init__(
        self,
        event_store_repository: EventStoreRepository,
        events: List[Type[BasicSendingEvent]],
    ):
        super(PickleEventStore, self).__init__(event_store_repository)
        self.events = {e.__name__: e for e in events}

    def commit(self, event_stream: EventStream, aggregate: str, version: int):
        import pickle

        for event in event_stream.events:
            self.event_store_repository.add(
                Message(
                    id=_message_id(event),
                    occurred_on=datetime.now(timezone.utc),
                    event=event.__class__.__name__,
                    data=pickle.dumps(event),
                    object_id=event.object_id,
                    aggregate_root_id=event.aggregate_root_id,
                )
            )

    def get_event_stream(
        self, specification: Optional[Specification] = None
    ) -> EventStream:
        import pickle

        events = []
        for m in self.event_store_repository.find(specification):
            events.append(_restore_identity(pickle.loads(m.data), m))
        return EventStream(events=events)
