"""Explainable rules-based routing for synthetic support tickets."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping, Any


@dataclass(frozen=True)
class RoutingDecision:
    """Result of trying to route one ticket."""
    agent_id: str | None
    reason: str
    eligible_agent_count: int


def split_pipe(value: str | None) -> set[str]:
    """Turn values such as 'payment|refund' into {'payment', 'refund'}."""
    return {part.strip() for part in (value or "").split("|") if part.strip()}


def route_ticket(
    ticket: Mapping[str, Any],
    agents: Iterable[Mapping[str, Any]],
    active_loads: Mapping[str, int] | None = None,
) -> RoutingDecision:
    """Choose an eligible agent, preferring the least-loaded agent.

    Required ticket keys: ticket_id, intent, language, priority.
    Required agent keys: agent_id, skills, languages, available, max_concurrent.
    active_loads maps agent IDs to their current number of open assignments.
    """
    active_loads = active_loads or {}
    intent = str(ticket.get("intent", ""))
    language = str(ticket.get("language", ""))
    priority = str(ticket.get("priority", "normal")).lower()

    # A safety case must never be treated as low priority.
    if intent == "safety" and priority not in {"critical", "urgent"}:
        return RoutingDecision(None, "blocked_invalid_safety_priority", 0)

    eligible: list[tuple[int, str, Mapping[str, Any]]] = []
    for agent in agents:
        agent_id = str(agent.get("agent_id", ""))
        available = str(agent.get("available", "false")).lower() in {"true", "1", "yes"}
        skills = split_pipe(str(agent.get("skills", "")))
        languages = split_pipe(str(agent.get("languages", "")))
        try:
            max_concurrent = int(agent.get("max_concurrent", 0))
            load = int(active_loads.get(agent_id, 0))
        except (TypeError, ValueError):
            continue
        if not agent_id or not available:
            continue
        if intent not in skills or language not in languages:
            continue
        # When a ticket timestamp and shift fields are provided, only route to an
        # agent whose local simulation shift is active. Unit callers that omit
        # created_at retain backwards-compatible skill/capacity-only behavior.
        created_at = ticket.get("created_at")
        if created_at and agent.get("shift_start_hour") is not None and agent.get("shift_end_hour") is not None:
            try:
                created_dt = datetime.fromisoformat(str(created_at))
                hour = created_dt.hour + created_dt.minute / 60
                shift_start = float(agent["shift_start_hour"])
                shift_end = float(agent["shift_end_hour"])
            except (TypeError, ValueError):
                continue
            on_shift = (shift_start <= hour < shift_end) if shift_start < shift_end else (hour >= shift_start or hour < shift_end)
            if not on_shift:
                continue
        if max_concurrent <= 0 or load < 0 or load >= max_concurrent:
            continue
        eligible.append((load, agent_id, agent))

    if not eligible:
        return RoutingDecision(None, "no_agent_matches_skill_language_availability_and_capacity", 0)

    # Stable tie-break makes results predictable: lowest active load, then agent ID.
    eligible.sort(key=lambda item: (item[0], item[1]))
    selected_load, selected_id, _ = eligible[0]
    return RoutingDecision(
        selected_id,
        f"matched_skill_language_available_capacity; load_before_assignment={selected_load}",
        len(eligible),
    )
