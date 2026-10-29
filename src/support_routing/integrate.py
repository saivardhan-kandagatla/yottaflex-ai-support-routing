"""Integrate routing, SLA deadlines, and ticket lifecycle events into generated data."""
from __future__ import annotations
import csv, json
from datetime import datetime, timedelta
from pathlib import Path
from .routing import route_ticket
from .sla import calculate_deadlines, assess_sla, get_sla_target_minutes
from .lifecycle import TicketLifecycle


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def integrate(data_dir: Path) -> dict:
    """Re-route tickets in time order and generate SLA/lifecycle history.

    The active load is incremented on assignment and decremented on resolution.
    Example SLA rules live in sla.py and must be aligned to the challenge's exact
    calendar/targets before final submission.
    """
    tickets = read_csv(data_dir / "tickets.csv")
    agents = read_csv(data_dir / "agents.csv")
    messages = read_csv(data_dir / "messages.csv")
    resolutions = {r["ticket_id"]: r for r in read_csv(data_dir / "resolutions.csv")}
    loads = {a["agent_id"]: 0 for a in agents}
    assigned_agent: dict[str, str] = {}
    # The time at which each active assignment stops consuming agent capacity.
    # Resolved tickets release at resolution; unresolved tickets release when
    # they are escalated out of the assigned agent's queue.
    release_at: dict[str, datetime] = {}
    assignments: list[dict] = []
    sla_rows: list[dict] = []
    ticket_events: list[dict] = []
    sla_audit_events: list[dict] = []
    message_groups: dict[str, list[dict]] = {}
    for m in messages:
        message_groups.setdefault(m["ticket_id"], []).append(m)
    # Deterministic order is important: load changes as tickets are resolved.
    tickets.sort(key=lambda t: (t["created_at"], t["ticket_id"]))
    for ticket in tickets:
        tid = ticket["ticket_id"]
        created = datetime.fromisoformat(ticket["created_at"])
        # Release any assignment whose resolution/escalation event has occurred.
        for prior_tid, agent_id in list(assigned_agent.items()):
            release_time = release_at.get(prior_tid)
            if release_time is not None and release_time <= created:
                loads[agent_id] = max(0, loads[agent_id] - 1)
                del assigned_agent[prior_tid]
                release_at.pop(prior_tid, None)
        decision = route_ticket(ticket, agents, loads)
        ticket["assigned_agent_id"] = decision.agent_id or ""
        ticket["status"] = "assigned" if decision.agent_id else "unassigned"
        if decision.agent_id:
            aid = decision.agent_id
            loads[aid] += 1
            assigned_agent[tid] = aid
            assignments.append({"assignment_id": f"ASN-{tid}-001", "ticket_id": tid,
                "agent_id": aid, "queue_id": ticket.get("queue_id", f"QUE-{ticket['intent'].upper()}"),
                "assigned_at": ticket["created_at"], "reason": decision.reason,
                "event_type": "assigned"})
        deadlines = calculate_deadlines(ticket)
        ticket["first_response_deadline"] = deadlines["first_response_deadline"]
        ticket["resolution_deadline"] = deadlines["resolution_deadline"]
        ticket["sla_deadline"] = deadlines["first_response_deadline"]
        response_minutes = get_sla_target_minutes(ticket, "first_response")
        sla_record = {"sla_event_id": f"SLA-{tid}", "ticket_id": tid,
            "target_response_minutes": response_minutes, "started_at": ticket["created_at"],
            "deadline_at": deadlines["first_response_deadline"], "sla_status": "open"}
        sla_rows.append(sla_record)
        life = TicketLifecycle(tid)
        life.transition("assigned" if decision.agent_id else "unassigned", at=ticket["created_at"], note=decision.reason)
        ticket_messages = sorted(message_groups.get(tid, []), key=lambda m: m["sent_at"])
        first_agent_message = next((m for m in ticket_messages if m["sender_type"] == "agent"), None)
        if first_agent_message and decision.agent_id:
            life.transition("responded", at=first_agent_message["sent_at"], note="First agent response")
        resolution = resolutions.get(tid)
        if resolution:
            resolved_at = resolution["resolved_at"]
            # Keep the resolution after ticket creation and the final thread message.
            latest_message_at = max(
                (datetime.fromisoformat(m["sent_at"]) for m in ticket_messages),
                default=created,
            )
            resolved_dt = datetime.fromisoformat(resolved_at)
            if resolved_dt <= max(created, latest_message_at):
                resolved_dt = max(created, latest_message_at) + timedelta(minutes=1)
                resolved_at = resolved_dt.isoformat()
                resolution["resolved_at"] = resolved_at
            if life.status == "unassigned":
                life.transition("escalated", at=resolved_at, note="No eligible agent available")
            if life.status != "resolved":
                life.transition("resolved", at=resolved_at, note=resolution["resolution_type"])
            ticket["status"] = "resolved"
            if decision.agent_id:
                release_at[tid] = datetime.fromisoformat(resolved_at)
        # Add auditable SLA assessment events. Use messages/resolution as observed outcomes.
        sla_audit_events.extend(assess_sla(ticket,
            first_response_at=first_agent_message["sent_at"] if first_agent_message else None,
            resolved_at=resolution["resolved_at"] if resolution else None))
        # Any ticket still unresolved after the two-day observation horizon is
        # escalated out of the original agent queue, whether or not a first
        # response was sent. This creates a terminal event for capacity accounting
        # without falsely marking the ticket as resolved.
        if not resolution:
            deadline_at = datetime.fromisoformat(deadlines["first_response_deadline"])
            # Escalate after both the two-day observation horizon and the SLA
            # deadline, so the lifecycle event is actually overdue.
            escalation_at = max(created + timedelta(days=2), deadline_at + timedelta(minutes=1))
            event = life.escalate_if_overdue(
                now=escalation_at.isoformat(),
                deadline=deadlines["first_response_deadline"],
            )
            if event:
                ticket["status"] = "escalated"
                if decision.agent_id:
                    release_at[tid] = datetime.fromisoformat(event["occurred_at"])
        if first_agent_message:
            response_dt = datetime.fromisoformat(first_agent_message["sent_at"])
            deadline_dt = datetime.fromisoformat(deadlines["first_response_deadline"])
            sla_record["sla_status"] = "met" if response_dt <= deadline_dt else "breached"
        elif ticket["status"] in {"resolved", "escalated"}:
            sla_record["sla_status"] = "breached"
        for index, event in enumerate(life.events, 1):
            ticket_events.append({"event_id": f"EVT-{tid}-{index:03d}", "ticket_id": tid,
                "event_type": event["event_type"], "event_at": event["occurred_at"],
                "actor_id": assigned_agent.get(tid, ""), "details": json.dumps({
                    "previous_status": event["previous_status"], "note": event["note"]}, sort_keys=True)})
    write_csv(data_dir / "tickets.csv", tickets)
    write_csv(data_dir / "assignment_events.csv", assignments)
    write_csv(data_dir / "sla_events.csv", sla_rows)
    write_csv(data_dir / "ticket_events.csv", ticket_events)
    write_csv(data_dir / "sla_audit_events.csv", sla_audit_events)
    if resolutions:
        write_csv(data_dir / "resolutions.csv", list(resolutions.values()))
    return {"tickets": len(tickets), "assignments": len(assignments), "ticket_events": len(ticket_events),
            "sla_records": len(sla_rows), "sla_audit_events": len(sla_audit_events),
            "unassigned_tickets": sum(not t["assigned_agent_id"] for t in tickets)}
