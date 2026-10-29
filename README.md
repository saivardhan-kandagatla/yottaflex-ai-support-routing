# YottaFlex AI — Support Routing Challenge

A deterministic Python implementation for synthetic support-ticket generation, explainable routing, SLA assessment, lifecycle history, anomaly fixtures, validation and SQLite loading.

## Requirements covered

- Generates 30,000 tickets, 100 agents, 100,000 messages and 15,000 customers in full mode across a 90-day ticket window using a fixed seed.
- Generates master dimensions for channels, intents, queues and intent-priority rules.
- Routes by skill, language, agent availability, configured shift and concurrency capacity.
- Preserves assignment, message, SLA, resolution and ticket-event history.
- Uses deterministic documented outcome rules and keeps deliberate anomaly labels in separate ground-truth fixtures.
- Exports CSV and JSON records plus a normalized SQLite database.
- Validates primary keys, references, event chronology, assignment eligibility and capacity timelines.

## Windows Command Prompt setup

Run from the repository root. If you do not have a virtual environment yet:

```bat
py -3.10 -m venv .venv
.venv\Scripts\activate.bat
set PYTHONPATH=src
```

Run tests:

```bat
python -m unittest discover -s tests -v
```

Generate and validate the full dataset:

```bat
python -m support_routing.generate --mode full --seed 20261022 --output data/full
python -m support_routing.validate --data data/full --report reports/full_validation_summary.json
python -m support_routing.database --data data/full --database data/support_routing_full.db
python -m support_routing.anomalies --data data/full --create --report reports/full_anomaly_validation.json
```

Starter mode uses the same generator at smaller scale:

```bat
python -m support_routing.generate --mode starter --seed 20261022 --output data/starter
python -m support_routing.validate --data data/starter --report reports/validation_summary.json
```

## SLA configuration

SLA targets are configured in `src/support_routing/sla.py`. Chat and phone use elapsed-time targets; email uses the configured business-hours calendar. The challenge page does not prescribe exact numeric targets, so the project documents its defaults as candidate-defined example policy. Adjust them if the recruitment team provides a more specific SLA policy. SLA outcomes are written to `sla_events.csv` and `sla_audit_events.csv`; the latter is also loaded into SQLite.

## Database model

`src/support_routing/sql/schema.sql` defines master tables (`customers`, `channels`, `intents`, `priority_rules`, `queues`, `agents`, `skills`, `languages`), bridge tables (`agent_skills`, `agent_languages`), and ticket/message/assignment/SLA/resolution/event tables. Foreign-key checks are run by the loader.

## Anomaly scenarios

The five controlled negative cases cover over-capacity assignment, incorrect email SLA calendar, lost resolution history after reopening, A-to-B-to-A transfer loop, and invalid low priority for safety intent. Fixtures are isolated from baseline rows and validated against `ground_truth.csv` so deliberate anomalies do not silently corrupt ordinary data.

## Important limitation

The baseline history fully models routing, responses, resolutions and overdue escalations. Full multi-agent transfer chains and multiple historical resolution records after reopening are not yet modeled end-to-end in the baseline tables; the corresponding required negative cases are currently represented as isolated labelled fixtures. Do not claim these workflows are fully simulated if the evaluator expects them in the main event history.

## Reproducibility and submission

The generator seed, mode, counts and integration summary are written to `data/<mode>/manifest.json`. Run generation twice with the same seed to reproduce identical output. Before submitting, push the source and tests to a public GitHub repository and submit its URL on the challenge portal. Do not include secrets or private data.
