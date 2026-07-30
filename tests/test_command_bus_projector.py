from dataclasses import dataclass

import pytest
from fractal_commands import Command, CommandBus, CommandHandler, NoCommandHandlerError
from fractal_core import FractalException

from fractal_events import (
    CommandBusProjector,
    EventCommandMapper,
    EventProcessMapper,
    ReceivingEvent,
    SendingEvent,
)


@dataclass
class Rebuild(Command):
    road_id: str


class RebuildHandler(CommandHandler[Rebuild]):
    command = Rebuild

    def __init__(self):
        self.handled = []

    def handle(self, command: Rebuild):
        self.handled.append(command)


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
class Unmapped(SendingEvent):
    command: Command

    @property
    def object_id(self):
        return "x"

    @property
    def aggregate_root_id(self):
        return "x"

    @property
    def aggregate_root_type(self):
        return "X"


@dataclass
class RoadImported(ReceivingEvent):
    road_id: str

    def to_command(self):
        return Rebuild(road_id=self.road_id)


class RebuildOnRoadAdded(EventCommandMapper):
    def mappers(self):
        return {RoadAdded: [lambda e: Rebuild(road_id=e.road_id)]}


class RebuildTwice(EventCommandMapper):
    def mappers(self):
        return {
            RoadAdded: [
                lambda e: [Rebuild(road_id=e.road_id), Rebuild(road_id=e.road_id)]
            ]
        }


class MapsToNothing(EventCommandMapper):
    def mappers(self):
        return {RoadAdded: [lambda e: None]}


def make(mappers, **kwargs):
    handler = RebuildHandler()
    bus = CommandBus()
    bus.add_handler(handler)
    return CommandBusProjector(lambda: bus, mappers, **kwargs), handler


def test_a_mapped_event_becomes_a_command():
    projector, handler = make([RebuildOnRoadAdded])

    projector.project("s1", RoadAdded(Command(), "1"))

    assert [c.road_id for c in handler.handled] == ["1"]


def test_a_mapper_may_return_several_commands():
    projector, handler = make([RebuildTwice])

    projector.project("s1", RoadAdded(Command(), "1"))

    assert len(handler.handled) == 2


def test_a_mapper_returning_none_produces_no_command():
    projector, handler = make([MapsToNothing])

    projector.project("s1", RoadAdded(Command(), "1"))

    assert handler.handled == []


def test_an_unmapped_event_is_ignored():
    projector, handler = make([RebuildOnRoadAdded])

    projector.project("s1", Unmapped(Command()))

    assert handler.handled == []


def test_a_receiving_event_converts_itself_to_a_command():
    projector, handler = make([])

    projector.project("s1", RoadImported(road_id="7"))

    assert [c.road_id for c in handler.handled] == ["7"]


def test_fan_out_onto_a_strict_bus_raises():
    """Why a projector's bus should be lenient.

    A command mapper legitimately produces commands this deployment has no
    handler for. On a strict bus that is an exception; on a lenient one it is a
    logged miss. The projector does not choose — whoever constructs the bus
    does — so this pins down what that choice means.
    """
    projector = CommandBusProjector(lambda: CommandBus(), [RebuildOnRoadAdded])

    with pytest.raises(NoCommandHandlerError):
        projector.project("s1", RoadAdded(Command(), "1"))


def test_fan_out_onto_a_lenient_bus_is_only_logged(caplog):
    projector = CommandBusProjector(
        lambda: CommandBus(strict=False), [RebuildOnRoadAdded]
    )

    projector.project("s1", RoadAdded(Command(), "1"))

    assert "no handler is registered for Rebuild" in caplog.text


# --------------------------------------------------------------------------- #
# The process path. It used to import ApplicationContext directly, which made
# this package depend on the layer above it. The context is injected now.
# --------------------------------------------------------------------------- #
class RunAProcess(EventProcessMapper):
    def mappers(self):
        return {RoadAdded: [lambda e: object()]}


def test_process_mappers_without_a_context_fail_at_construction():
    """Wiring mistakes should surface when the application is assembled.

    Not on whichever event happens to arrive first — that could be days later,
    in production, on the one code path nobody exercised.
    """
    with pytest.raises(FractalException, match="context_func"):
        CommandBusProjector(lambda: CommandBus(), [], process_mappers=[RunAProcess])


def test_process_mappers_with_a_context_construct_fine():
    projector = CommandBusProjector(
        lambda: CommandBus(),
        [],
        process_mappers=[RunAProcess],
        context_func=lambda: object(),
    )

    assert projector.process_mappers


def test_command_mappers_alone_need_no_context():
    assert CommandBusProjector(lambda: CommandBus(), [RebuildOnRoadAdded])


def test_the_process_path_does_not_import_the_application_layer():
    """fractal-events must not reach up into fractal-application.

    The check is on the module's own imports rather than on behaviour: the
    old code only touched ApplicationContext deep inside a branch, so a test
    that merely exercised the happy path would not have caught it.
    """
    import fractal_events.projectors.command_bus_projector as module

    source = open(module.__file__, encoding="utf-8").read()

    assert "application_context" not in source
    assert "ApplicationContext" not in source
