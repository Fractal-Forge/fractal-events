from typing import Any, Callable, List, Optional, Type, Union

from fractal_commands import CommandBus
from fractal_core import FractalException

from fractal_events.event import (
    EventCommandMapper,
    EventProcessMapper,
    ReceivingEvent,
    SendingEvent,
)
from fractal_events.event_projector import EventProjector


class CommandBusProjector(EventProjector):
    """Turns events back into commands.

    Two mapping styles. ``command_mappers`` translate an event into one or more
    commands and put them straight on the bus. ``process_mappers`` translate it
    into a Process — a stateful workflow — and run that instead.

    Note what a command mapper implies for the bus: fan-out legitimately
    produces commands this deployment has no handler for, so the bus it is
    given should be a lenient one (``CommandBus(strict=False)``). A strict bus
    is right for a service call, where a missing handler means the application
    is wired wrong; it is wrong here, where it may just mean this service does
    not care about that event.
    """

    def __init__(
        self,
        command_bus_func: Callable[[], CommandBus],
        # Mapper *classes*, not instances — the constructor calls each one. The
        # annotation used to say instances, which type-checked fine right up to
        # the TypeError at runtime.
        command_mappers: List[Type[EventCommandMapper]],
        process_mappers: Optional[List[Type[EventProcessMapper]]] = None,
        context_func: Optional[Callable[[], Any]] = None,
    ):
        self.command_bus_func = command_bus_func
        self.context_func = context_func
        self.command_mappers = {
            event: mapper
            for m in command_mappers
            for event, mapper in m().mappers().items()
        }
        self.process_mappers = {
            event: mapper
            for m in (process_mappers or [])
            for event, mapper in m().mappers().items()
        }
        if self.process_mappers and context_func is None:
            # Checked here rather than where the Process runs: this is a wiring
            # mistake, and a wiring mistake should surface when the application
            # is assembled, not on whichever event happens to arrive first.
            raise FractalException(
                f"{type(self).__name__} was given process mappers but no "
                "`context_func`, so a Process would have no application context "
                "to run against"
            )

    # Narrower than the base on purpose — see EventProjector.project.
    def project(self, id: str, event: Union[SendingEvent, ReceivingEvent]):  # type: ignore[override]
        if isinstance(event, ReceivingEvent):
            self.command_bus_func().handle(event.to_command())

        # Execute command mappers
        elif event.__class__ in self.command_mappers:
            for mapper in self.command_mappers[event.__class__]:
                commands = mapper(event)
                for command in (
                    commands if type(commands) is list else [commands]
                ):  # backwards compatibility
                    if command is not None:  # Skip None returns
                        self.command_bus_func().handle(command)

        # Execute process mappers
        elif event.__class__ in self.process_mappers:
            self._run_processes(event)

    def _run_processes(self, event: Union[SendingEvent, ReceivingEvent]):
        """Run the Processes mapped to this event.

        The imports are deliberately local. fractal-processes is an optional
        dependency — an application that only uses command mappers should not
        have to install a process engine — so nothing may import it at module
        load time.

        The application context arrives through ``context_func`` rather than
        being imported. Reaching for it directly would make this package, which
        sits below the application layer, depend on the layer above it for one
        constructor call; the two construction sites both live up there and can
        simply hand it down.
        """
        from fractal_processes.process import Process
        from fractal_processes.process_context import ProcessContext

        for mapper in self.process_mappers[event.__class__]:
            process = mapper(event)
            if not isinstance(process, Process):
                continue
            ctx = ProcessContext({"fractal": {"context": self.context_func()}})
            process.run(ctx)
