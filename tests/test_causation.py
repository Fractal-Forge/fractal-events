"""Every event has its own id, and knows the event it came from.

correlation_id is always the source of the chain, causation_id the event right
before it, depth the number of links. See fractal_events.causation.
"""

import pickle
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import pytest
from fractal_commands import Command, CommandBus, CommandHandler
from fractal_core import EnhancedEncoder

from fractal_events import (
    BasicSendingEvent,
    Cause,
    CommandBusProjector,
    DictEventStore,
    EventCommandMapper,
    EventProcessMapper,
    EventPublisher,
    EventStream,
    InMemoryEventStoreRepository,
    JsonEventStore,
    Message,
    ObjectEventStore,
    PickleEventStore,
    ReceivingEvent,
    caused_by,
    current_cause,
)


@dataclass
class PartyEvent(BasicSendingEvent):
    """Shaped like the event classes the generator writes: positional fields."""

    id: str
    by: str
    on: datetime
    account_id: str
    data: dict = field(default_factory=dict)

    @property
    def object_id(self):
        return self.id

    @property
    def aggregate_root_id(self):
        return self.id

    @property
    def aggregate_root_type(self):
        return "Party"


@dataclass
class PartyOpened(PartyEvent): ...


@dataclass
class GuestJoined(PartyEvent): ...


@dataclass
class MetricRecorded(PartyEvent): ...


def opened(party_id="p1", **kwargs) -> PartyOpened:
    return PartyOpened(party_id, "anne", datetime.now(timezone.utc), "acc", **kwargs)


# -- identity of a single event ---------------------------------------------------


def test_a_fresh_event_has_an_id_and_is_its_own_source():
    event = opened()
    assert len(event.event_id) == 36
    assert event.correlation_id == event.event_id
    assert event.causation_id == ""
    assert event.depth == 0


def test_two_events_get_different_ids():
    assert opened().event_id != opened().event_id


def test_generated_event_classes_keep_their_positional_fields():
    event = PartyOpened(
        "p1", "anne", datetime(2026, 11, 27, tzinfo=timezone.utc), "acc"
    )
    assert (event.id, event.by, event.account_id, event.data) == (
        "p1",
        "anne",
        "acc",
        {},
    )


def test_identity_is_left_out_of_equality():
    on = datetime(2026, 11, 27, tzinfo=timezone.utc)
    assert PartyOpened("p1", "anne", on, "acc") == PartyOpened("p1", "anne", on, "acc")


def test_an_identity_given_explicitly_is_kept():
    event = opened(event_id="e1", correlation_id="c1", causation_id="x1", depth=3)
    assert (event.event_id, event.correlation_id, event.causation_id, event.depth) == (
        "e1",
        "c1",
        "x1",
        3,
    )


# -- the chain ----------------------------------------------------------------------


def test_an_event_created_while_handling_another_continues_its_chain():
    source = opened()
    with caused_by(source):
        child = GuestJoined("p1", "sam", datetime.now(timezone.utc), "acc")
        with caused_by(child):
            grandchild = MetricRecorded(
                "p1", "system", datetime.now(timezone.utc), "acc"
            )

    assert child.correlation_id == source.event_id
    assert child.causation_id == source.event_id
    assert child.depth == 1
    assert grandchild.correlation_id == source.event_id  # always the source
    assert grandchild.causation_id == child.event_id  # the event right before
    assert grandchild.depth == 2


def test_the_cause_is_gone_after_the_block():
    with caused_by(opened()):
        assert current_cause() is not None
    assert current_cause() is None
    assert opened().depth == 0


def test_an_event_without_identity_sets_no_cause():
    @dataclass
    class Incoming(ReceivingEvent):
        pass

    with caused_by(Incoming()) as cause:
        assert cause is None
        assert opened().causation_id == ""


def test_a_cause_survives_a_trip_through_a_background_job():
    source = opened()
    with caused_by(source):
        stored = current_cause().to_dict()  # what a BackgroundJob keeps

    # Later, in the worker: no cause in effect until it is restored.
    assert current_cause() is None
    with caused_by(Cause.from_dict(stored)):
        later = GuestJoined("p1", "sam", datetime.now(timezone.utc), "acc")

    assert later.correlation_id == source.event_id
    assert later.causation_id == source.event_id
    assert later.depth == 1


def test_an_event_class_that_skips_the_base_post_init_still_gets_an_identity():
    @dataclass
    class Stubborn(PartyEvent):
        def __post_init__(self):
            pass  # does not call super()

    event = Stubborn("p1", "anne", datetime.now(timezone.utc), "acc")
    assert event.event_id == ""

    seen = []

    class Collect:
        def project(self, id, e):
            seen.append(e)

    EventPublisher([Collect()]).publish_event(event)
    assert seen[0].event_id and seen[0].correlation_id == seen[0].event_id


# -- through the CommandBusProjector ------------------------------------------------


@dataclass
class Join(Command):
    party_id: str


