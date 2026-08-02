"""Every projector accepts an Event, and says so honestly.

The three projectors used to narrow `project` to SendingEvent (or a union),
which is a Liskov violation — a PrintEventProjector cannot stand in wherever an
EventProjector is expected, because CommandBusProjector really does receive
ReceivingEvents. Each narrowing was silenced with a type: ignore. They take a
plain Event now and check what they actually need.
"""

import inspect
from dataclasses import dataclass

import pytest
from fractal_commands import Command, CommandBus

from fractal_events import (
    CommandBusProjector,
    Event,
    EventProjector,
    EventStoreProjector,
    InMemoryEventStoreRepository,
    ObjectEventStore,
    PrintEventProjector,
    ReceivingEvent,
    SendingEvent,
)


@dataclass
class RoadAdded(SendingEvent):
    command: Command
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


@dataclass
class RoadImported(ReceivingEvent):
    road_id: str

    def to_command(self):
        return Command()


PROJECTORS = [
    lambda: PrintEventProjector(),
    lambda: EventStoreProjector(ObjectEventStore(InMemoryEventStoreRepository())),
    lambda: CommandBusProjector(lambda: CommandBus(strict=False), []),
]


@pytest.mark.parametrize("build", PROJECTORS)
def test_every_projector_takes_the_same_event_type_as_the_base(build):
    """Substitutability, checked on the signatures rather than assumed."""
    base = inspect.signature(EventProjector.project).parameters["event"].annotation
    own = inspect.signature(type(build()).project).parameters["event"].annotation

    assert own is base is Event


def test_no_projector_silences_the_type_checker():
    """A narrowed signature is what the ignore comments were hiding."""
    import fractal_events.projectors as pkg

    for module in (
        "command_bus_projector",
        "event_store_projector",
        "print_projector",
    ):
        source = open(
            __import__(f"fractal_events.projectors.{module}", fromlist=["x"]).__file__,
            encoding="utf-8",
        ).read()
        assert "type: ignore[override]" not in source, module
    assert pkg  # the package imports


def test_a_sending_projector_rejects_a_receiving_event(capsys):
    """It used to reach for object_id and fail with AttributeError."""
    with pytest.raises(TypeError, match="object id"):
        PrintEventProjector().project("s1", RoadImported(road_id="1"))

    assert capsys.readouterr().out == ""


def test_the_event_store_projector_rejects_one_too():
    store = ObjectEventStore(InMemoryEventStoreRepository())

    with pytest.raises(TypeError, match="object id"):
        EventStoreProjector(store).project("s1", RoadImported(road_id="1"))

    assert store.get_event_stream().events == []


def test_the_command_bus_projector_accepts_both_kinds():
    """The reason the base has to be wide in the first place."""
    projector = CommandBusProjector(lambda: CommandBus(strict=False), [])

    projector.project("s1", RoadImported(road_id="1"))
    projector.project("s1", RoadAdded(Command(), "1"))


def test_sending_events_still_project_normally(capsys):
    PrintEventProjector().project("s1", RoadAdded(Command(), "1"))

    assert "RoadAdded" in capsys.readouterr().out
