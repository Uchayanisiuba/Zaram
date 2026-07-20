"""Provider-independent orchestrator events (v0.6.1).

Every helper returns a standard :class:`core.event_bus.ZaramEvent` so
orchestrator events flow through the *same* event bus as kernel, voice, media,
and garage events. Events are fully generic: they reference request/plan/model
identifiers, never a provider or model name.

Event types:
    RoutingStarted, RoutingCompleted, RoutingFailed, PlanCreated, PlanUpdated,
    ModelSelected, PreferencesChanged, PreferencesUpdated, ProfileChanged,
    PolicyChanged
"""

from __future__ import annotations

from typing import Any, Optional

from core.event_bus import ZaramEvent

# --- Event type identifiers (Event Bus) ---
ROUTING_STARTED = "orchestrator.routing_started"
ROUTING_COMPLETED = "orchestrator.routing_completed"
ROUTING_FAILED = "orchestrator.routing_failed"
PLAN_CREATED = "orchestrator.plan_created"
PLAN_UPDATED = "orchestrator.plan_updated"
MODEL_SELECTED = "orchestrator.model_selected"
PREFERENCES_CHANGED = "orchestrator.preferences_changed"
PREFERENCES_UPDATED = "orchestrator.preferences_updated"
PROFILE_CHANGED = "orchestrator.profile_changed"
POLICY_CHANGED = "orchestrator.policy_changed"

ALL_ORCHESTRATOR_EVENTS = [
    ROUTING_STARTED,
    ROUTING_COMPLETED,
    ROUTING_FAILED,
    PLAN_CREATED,
    PLAN_UPDATED,
    MODEL_SELECTED,
    PREFERENCES_CHANGED,
    PREFERENCES_UPDATED,
    PROFILE_CHANGED,
    POLICY_CHANGED,
]


def create_orchestrator_event(
    event_type: str,
    *,
    request_id: str = "",
    plan_id: str = "",
    model_id: str = "",
    source_runtime: str = "orchestrator",
    correlation_id: str = "",
    priority: str = "normal",
    metadata: Optional[dict[str, Any]] = None,
) -> ZaramEvent:
    """Build an orchestrator event as a standard ``ZaramEvent``.

    Identifiers are carried in ``event.data``; the timestamp comes from the
    ``ZaramEvent`` itself.
    """
    data: dict[str, Any] = {}
    if request_id:
        data["request_id"] = request_id
    if plan_id:
        data["plan_id"] = plan_id
    if model_id:
        data["model_id"] = model_id
    if metadata:
        data.update(metadata)
    return ZaramEvent(
        source_runtime=source_runtime,
        event_type=event_type,
        correlation_id=correlation_id,
        priority=priority,
        data=data,
    )
