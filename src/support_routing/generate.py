"""Generate deterministic synthetic support-routing datasets using only the standard library."""
from __future__ import annotations
import argparse, csv, json, random
from datetime import datetime, timedelta, timezone
from pathlib import Path

CHANNELS = ["email", "chat", "phone"]
LANGUAGES = ["en", "hi", "te", "ta", "es"]
INTENTS = ["payment", "delivery", "refund", "technical", "account", "safety"]
PRIORITY_BY_INTENT = {"safety": "critical", "payment": "high", "delivery": "normal", "refund": "normal", "technical": "high", "account": "low"}
SKILLS = ["payment", "delivery", "refund", "technical", "account", "safety"]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def make_id(prefix: str, number: int, width: int = 6) -> str:
    return f"{prefix}{number:0{width}d}"


def generate(output: Path, mode: str = "starter", seed: int = 20261022,
             ticket_count: int | None = None, agent_count: int | None = None,
             message_count: int | None = None) -> dict:
    rng = random.Random(seed)
    if mode == "full":
        ticket_count = ticket_count or 30_000
        agent_count = agent_count or 100
        message_count = message_count or 100_000
    else:
        ticket_count = ticket_count or 100
        agent_count = agent_count or 10
        message_count = message_count or max(300, ticket_count * 3)
    if ticket_count < 1 or agent_count < 1 or message_count < ticket_count:
        raise ValueError("Use at least 1 ticket and agent, and at least as many messages as tickets.")

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    customers = [{"customer_id": make_id("CUS-", i), "language": rng.choice(LANGUAGES),
                  "created_at": (start + timedelta(days=rng.randrange(365))).isoformat()}
                 for i in range(1, max(50, ticket_count // 2) + 1)]
    channels = [{"channel_id": f"CHN-{name}", "channel_name": name} for name in CHANNELS]
    intents = [{"intent_id": f"INT-{name}", "intent_name": name} for name in INTENTS]
    priority_rules = [{"priority_rule_id": f"PR-{name}", "intent_name": name,
                       "required_priority": PRIORITY_BY_INTENT[name],
                       "rule_description": f"Intent {name} uses {PRIORITY_BY_INTENT[name]} priority in the baseline taxonomy."}
                      for name in INTENTS]
    queues = [{"queue_id": f"QUE-{name.upper()}", "queue_name": f"{name.title()} Queue", "intent_name": name}
              for name in INTENTS]
    agents = []
    for i in range(1, agent_count + 1):
        agent_skills = sorted(rng.sample(SKILLS, k=rng.randint(2, min(4, len(SKILLS)))))
        agent_languages = sorted(rng.sample(LANGUAGES, k=rng.randint(1, min(3, len(LANGUAGES)))))
        agents.append({"agent_id": make_id("AGT-", i), "name": f"Agent {i:03d}",
                       "skills": "|".join(agent_skills), "languages": "|".join(agent_languages),
                       "available": "true" if rng.random() > 0.08 else "false",
                       "max_concurrent": rng.randint(4, 12), "shift_start_hour": 8,
                       "shift_end_hour": 18})
    customer_by_id = {x["customer_id"]: x for x in customers}
    agent_load = {x["agent_id"]: 0 for x in agents}
    tickets, messages, assignments, sla_events, resolutions, ground_truth = [], [], [], [], [], []
    ticket_ids = [make_id("TKT-2026-", i) for i in range(1, ticket_count + 1)]
    # Every ticket receives at least one message; the remaining messages are distributed deterministically.
    message_counts = [1] * ticket_count
    for _ in range(message_count - ticket_count):
        message_counts[rng.randrange(ticket_count)] += 1
    for idx, ticket_id in enumerate(ticket_ids, 1):
        customer = rng.choice(customers)
        intent = rng.choice(INTENTS)
        language = customer["language"]
        priority = PRIORITY_BY_INTENT[intent]
        channel = rng.choice(CHANNELS)
        created = start + timedelta(minutes=rng.randrange(90 * 24 * 60))
        sla_minutes = {"critical": 30, "high": 120, "normal": 480, "low": 1440}[priority]
        deadline = created + timedelta(minutes=sla_minutes)
        candidates = [a for a in agents if a["available"] == "true"
                      and intent in a["skills"].split("|")
                      and language in a["languages"].split("|")
                      and agent_load[a["agent_id"]] < a["max_concurrent"]]
        # Deterministic rule: prefer lowest active load, then stable agent ID.
        candidates.sort(key=lambda a: (agent_load[a["agent_id"]], a["agent_id"]))
        chosen = candidates[0] if candidates else None
        status = "assigned" if chosen else "unassigned"
        if chosen:
            agent_load[chosen["agent_id"]] += 1
            assignments.append({"assignment_id": f"ASN-{ticket_id}-001", "ticket_id": ticket_id,
                                 "agent_id": chosen["agent_id"], "queue_id": f"QUE-{intent.upper()}",
                                 "assigned_at": created.isoformat(),
                                 "reason": "skill_language_availability_capacity_match", "event_type": "assigned"})
        tickets.append({"ticket_id": ticket_id, "customer_id": customer["customer_id"], "channel": channel,
                        "intent": intent, "queue_id": f"QUE-{intent.upper()}", "language": language, "priority": priority,
                        "created_at": created.isoformat(), "sla_deadline": deadline.isoformat(),
                        "status": status, "assigned_agent_id": chosen["agent_id"] if chosen else ""})
        sla_events.append({"sla_event_id": f"SLA-{ticket_id}", "ticket_id": ticket_id,
                           "target_response_minutes": sla_minutes, "started_at": created.isoformat(),
                           "deadline_at": deadline.isoformat(), "sla_status": "open"})
        ticket_messages = []
        for j in range(1, message_counts[idx - 1] + 1):
            msg_time = created + timedelta(minutes=j * rng.randint(1, 20))
            message = {"message_id": f"MSG-{ticket_id}-{j:03d}", "ticket_id": ticket_id,
                       "channel": channel, "sender_type": ("customer" if (not chosen or j % 2) else "agent"),
                       "language": language, "sent_at": msg_time.isoformat(),
                       "body": f"Synthetic {intent} support message {j} for {ticket_id}."}
            messages.append(message)
            ticket_messages.append(message)
        # Outcome is derived from a documented deterministic rule, not an independent
        # random draw. The rule gives approximately 82% resolved records while being
        # reproducible and explainable from the ticket's stable attributes.
        channel_index = CHANNELS.index(channel)
        intent_index = INTENTS.index(intent)
        priority_weight = {"critical": 3, "high": 2, "normal": 1, "low": 0}[priority]
        outcome_score = (idx * 37 + channel_index * 13 + intent_index * 17 + priority_weight * 7) % 100
        if outcome_score < 82:
            duration_minutes = 5 + ((idx * 19 + intent_index * 11 + channel_index * 7) % max(6, sla_minutes * 2 - 4))
            resolved_at = created + timedelta(minutes=duration_minutes)
            # Resolution must not precede any message in the ticket thread.
            latest_message = max((datetime.fromisoformat(m["sent_at"]) for m in ticket_messages), default=created)
            if resolved_at <= latest_message:
                resolved_at = latest_message + timedelta(minutes=1)
            resolution_types = ["solved", "refunded", "explained", "escalated"]
            resolution_type = resolution_types[(idx + intent_index + channel_index) % len(resolution_types)]
            satisfaction = max(1, min(5, 4 - priority_weight + ((idx + intent_index) % 3) - 1))
            resolutions.append({"resolution_id": f"RES-{ticket_id}", "ticket_id": ticket_id,
                                "resolved_at": resolved_at.isoformat(), "resolution_type": resolution_type,
                                "customer_satisfaction": satisfaction})
    # Include five explicit, labelled anomaly examples, separate from baseline records.
    anomaly_specs = [
        ("agent_over_capacity", "Reject assignment when agent is at max concurrent capacity"),
        ("sla_calendar_mismatch", "Flag SLA deadline calculated against the wrong channel calendar"),
        ("reopen_history_lost", "Reopening must append an event and preserve the prior resolution"),
        ("transfer_loop", "Detect repeated A-to-B-to-A ticket transfers"),
        ("unsafe_priority", "Critical safety intent must not be assigned low priority"),
    ]
    for n, (issue_type, expected) in enumerate(anomaly_specs, 1):
        ground_truth.append({"case_id": f"ANOM-{n:03d}", "issue_type": issue_type,
                             "expected_behavior": expected, "is_deliberate_anomaly": "true"})

    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "customers.csv", customers)
    write_csv(output / "channels.csv", channels)
    write_csv(output / "intents.csv", intents)
    write_csv(output / "priority_rules.csv", priority_rules)
    write_csv(output / "queues.csv", queues)
    write_csv(output / "agents.csv", agents)
    write_csv(output / "tickets.csv", tickets)
    write_csv(output / "messages.csv", messages)
    write_csv(output / "assignment_events.csv", assignments)
    write_csv(output / "sla_events.csv", sla_events)
    write_csv(output / "resolutions.csv", resolutions)
    write_csv(output / "ground_truth.csv", ground_truth)
    # Recalculate assignments/deadlines and add lifecycle/SLA audit events as a
    # deterministic second pass over the generated records.
    from .integrate import integrate
    integration_report = integrate(output)
    # Create the five isolated labelled negative scenarios as part of every build.
    from .anomalies import create_fixtures
    create_fixtures(output)
    manifest = {"seed": seed, "mode": mode, "tickets": len(tickets), "agents": len(agents),
                "messages": len(messages), "customers": len(customers), "assignments": len(assignments),
                "sla_events": len(sla_events), "resolutions": len(resolutions),
                "integration": integration_report,
                "note": "Integrated synthetic data; SLA defaults are illustrative and must be aligned to the challenge specification."}
    # Provide JSON seed exports alongside CSV files for downstream consumers.
    for csv_path in sorted(output.glob("*.csv")):
        with csv_path.open(newline="", encoding="utf-8") as handle:
            json_rows = list(csv.DictReader(handle))
        (output / f"{csv_path.stem}.json").write_text(
            json.dumps(json_rows, indent=2), encoding="utf-8"
        )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic support-routing data")
    parser.add_argument("--mode", choices=["starter", "full"], default="starter")
    parser.add_argument("--seed", type=int, default=20261022)
    parser.add_argument("--output", type=Path, default=Path("data/starter"))
    parser.add_argument("--tickets", type=int)
    parser.add_argument("--agents", type=int)
    parser.add_argument("--messages", type=int)
    args = parser.parse_args()
    if args.mode == "full" and args.output == Path("data/starter"):
        args.output = Path("data/full")
    manifest = generate(args.output, args.mode, args.seed, args.tickets, args.agents, args.messages)
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
