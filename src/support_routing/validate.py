"""Validate generated CSV files and produce a concise integrity report."""
from __future__ import annotations
import argparse, csv, json
from .lifecycle import ALLOWED
from datetime import datetime
from pathlib import Path


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def validate(data_dir: Path) -> dict:
    customers = read_rows(data_dir / "customers.csv")
    agents = read_rows(data_dir / "agents.csv")
    tickets = read_rows(data_dir / "tickets.csv")
    messages = read_rows(data_dir / "messages.csv")
    assignments = read_rows(data_dir / "assignment_events.csv")
    sla_events = read_rows(data_dir / "sla_events.csv")
    resolutions = read_rows(data_dir / "resolutions.csv")
    ticket_events = read_rows(data_dir / "ticket_events.csv") if (data_dir / "ticket_events.csv").exists() else []
    customer_ids = {r["customer_id"] for r in customers}
    agent_ids = {r["agent_id"] for r in agents}
    ticket_ids = {r["ticket_id"] for r in tickets}
    errors: list[str] = []
    def unique(rows, key, label):
        vals = [r[key] for r in rows]
        if len(vals) != len(set(vals)):
            errors.append(f"Duplicate {label} values in {key}")
    for rows, key, label in [(customers,"customer_id","customer IDs"),(agents,"agent_id","agent IDs"),
                             (tickets,"ticket_id","ticket IDs"),(messages,"message_id","message IDs"),
                             (assignments,"assignment_id","assignment IDs"),(sla_events,"sla_event_id","SLA IDs"),
                             (resolutions,"resolution_id","resolution IDs")]:
        unique(rows, key, label)
    for t in tickets:
        if t["customer_id"] not in customer_ids: errors.append(f"Ticket {t['ticket_id']} references missing customer")
        if t["assigned_agent_id"] and t["assigned_agent_id"] not in agent_ids: errors.append(f"Ticket {t['ticket_id']} references missing agent")
        if t["intent"] == "safety" and t["priority"] != "critical": errors.append(f"Safety ticket {t['ticket_id']} is not critical")
        if t.get("status") not in {"assigned", "unassigned", "resolved", "escalated", "reopened"}:
            errors.append(f"Ticket {t['ticket_id']} has invalid status {t.get('status')}")
        try:
            if not t.get("created_at"):
                raise ValueError("missing created_at")
            datetime.fromisoformat(t["created_at"])
        except (TypeError, ValueError):
            errors.append(f"Ticket {t['ticket_id']} has invalid created_at")
    for r in messages + assignments + sla_events + resolutions:
        if r["ticket_id"] not in ticket_ids: errors.append(f"Record references missing ticket {r['ticket_id']}")
    tickets_by_id = {t["ticket_id"]: t for t in tickets}
    agents_by_id = {a["agent_id"]: a for a in agents}
    created_at_by_ticket = {tid: datetime.fromisoformat(t["created_at"]) for tid, t in tickets_by_id.items()}
    latest_message_at: dict[str, datetime] = {}
    for message in messages:
        tid = message["ticket_id"]
        try:
            sent_at = datetime.fromisoformat(message["sent_at"])
            if tid in created_at_by_ticket and sent_at < created_at_by_ticket[tid]:
                errors.append(f"Message {message['message_id']} occurs before ticket creation")
            latest_message_at[tid] = max(latest_message_at.get(tid, sent_at), sent_at)
        except (TypeError, ValueError):
            errors.append(f"Message {message.get('message_id')} has invalid sent_at")
    for resolution in resolutions:
        tid = resolution["ticket_id"]
        try:
            resolved_at = datetime.fromisoformat(resolution["resolved_at"])
            minimum = max(created_at_by_ticket.get(tid, resolved_at), latest_message_at.get(tid, resolved_at))
            if resolved_at <= minimum:
                errors.append(f"Resolution for {tid} does not occur after ticket messages")
        except (TypeError, ValueError):
            errors.append(f"Resolution for {tid} has invalid resolved_at")
    events_by_ticket: dict[str, list[dict]] = {}
    for event in ticket_events:
        events_by_ticket.setdefault(event["ticket_id"], []).append(event)
        try:
            event_at = datetime.fromisoformat(event["event_at"])
            if event["ticket_id"] in created_at_by_ticket and event_at < created_at_by_ticket[event["ticket_id"]]:
                errors.append(f"Ticket event {event['event_id']} occurs before ticket creation")
        except (TypeError, ValueError):
            errors.append(f"Ticket event {event.get('event_id')} has invalid event_at")
    for tid, events in events_by_ticket.items():
        ordered = sorted(events, key=lambda e: e["event_id"])
        times = [datetime.fromisoformat(e["event_at"]) for e in ordered if e.get("event_at")]
        if times != sorted(times):
            errors.append(f"Ticket events are not chronological for {tid}")
        current_status = "new"
        for event in ordered:
            try:
                details = json.loads(event.get("details", "{}"))
            except (TypeError, json.JSONDecodeError):
                details = {}
            previous_status = details.get("previous_status")
            next_status = event.get("event_type")
            if previous_status != current_status:
                errors.append(f"Ticket lifecycle history has inconsistent previous status for {event.get('event_id')}")
            if next_status not in ALLOWED.get(current_status, set()):
                errors.append(f"Invalid lifecycle transition for {tid}: {current_status} -> {next_status}")
            current_status = next_status
    assignment_by_ticket: dict[str, list[dict]] = {}
    for assignment in assignments:
        assignment_by_ticket.setdefault(assignment["ticket_id"], []).append(assignment)
        try:
            assigned_at = datetime.fromisoformat(assignment["assigned_at"])
            tid = assignment["ticket_id"]
            if tid in created_at_by_ticket and assigned_at < created_at_by_ticket[tid]:
                errors.append(f"Assignment {assignment['assignment_id']} occurs before ticket creation")
        except (TypeError, ValueError):
            errors.append(f"Assignment {assignment.get('assignment_id')} has invalid assigned_at")
    for tid, ticket in tickets_by_id.items():
        history = assignment_by_ticket.get(tid, [])
        if ticket.get("assigned_agent_id") and not history:
            errors.append(f"Ticket {tid} has an assigned agent but no assignment history")
        if history and history[-1].get("agent_id") != ticket.get("assigned_agent_id"):
            errors.append(f"Ticket {tid} assigned_agent_id does not match latest assignment event")
    for sla in sla_events:
        if sla.get("sla_status") not in {"open", "met", "breached"}:
            errors.append(f"SLA {sla.get('sla_event_id')} has invalid status {sla.get('sla_status')}")
    # Check assignment eligibility and build a concurrency timeline. Capacity is
    # released at resolution, or at escalation when the ticket leaves the agent queue.
    escalations = {}
    for event in ticket_events:
        if event.get("event_type") == "escalated":
            escalations[event["ticket_id"]] = event["event_at"]
    resolution_times = {r["ticket_id"]: r["resolved_at"] for r in resolutions}
    concurrency_events: dict[str, list[tuple[str, int, str]]] = {}
    for a in assignments:
        agent = agents_by_id.get(a["agent_id"])
        ticket = tickets_by_id.get(a["ticket_id"])
        if not agent:
            errors.append(f"Assignment {a['assignment_id']} references missing agent")
            continue
        if str(agent.get("available", "false")).lower() not in {"true", "1", "yes"}:
            errors.append(f"Unavailable agent assigned: {a['ticket_id']}")
        if ticket:
            if ticket["intent"] not in agent["skills"].split("|"): errors.append(f"Skill mismatch: {a['ticket_id']}")
            if ticket["language"] not in agent["languages"].split("|"): errors.append(f"Language mismatch: {a['ticket_id']}")
        release = resolution_times.get(a["ticket_id"]) or escalations.get(a["ticket_id"])
        if not release:
            errors.append(f"Assignment {a['assignment_id']} has no resolution or escalation release event")
            continue
        concurrency_events.setdefault(a["agent_id"], []).append((a["assigned_at"], 1, a["ticket_id"]))
        concurrency_events[a["agent_id"]].append((release, -1, a["ticket_id"]))
    max_observed_concurrent = 0
    for agent_id, timeline in concurrency_events.items():
        active = 0
        agent = agents_by_id[agent_id]
        try:
            capacity = int(agent["max_concurrent"])
        except (KeyError, ValueError):
            errors.append(f"Invalid max_concurrent for {agent_id}")
            continue
        for at, delta, ticket_id in sorted(timeline, key=lambda item: (item[0], item[1])):
            active += delta  # releases (-1) happen before assignments (+1) at equal timestamps
            max_observed_concurrent = max(max_observed_concurrent, active)
            if active < 0:
                errors.append(f"Negative active load for {agent_id} at {at}")
                active = 0
            if active > capacity:
                errors.append(f"Agent {agent_id} exceeds capacity {capacity} at {at} (active={active})")
                # Avoid emitting thousands of duplicate errors for one agent/time range.
                break
    report = {"data_directory": str(data_dir), "counts": {"customers":len(customers),"agents":len(agents),
              "tickets":len(tickets),"messages":len(messages),"assignments":len(assignments),
              "sla_events":len(sla_events),"resolutions":len(resolutions)},
              "unassigned_tickets":sum(not t["assigned_agent_id"] for t in tickets),
              "max_observed_concurrent": max_observed_concurrent,
              "integrity_errors":errors, "passed":not errors}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated support-routing data")
    parser.add_argument("--data", type=Path, default=Path("data/starter"))
    parser.add_argument("--report", type=Path, default=Path("reports/validation_summary.json"))
    args = parser.parse_args()
    report = validate(args.data)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["passed"]: raise SystemExit(1)

if __name__ == "__main__": main()