class JoinHandler(CommandHandler[Join]):
    command = Join

    def __init__(self, publisher_func):
        self.publisher_func = publisher_func

    def handle(self, command: Join):
        self.publisher_func().publish_event(
            GuestJoined(command.party_id, "sam", datetime.now(timezone.utc), "acc")
        )


class JoinOnOpened(EventCommandMapper):
    def mappers(self):
        return {PartyOpened: [lambda e: Join(party_id=e.id)]}


def test_events_published_by_a_mapped_command_descend_from_the_event():
    seen = []

    class Collect:
        def project(self, id, e):
            seen.append(e)

    bus = CommandBus(strict=False)
    publisher = EventPublisher([])
    bus.add_handler(JoinHandler(lambda: publisher))
    publisher.projectors = [Collect(), CommandBusProjector(lambda: bus, [JoinOnOpened])]

    source = opened()
    publisher.publish_event(source)

    joined = [e for e in seen if isinstance(e, GuestJoined)]
    assert len(joined) == 1
    assert joined[0].correlation_id == source.event_id
    assert joined[0].causation_id == source.event_id
    assert joined[0].depth == 1


def test_command_and_process_mappers_both_run_for_the_same_event():
    pytest.importorskip("fractal_processes")
    from fractal_processes.action import Action
    from fractal_processes.process import Process

    ran = []

    class Remember(Action):
        def execute(self, context):
            ran.append(current_cause())
            return context

    class RecordOnOpened(EventProcessMapper):
        def mappers(self):
            return {PartyOpened: [lambda e: Process([Remember()])]}

    bus = CommandBus(strict=False)
    publisher = EventPublisher([])
    bus.add_handler(JoinHandler(lambda: publisher))
    projector = CommandBusProjector(
        lambda: bus,
        [JoinOnOpened],
        process_mappers=[RecordOnOpened],
        context_func=lambda: object(),
    )

    source = opened()
    projector.project("stream", source)

    assert len(ran) == 1  # the Process ran although a command mapper exists too
    assert ran[0] == Cause(
        correlation_id=source.event_id, causation_id=source.event_id, depth=1
    )


# -- event stores ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "make_store",
    [
        lambda: ObjectEventStore(InMemoryEventStoreRepository()),
        lambda: DictEventStore(InMemoryEventStoreRepository(), events=[PartyOpened]),
        lambda: JsonEventStore(
            InMemoryEventStoreRepository(),
            events=[PartyOpened],
            json_encoder=EnhancedEncoder,
        ),
        lambda: PickleEventStore(InMemoryEventStoreRepository(), events=[PartyOpened]),
    ],
)
def test_a_stored_message_uses_the_event_id_and_reads_back_with_its_identity(
    make_store,
):
    store = make_store()
    source = opened()
    with caused_by(source):
        child = GuestJoined("p1", "sam", datetime.now(timezone.utc), "acc")
    stored = PartyOpened(
        "p1",
        "anne",
        datetime.now(timezone.utc),
        "acc",
        event_id=child.event_id,
        correlation_id=child.correlation_id,
        causation_id=child.causation_id,
        depth=child.depth,
    )

    store.commit(EventStream(events=[stored]), aggregate="Party", version=1)

    message = next(iter(store.event_store_repository.find()))
    assert message.id == stored.event_id
    # Read back inside another chain: a stored identity is never overwritten.
    with caused_by(opened()):
        (read,) = store.get_event_stream().events
    assert (read.event_id, read.correlation_id, read.causation_id, read.depth) == (
        stored.event_id,
        source.event_id,
        source.event_id,
        1,
    )


def _old_message(data, message_id="m-1") -> Message:
    return Message(
        id=message_id,
        occurred_on=datetime.now(timezone.utc),
        event="PartyOpened",
        data=data,
        object_id="p1",
        aggregate_root_id="p1",
    )


def test_an_event_stored_before_identities_reads_back_as_its_own_source_every_time():
    repository = InMemoryEventStoreRepository()
    old = {
        "id": "p1",
        "by": "anne",
        "on": datetime.now(timezone.utc),
        "account_id": "acc",
        "data": {},
    }
    repository.add(_old_message(old))
    store = DictEventStore(repository, events=[PartyOpened])

    first = store.get_event_stream().events[0]
    second = store.get_event_stream().events[0]

    assert first.event_id == second.event_id == "m-1"
    assert first.correlation_id == "m-1"
    assert first.causation_id == "" and first.depth == 0


def test_a_pickled_event_from_before_identities_gets_its_message_id():
    event = opened()
    for name in ("event_id", "correlation_id", "causation_id", "depth"):
        del event.__dict__[name]  # as an object pickled by fractal-events 1.1
    repository = InMemoryEventStoreRepository()
    repository.add(_old_message(pickle.dumps(event), message_id="m-2"))

    (read,) = (
        PickleEventStore(repository, events=[PartyOpened]).get_event_stream().events
    )

    assert read.event_id == read.correlation_id == "m-2"
    assert read.depth == 0


def test_asdict_carries_the_identity_for_dict_stores_and_webhooks():
    data = asdict(opened())
    assert {"event_id", "correlation_id", "causation_id", "depth"} <= set(data)
