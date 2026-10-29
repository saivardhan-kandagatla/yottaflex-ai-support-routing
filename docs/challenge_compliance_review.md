# YottaFlex challenge compliance review

Source reviewed: user's screen recording of the YottaFlex.ai “72 Hours Code Challenge” page for Associate AI Forward Deployed Engineers.

## Requirements visible in the challenge page

- Route email/chat/phone cases by intent, urgency, language, skill and agent capacity while tracking SLA.
- Expose decisions and exceptions, preserve traceability, and produce measurable outputs.
- Generate/reference master data before dependent records.
- Include Customer, Channel, Ticket, Message, Intent, Language, PriorityRule, Agent, Skill, Queue, AssignmentEvent, SLAEvent and Resolution entities.
- Define primary/foreign keys, cardinalities, optional relationships, effective dates/lifecycle states, bridge tables for many-to-many relationships, and event history.
- Generate 30,000 tickets, 100 agents, 100,000 messages and a 90-day event window with a fixed seed.
- Include language mismatch, critical incidents, queue spikes and after-hours arrivals.
- Define agent skills, languages, shifts and concurrency limits; simulate transfers, escalations, reopenings, resolution and customer satisfaction.
- Derive totals/statuses/dates from source records and documented rules, not independent random assignment.
- Keep deliberate anomaly cases labelled with `issue_type`/ground truth.
- Validate uniqueness, foreign keys, allowed values, date ordering, reconciliation, lifecycle transitions and duplicates.
- Export CSV/JSON/SQL seed data, README, schema/data dictionary, generator command, fixed seed, source manifest and validation summary.
- Demonstrate same-seed reproducibility.
- Before submission: push code to a public GitHub repository, include README and tests, and submit the repository URL. The portal warns that submission is final.

## Current verification

| Requirement/check | Current evidence | Status |
|---|---|---|
| Required volume and fixed seed | Full generator output: 30,000 tickets, 100 agents, 100,000 messages, 15,000 customers; 90-day ticket window | Pass |
| Master dimensions | Channels, intents, priority rules and queues exported and loaded into SQLite | Pass |
| Skills/language/availability/capacity routing | Rule-based routing plus validation of eligibility and active concurrency | Pass for implemented checks |
| Shift-aware routing | Shift window enforced when `created_at` is supplied; tests include an after-hours case | Pass for implemented checks |
| Referential integrity | Full validation has no integrity errors; SQLite foreign-key check empty | Pass |
| Event chronology | Validator checks message/resolution chronology and ticket lifecycle ordering | Pass for implemented checks |
| SLA status and audit persistence | `sla_events.csv`, `sla_audit_events.csv`, SQLite table and report output | Pass for configured policy |
| Reproducibility | Key full-data CSV files compared across two same-seed generation runs; SHA-256 matched | Pass |
| Five labelled negative cases | All five isolated fixtures detected and matched to ground truth | Pass as fixture tests |
| Public GitHub repository | Not performed by this code build; requires user account/action | Pending |
| Full multi-agent transfer history | Not implemented end-to-end in baseline event stream | Gap |
| Multiple historical resolutions after reopening | Baseline `resolutions.csv` and SQL schema still model at most one resolution per ticket | Gap |
| Queue spikes as an explicit controlled workload pattern | No dedicated queue-spike metric/fixture has been added | Gap / improve |
| SLA target values | Challenge page asks to define SLA calendars but does not prescribe exact numeric targets; defaults are candidate-defined and configurable | Documented assumption |

## Verified test outputs

- `python -m unittest discover -s tests -v`: **17 tests passed**.
- Full data validation: **passed**, no integrity errors; 12,582 assignment events; 17,418 tickets without an assignment; observed maximum concurrent assignments was 2 in this seed's dataset.
- SQLite: 30,000 tickets, 100,000 messages, 12,582 assignment events, 30,000 SLA records, 24,623 resolutions, 74,538 ticket events and 25,268 SLA audit events; no foreign-key errors.
- Controlled anomalies: 5/5 detected and ground-truth labels matched.
- Same-seed reproducibility: SHA-256 matched for tickets, messages, assignments, SLA records, SLA audit records, ticket events, resolutions, ground truth, channels and queues.

## Honest submission guidance

The current code is stronger and the validation is stricter, but it should not be described as fully meeting every workflow requirement yet. The most important remaining engineering tasks are: implement real transfer chains with assignment/capacity history; support reopening with multiple resolution records; add a measurable queue-spike workload/metric; and publish to a public GitHub repository. SLA defaults are explicitly documented and should be adjusted if the recruiting team supplies a more specific policy.
