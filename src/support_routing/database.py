"""Create a SQLite database from generated CSV files."""
from __future__ import annotations
import argparse, csv, json, sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "sql" / "schema.sql"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def create_database(data_dir: Path, database_path: Path) -> dict:
    """Load generated CSV data into normalized SQLite tables."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if database_path.exists():
        database_path.unlink()
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        customers = rows(data_dir / "customers.csv")
        channels = rows(data_dir / "channels.csv") if (data_dir / "channels.csv").exists() else [{"channel_id": f"CHN-{x}", "channel_name": x} for x in ("email", "chat", "phone")]
        intents = rows(data_dir / "intents.csv") if (data_dir / "intents.csv").exists() else []
        priority_rules = rows(data_dir / "priority_rules.csv") if (data_dir / "priority_rules.csv").exists() else []
        queues = rows(data_dir / "queues.csv") if (data_dir / "queues.csv").exists() else []
        agents = rows(data_dir / "agents.csv")
        tickets = rows(data_dir / "tickets.csv")
        messages = rows(data_dir / "messages.csv")
        assignments = rows(data_dir / "assignment_events.csv")
        slas = rows(data_dir / "sla_events.csv")
        resolutions = rows(data_dir / "resolutions.csv")
        ticket_events = rows(data_dir / "ticket_events.csv") if (data_dir / "ticket_events.csv").exists() else []
        sla_audit_events = rows(data_dir / "sla_audit_events.csv") if (data_dir / "sla_audit_events.csv").exists() else []

        connection.executemany("INSERT INTO customers VALUES (:customer_id,:language,:created_at)", customers)
        connection.executemany("INSERT INTO channels VALUES (:channel_id,:channel_name)", channels)
        if intents:
            connection.executemany("INSERT INTO intents VALUES (:intent_id,:intent_name)", intents)
        if priority_rules:
            connection.executemany("INSERT INTO priority_rules VALUES (:priority_rule_id,:intent_name,:required_priority,:rule_description)", priority_rules)
        if queues:
            connection.executemany("INSERT INTO queues VALUES (:queue_id,:queue_name,:intent_name)", queues)
        connection.executemany(
            "INSERT INTO agents VALUES (:agent_id,:name,:available,:max_concurrent,:shift_start_hour,:shift_end_hour)",
            [{**a, "available": int(a["available"].lower() == "true")} for a in agents],
        )
        skill_set, language_set = set(), set()
        agent_skill_rows, agent_language_rows = [], []
        for agent in agents:
            for skill in filter(None, agent["skills"].split("|")):
                skill_set.add(skill); agent_skill_rows.append((agent["agent_id"], skill))
            for language in filter(None, agent["languages"].split("|")):
                language_set.add(language); agent_language_rows.append((agent["agent_id"], language))
        connection.executemany("INSERT INTO skills VALUES (?)", [(x,) for x in sorted(skill_set)])
        connection.executemany("INSERT INTO languages VALUES (?)", [(x,) for x in sorted(language_set)])
        connection.executemany("INSERT INTO agent_skills VALUES (?,?)", agent_skill_rows)
        connection.executemany("INSERT INTO agent_languages VALUES (?,?)", agent_language_rows)
        connection.executemany(
            "INSERT INTO tickets (ticket_id,customer_id,channel,intent,queue_id,language,priority,created_at,sla_deadline,status,assigned_agent_id) VALUES (:ticket_id,:customer_id,:channel,:intent,:queue_id,:language,:priority,:created_at,:sla_deadline,:status,:assigned_agent_id)",
            [dict(t, assigned_agent_id=t["assigned_agent_id"] or None) for t in tickets],
        )
        connection.executemany("INSERT INTO messages VALUES (:message_id,:ticket_id,:channel,:sender_type,:language,:sent_at,:body)", messages)
        connection.executemany("INSERT INTO assignment_events (assignment_id,ticket_id,agent_id,queue_id,assigned_at,reason,event_type) VALUES (:assignment_id,:ticket_id,:agent_id,:queue_id,:assigned_at,:reason,:event_type)", assignments)
        connection.executemany("INSERT INTO sla_events VALUES (:sla_event_id,:ticket_id,:target_response_minutes,:started_at,:deadline_at,:sla_status)", slas)
        connection.executemany("INSERT INTO resolutions VALUES (:resolution_id,:ticket_id,:resolved_at,:resolution_type,:customer_satisfaction)", resolutions)
        connection.executemany("INSERT INTO ticket_events VALUES (:event_id,:ticket_id,:event_type,:event_at,:actor_id,:details)", ticket_events)
        connection.executemany("INSERT INTO sla_audit_events (ticket_id,event_type,deadline_at,occurred_at) VALUES (:ticket_id,:event_type,:deadline_at,:occurred_at)", sla_audit_events)
        connection.commit()
        counts = {}
        for table in ("customers", "channels", "intents", "priority_rules", "queues", "agents", "skills", "languages", "agent_skills", "agent_languages", "tickets", "messages", "assignment_events", "sla_events", "resolutions", "ticket_events", "sla_audit_events"):
            counts[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return {"database": str(database_path), "counts": counts, "foreign_key_errors": connection.execute("PRAGMA foreign_key_check").fetchall()}
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load generated CSV data into SQLite")
    parser.add_argument("--data", type=Path, default=Path("data/starter"))
    parser.add_argument("--database", type=Path, default=Path("data/support_routing.db"))
    args = parser.parse_args()
    result = create_database(args.data, args.database)
    print(json.dumps(result, indent=2))
    if result["foreign_key_errors"]:
        raise SystemExit("Database foreign-key check failed")

if __name__ == "__main__":
    main()
