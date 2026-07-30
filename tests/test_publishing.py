import json
from dataclasses import dataclass

from fractal_commands import Command

from fractal_events import (
    BasicSendingEvent,
    EventProjector,
    EventPublisher,
    EventStream,
    PrintEventProjector,
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


class RecordingProjector(EventProjector):
    def __init__(self):
        self.projected = []

    def project(self, id: str, event: BasicSendingEvent):
        self.projected.append((id, event))


def test_publish_event_reaches_every_projector():
    a, b = RecordingProjector(), RecordingProjector()
    publisher = EventPublisher([a, b])
    event = RoadAdded(command=Command(), road_id="1")

    publisher.publish_event(event)

    assert [e for _, e in a.projected] == [event]
    assert [e for _, e in b.projected] == [event]


def test_publish_events_shares_one_stream_id():
    projector = RecordingProjector()
    publisher = EventPublisher([projector])

    publisher.publish_events([RoadAdded(Command(), "1"), RoadAdded(Command(), "2")])

    ids = {stream_id for stream_id, _ in projector.projected}
    assert len(projector.projected) == 2
    assert len(ids) == 1, "events published together belong to one stream"


def test_separate_publishes_get_separate_stream_ids():
    projector = RecordingProjector()
    publisher = EventPublisher([projector])

    publisher.publish_event(RoadAdded(Command(), "1"))
    publisher.publish_event(RoadAdded(Command(), "2"))

    ids = [stream_id for stream_id, _ in projector.projected]
    assert ids[0] != ids[1]


def test_publishing_without_projectors_is_harmless():
    EventPublisher([]).publish_event(RoadAdded(Command(), "1"))


def test_an_event_stream_gets_an_id_of_its_own():
    assert EventStream().id != EventStream().id


def test_print_projector_writes_one_json_line(capsys):
    PrintEventProjector().project("stream-1", RoadAdded(Command(), "1"))

    printed = json.loads(capsys.readouterr().out)
    assert printed["id"] == "stream-1"
    assert printed["event"] == "RoadAdded"
    assert printed["object_id"] == "1"
    assert printed["aggregate_root_id"] == "1"
