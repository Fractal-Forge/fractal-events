import json
from dataclasses import dataclass

import pytest
from fractal_commands import Command
from fractal_core import DomainException, EnhancedEncoder
from fractal_specifications.generic.operators import EqualsSpecification

from fractal_events import (
    DictEventStore,
    EventNotMappedError,
    EventStoreProjector,
    EventStream,
    InMemoryEventStoreRepository,
    JsonEventStore,
    ObjectEventStore,
    PickleEventStore,
)


@dataclass
class RoadAdded(Command):
    road_id: str = "1"


@dataclass
class RoadEvent:
    road_id: str

    @property
    def object_id(self):
        return self.road_id

    @property
    def aggregate_root_id(self):
        return self.road_id

    @property
    def aggregate_root_type(self):
        return "Road"


def repo():
    return InMemoryEventStoreRepository()


def test_object_store_round_trips_the_event_itself():
    store = ObjectEventStore(repo())
    event = RoadEvent("1")

    store.commit(EventStream(events=[event]), aggregate="Road", version=1)

    assert store.get_event_stream().events == [event]


def test_dict_store_round_trips_through_a_dict():
    store = DictEventStore(repo(), events=[RoadEvent])

    store.commit(EventStream(events=[RoadEvent("1")]), aggregate="Road", version=1)

    assert store.get_event_stream().events == [RoadEvent("1")]


def test_json_store_round_trips_through_a_string():
    store = JsonEventStore(repo(), events=[RoadEvent], json_encoder=EnhancedEncoder)

    store.commit(EventStream(events=[RoadEvent("1")]), aggregate="Road", version=1)

    assert store.get_event_stream().events == [RoadEvent("1")]


def test_pickle_store_round_trips():
    store = PickleEventStore(repo(), events=[RoadEvent])

    store.commit(EventStream(events=[RoadEvent("1")]), aggregate="Road", version=1)

    assert store.get_event_stream().events == [RoadEvent("1")]


def test_an_unknown_event_type_is_reported_not_guessed():
    """A stored event whose class is no longer mapped must not be skipped."""
    store = DictEventStore(repo(), events=[])
    ObjectEventStore(store.event_store_repository).commit(
        EventStream(events=[RoadEvent("1")]), aggregate="Road", version=1
    )

    with pytest.raises(EventNotMappedError, match="RoadEvent"):
        store.get_event_stream()


def test_event_not_mapped_is_a_domain_exception_with_a_status():
    exc = EventNotMappedError("RoadEvent")

    assert isinstance(exc, DomainException)
    assert (exc.code, exc.status_code) == ("EVENT_NOT_MAPPED_ERROR", 501)


def test_get_event_stream_can_be_filtered():
    store = ObjectEventStore(repo())
    store.commit(
        EventStream(events=[RoadEvent("1"), RoadEvent("2")]),
        aggregate="Road",
        version=1,
    )

    found = store.get_event_stream(EqualsSpecification("object_id", "2")).events

    assert found == [RoadEvent("2")]


def test_stored_messages_are_ordered_by_when_they_happened():
    store = ObjectEventStore(repo())

    store.commit(EventStream(events=[RoadEvent("1")]), aggregate="Road", version=1)
    store.commit(EventStream(events=[RoadEvent("2")]), aggregate="Road", version=1)

    assert [e.road_id for e in store.get_event_stream().events] == ["1", "2"]


def test_a_healthy_repository_makes_a_healthy_store():
    assert ObjectEventStore(repo()).is_healthy()


def test_the_event_store_projector_commits_what_it_is_given():
    store = ObjectEventStore(repo())

    EventStoreProjector(store).project("s1", RoadEvent("1"))

    assert store.get_event_stream().events == [RoadEvent("1")]


def test_messages_survive_the_enhanced_encoder():
    """The print projector serialises a Message; make sure that is possible."""
    store = ObjectEventStore(repo())
    store.commit(EventStream(events=[RoadEvent("1")]), aggregate="Road", version=1)

    message = list(store.event_store_repository.find())[0]

    assert json.loads(json.dumps(message.__dict__, cls=EnhancedEncoder))["event"] == (
        "RoadEvent"
    )


def test_json_store_also_reports_an_unknown_event_type():
    store = JsonEventStore(repo(), events=[], json_encoder=EnhancedEncoder)
    JsonEventStore(
        store.event_store_repository, events=[RoadEvent], json_encoder=EnhancedEncoder
    ).commit(EventStream(events=[RoadEvent("1")]), aggregate="Road", version=1)

    with pytest.raises(EventNotMappedError, match="RoadEvent"):
        store.get_event_stream()


def test_to_event_passes_an_event_through_unchanged():
    """The SendingEvent hook subclasses override to translate an external
    payload; the default is the identity."""
    from fractal_events import SendingEvent

    event = RoadEvent("1")
    assert SendingEvent.to_event(event) is event
