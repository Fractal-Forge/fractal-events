# Fractal Events

> Fractal Events is event sourcing for the Fractal stack: events, a publisher that fans them out to projectors, an event store to keep them in, and the projectors that print them, persist them, or turn them back into commands.

[![PyPI Version][pypi-image]][pypi-url]
[![Build Status][build-image]][build-url]

<!-- Badges -->

[pypi-image]: https://img.shields.io/pypi/v/fractal-events
[pypi-url]: https://pypi.org/project/fractal-events/
[build-image]: https://github.com/Fractal-Forge/fractal-events/actions/workflows/build.yml/badge.svg
[build-url]: https://github.com/Fractal-Forge/fractal-events/actions/workflows/build.yml

## Installation

```sh
pip install fractal-events
```

## Background

An event says something already happened: *this road was added*. A command asks
for something to happen. Keeping those apart is what makes the write side of an
application replayable — events are facts, and facts can be stored, re-read and
projected onto as many things as you like without any of those things knowing
about each other.

That is what this package is: the fact, the fan-out, and somewhere to keep the
facts.

## Publishing

```python
from fractal_events import EventPublisher, PrintEventProjector

publisher = EventPublisher([PrintEventProjector()])
publisher.publish_event(RoadAddedEvent(command=command, road_id="1"))
```

Events published together share one stream id; separate calls get separate
ones. Every projector sees every event — the publisher does not filter, and
projectors do not know about each other.

## Event identity and causation

Every sending event carries four keyword-only fields, set when it is created:

| field | meaning |
|---|---|
| `event_id` | its own id (`uuid4`) |
| `correlation_id` | the `event_id` of the event the chain started from; a source is its own |
| `causation_id` | the `event_id` of the event whose handling created this one; empty for a source |
| `depth` | links from the source: 0 for a source, one more per link |

`CommandBusProjector` runs the mappers and Processes for an event inside
`caused_by(event)`, so every event created meanwhile continues that event's
chain. Work that leaves the current context takes the cause along and restores
it later:

```python
from fractal_events import Cause, caused_by, current_cause

job.cause = current_cause().to_dict()          # when scheduling
with caused_by(Cause.from_dict(job.cause)):    # in the worker
    run(job)
```

The fields are left out of equality, so two events that say the same thing still
compare equal. The event stores use `event_id` as the message id, so a live event
and its replay share one key; events stored before identities existed read back
with their message id as `event_id`, the same on every replay.

## Projectors

- **`PrintEventProjector`** — writes each event as one JSON line. Useful in
  development, and the cheapest possible audit trail.
- **`EventStoreProjector`** — commits each event to an `EventStore`.
- **`CommandBusProjector`** — maps events back onto commands, or onto Processes.

### Mapping events back to commands

```python
from fractal_events import CommandBusProjector, EventCommandMapper


class RebuildOnRoadAdded(EventCommandMapper):
    def mappers(self):
        return {RoadAddedEvent: [lambda e: RebuildCommand(road_id=e.road_id)]}


projector = CommandBusProjector(
    lambda: context.command_bus,
    [RebuildOnRoadAdded()],
)
```

**Give this projector a lenient bus.** Fan-out legitimately produces commands
this particular deployment has no handler for — that is normal, not broken. A
`CommandBus()` is strict and will raise; construct it as
`CommandBus(strict=False)` for a projector, so a miss is logged rather than
thrown. A strict bus is right for a service call, where a missing handler does
mean the application is wired wrong.

When an event has both command mappers and process mappers, both run (before
1.2 a command mapper hid the Processes mapped to the same event).

### Mapping events to Processes

Process mappers run a stateful workflow instead of dispatching a command. They
need [fractal-processes](https://github.com/Fractal-Forge/fractal-processes)
(`pip install fractal-processes`), which is imported only when a process mapper
actually fires, and they need an application context:

```python
projector = CommandBusProjector(
    lambda: context.command_bus,
    [],
    process_mappers=[BuildRoadWorkflow()],
    context_func=lambda: context,
)
```

`context_func` is injected rather than imported. The application context lives a
layer above this package, and importing it here would point the middle of the
stack at the top for one constructor call. Leaving it out while passing process
mappers raises at construction time, not on whichever event happens to arrive
first.

## Event stores

Four flavours, differing only in how an event is stored and read back:

| store | stored as | needs |
|---|---|---|
| `ObjectEventStore` | the event object itself | an in-memory repository |
| `DictEventStore` | `asdict(event)` | the event classes, to rebuild them |
| `JsonEventStore` | a JSON string | the event classes, plus an encoder |
| `PickleEventStore` | a pickle | — |

All of them take an `EventStoreRepository`, so where the messages actually land
is a [fractal-repositories](https://github.com/douwevandermeij/fractal-repositories)
concern rather than this package's.

Reading back an event whose class is no longer mapped raises
`EventNotMappedError` rather than skipping it — a gap in a replayed stream is
worse than a loud failure.

## Development

```sh
make dev-install
make test
make lint
make format
```
