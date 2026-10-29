# Review status and Windows run guide

## Verified in this package

- 17 unit tests pass.
- Full dataset: 30,000 tickets, 100 agents, 100,000 messages, 15,000 customers.
- Deterministic seed `20261022`; key CSV files were regenerated twice and SHA-256 compared with matching results.
- Routing checks skill, language, availability, shift window (when timestamp is supplied), safety priority and capacity.
- Validator checks keys/references, safety priority, chronology, lifecycle transitions, assignment history and observed concurrent capacity.
- SLA status is recorded as `open`, `met` or `breached`; SLA audit records are persisted in SQLite.
- SQLite foreign-key check returns no errors.
- All 5 isolated anomaly fixtures match their ground-truth labels.

## Windows Command Prompt

```bat
py -3.10 -m venv .venv
.venv\Scripts\activate.bat
set PYTHONPATH=src
python -m unittest discover -s tests -v
python -m support_routing.generate --mode full --seed 20261022 --output data/full
python -m support_routing.validate --data data/full --report reports/full_validation_summary.json
python -m support_routing.database --data data/full --database data/support_routing_full.db
python -m support_routing.anomalies --data data/full --report reports/full_anomaly_validation.json
```

Skip environment creation/activation if already done. Run one command at a time.

## Remaining scope limitations

The challenge page requires transfers, escalations and reopenings. Escalation is represented in the baseline lifecycle. Full multi-agent transfer chains and multiple historical resolution records after reopening are not yet modeled end-to-end in the baseline event tables. The five corresponding negative cases are isolated labelled fixtures rather than corruption of ordinary records. The SLA values are documented, configurable candidate-defined defaults because the challenge page does not state exact numeric targets. See `docs/challenge_compliance_review.md`.
