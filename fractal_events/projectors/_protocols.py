from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RecordableEvent(Protocol):
    """An event carrying enough identity to be written down.

    Structural on purpose. The event stores have always accepted anything with
    these two attributes rather than only ``BasicSendingEvent`` subclasses, and
    tightening that to a subclass check would break callers whose events merely
    satisfy the shape. A ``runtime_checkable`` Protocol keeps the runtime check
    structural while still letting the type checker follow it — which a
    hand-written ``getattr`` guard cannot do, and which is why the projectors
    used to narrow their signature and silence the resulting complaint.
    """

    object_id: Any
    aggregate_root_id: Any
