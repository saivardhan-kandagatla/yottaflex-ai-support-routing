"""Small, auditable ticket lifecycle state machine."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone

ALLOWED = {
    "new": {"assigned", "unassigned"},
    "unassigned": {"assigned", "escalated"},
    "assigned": {"responded", "transferred", "escalated", "resolved"},
    "responded": {"transferred", "escalated", "resolved"},
    "transferred": {"assigned", "escalated", "resolved"},
    "escalated": {"assigned", "transferred", "resolved"},
    "resolved": {"reopened"},
    "reopened": {"assigned", "escalated", "resolved"},
}

@dataclass
class TicketLifecycle:
    ticket_id: str
    status: str = "new"
    events: list[dict[str, str]] = field(default_factory=list)

    def transition(self, new_status: str, *, at: str | None = None, note: str = "") -> dict[str, str]:
        if new_status not in ALLOWED.get(self.status, set()):
            raise ValueError(f"Invalid ticket transition: {self.status} -> {new_status}")
        timestamp = at or datetime.now(timezone.utc).isoformat()
        event = {"ticket_id": self.ticket_id, "event_type": new_status,
                 "previous_status": self.status, "occurred_at": timestamp, "note": note}
        self.events.append(event)
        self.status = new_status
        return event

    def escalate_if_overdue(self, *, now: str, deadline: str) -> dict[str, str] | None:
        current = datetime.fromisoformat(now)
        due = datetime.fromisoformat(deadline)
        if current > due and self.status not in {"resolved", "escalated"}:
            return self.transition("escalated", at=now, note="SLA deadline exceeded")
        return None
