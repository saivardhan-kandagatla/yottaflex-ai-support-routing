"""Channel-aware SLA deadline calculations using configurable business calendars."""
from __future__ import annotations
from datetime import datetime, timedelta, time
from typing import Mapping, Any

# Example defaults. Replace with values explicitly required by the challenge if different.
DEFAULT_SLA_RULES = {
    "chat": {"first_response_minutes": {"critical": 5, "high": 15, "normal": 30, "low": 60},
             "resolution_minutes": {"critical": 60, "high": 240, "normal": 480, "low": 1440},
             "business_hours_only": False},
    "phone": {"first_response_minutes": {"critical": 1, "high": 5, "normal": 10, "low": 15},
              "resolution_minutes": {"critical": 60, "high": 240, "normal": 480, "low": 1440},
              "business_hours_only": False},
    "email": {"first_response_minutes": {"critical": 15, "high": 60, "normal": 240, "low": 480},
              "resolution_minutes": {"critical": 240, "high": 480, "normal": 1440, "low": 2880},
              "business_hours_only": True},
}


def add_business_minutes(start: datetime, minutes: int, *, start_hour: int = 9,
                         end_hour: int = 17, weekdays_only: bool = True) -> datetime:
    """Add working minutes, skipping nights and (optionally) weekends."""
    if minutes < 0:
        raise ValueError("minutes must be non-negative")
    current = start
    remaining = minutes
    while remaining > 0:
        if weekdays_only and current.weekday() >= 5:
            current = (current + timedelta(days=1)).replace(hour=start_hour, minute=0, second=0, microsecond=0)
            continue
        opening = current.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        closing = current.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        if current < opening:
            current = opening
        elif current >= closing:
            current = (current + timedelta(days=1)).replace(hour=start_hour, minute=0, second=0, microsecond=0)
            continue
        available = int((closing - current).total_seconds() // 60)
        step = min(remaining, available)
        current += timedelta(minutes=step)
        remaining -= step
        if remaining and current >= closing:
            current = (current + timedelta(days=1)).replace(hour=start_hour, minute=0, second=0, microsecond=0)
    return current


def get_sla_target_minutes(ticket: Mapping[str, Any], kind: str = "first_response",
                           rules: Mapping[str, Any] | None = None) -> int:
    """Return the configured target duration for a ticket/channel/priority."""
    rules = rules or DEFAULT_SLA_RULES
    channel = str(ticket.get("channel", "")).lower()
    priority = str(ticket.get("priority", "normal")).lower()
    key = "first_response_minutes" if kind == "first_response" else "resolution_minutes"
    try:
        return int(rules[channel][key][priority])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Unknown SLA target for channel={channel}, priority={priority}, kind={kind}") from exc


def calculate_deadlines(ticket: Mapping[str, Any], rules: Mapping[str, Any] | None = None) -> dict[str, str]:
    """Return ISO first-response and resolution deadlines for a ticket."""
    rules = rules or DEFAULT_SLA_RULES
    channel = str(ticket.get("channel", "")).lower()
    priority = str(ticket.get("priority", "normal")).lower()
    if channel not in rules:
        raise ValueError(f"Unknown channel: {channel}")
    channel_rules = rules[channel]
    try:
        created = datetime.fromisoformat(str(ticket["created_at"]))
        response_minutes = int(channel_rules["first_response_minutes"][priority])
        resolution_minutes = int(channel_rules["resolution_minutes"][priority])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Ticket is missing valid created_at/channel/priority SLA configuration: {exc}") from exc
    if channel_rules.get("business_hours_only", False):
        response_deadline = add_business_minutes(created, response_minutes)
        resolution_deadline = add_business_minutes(created, resolution_minutes)
    else:
        response_deadline = created + timedelta(minutes=response_minutes)
        resolution_deadline = created + timedelta(minutes=resolution_minutes)
    return {"first_response_deadline": response_deadline.isoformat(),
            "resolution_deadline": resolution_deadline.isoformat()}


def assess_sla(ticket: Mapping[str, Any], *, first_response_at: str | None = None,
               resolved_at: str | None = None, rules: Mapping[str, Any] | None = None) -> list[dict[str, str]]:
    """Return SLA event records for deadlines that have been met or breached."""
    deadlines = calculate_deadlines(ticket, rules)
    events: list[dict[str, str]] = []
    for kind, actual in (("first_response", first_response_at), ("resolution", resolved_at)):
        deadline = datetime.fromisoformat(deadlines[f"{kind}_deadline"])
        if actual is None:
            continue
        actual_dt = datetime.fromisoformat(actual)
        events.append({"ticket_id": str(ticket["ticket_id"]), "event_type": f"{kind}_{'met' if actual_dt <= deadline else 'breached'}",
                       "deadline_at": deadline.isoformat(), "occurred_at": actual_dt.isoformat()})
    return events
