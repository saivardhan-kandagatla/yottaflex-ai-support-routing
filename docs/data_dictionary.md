# Data dictionary and relationships

All timestamps are ISO-8601 UTC strings. IDs are stable within a generation run. Each generated CSV has a same-named JSON export, and the SQLite schema is under `src/support_routing/sql/schema.sql`.

| File / entity | Primary key | Purpose / rules |
|---|---|---|
| `customers.csv` / Customer | `customer_id` | Customer language and creation timestamp. |
| `channels.csv` / Channel | `channel_id` | Allowed channels: email, chat, phone. |
| `intents.csv` / Intent | `intent_id` | Intent taxonomy. |
| `priority_rules.csv` / PriorityRule | `priority_rule_id` | Documented required priority per intent; safety is critical. |
| `queues.csv` / Queue | `queue_id` | One logical queue per intent. |
| `agents.csv` / Agent | `agent_id` | Skills, languages, availability, shift window and concurrency limit. |
| `tickets.csv` / Ticket | `ticket_id` | Customer, channel, intent, queue, language, priority, status and assigned agent. |
| `messages.csv` / Message | `message_id` | Threaded customer/agent messages; sent after ticket creation. |
| `assignment_events.csv` / AssignmentEvent | `assignment_id` | Agent, queue, timestamp, decision reason and event type. |
| `sla_events.csv` / SLAEvent | `sla_event_id` | One first-response SLA record per ticket, with target, deadline and status. |
| `sla_audit_events.csv` / SLA audit event | Composite/autoincrement in SQL | Met/breached first-response and resolution outcomes. |
| `resolutions.csv` / Resolution | `resolution_id` | Optional resolution and 1–5 customer satisfaction score. |
| `ticket_events.csv` / TicketEvent | `event_id` | Append-only lifecycle transition history. |
| `ground_truth.csv` / Ground truth | `case_id` | Expected labels for the five controlled negative scenarios. |
| `anomaly_cases.csv` / Anomaly fixture | `case_id` | Isolated labelled negative test cases, separate from baseline rows. |
| `manifest.json` | N/A | Seed, mode, record counts and integration summary. |

## Relationship cardinality

- Customer 1:N Ticket.
- Channel 1:N Ticket and Message.
- Intent 1:N Ticket and Queue.
- Intent 1:1 baseline PriorityRule.
- Queue 1:N Ticket and AssignmentEvent.
- Ticket 1:N Message, AssignmentEvent, TicketEvent and SLA audit event.
- Ticket 1:1 first-response SLA record.
- Ticket 0:1 current Resolution in the baseline generator.
- Agent N:M Skill and Agent N:M Language through `agent_skills` and `agent_languages` bridge tables in SQLite.

## Generation and validation rules

- `--seed 20261022` reproduces generated data. Resolution eligibility and outcome values use a documented deterministic rule based on stable ticket attributes/index, not an independent random draw.
- A resolution is moved after the latest message in its ticket thread to preserve chronology.
- Routing checks availability, skill, language, shift window (when `created_at` is provided), and active capacity.
- The validator checks IDs, foreign keys, safety priority, event chronology, assignment eligibility and observed concurrent capacity.
- Numeric SLA targets and the email business-hours calendar are configurable examples because the challenge page asks candidates to define SLA calendars but does not prescribe exact numeric targets. See `src/support_routing/sla.py`.

## Known scope boundary

The five required negative scenarios are isolated labelled fixtures and are tested against their ground truth. The ordinary baseline event generator records assignment, response, resolution and overdue escalation histories. It does not yet model full multi-agent transfer chains or multiple historical resolutions after a ticket is reopened in the baseline tables; those are important extensions if the evaluator expects them in the main 30,000-ticket history rather than as controlled scenario fixtures.
