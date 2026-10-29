# Windows execution guide (Command Prompt)

Run commands from the repository root: `yottaflex-support-routing-complete-project`.

## 1. Create/activate Python environment

```bat
py -3.10 -m venv .venv
.venv\Scripts\activate.bat
set PYTHONPATH=src
```

If `.venv` already exists and is active, skip the first two commands. This project uses the Python standard library only.

## 2. Run tests

```bat
python -m unittest discover -s tests -v
```

Expected: **17 tests pass**.

## 3. Generate full dataset and verify

```bat
python -m support_routing.generate --mode full --seed 20261022 --output data/full
python -m support_routing.validate --data data/full --report reports/full_validation_summary.json
python -m support_routing.database --data data/full --database data/support_routing_full.db
python -m support_routing.anomalies --data data/full --report reports/full_anomaly_validation.json
```

Full mode defaults to 30,000 tickets, 100 agents, 100,000 messages, and 15,000 customers. Generation also writes CSV and JSON exports, master dimensions, lifecycle events, SLA audit events, ground truth, and a manifest.

## 4. GitHub submission checklist

- Review `README.md`, `docs/data_dictionary.md`, and `docs/challenge_compliance_review.md`.
- Push the code and tests to a **public** GitHub repository.
- Do not commit secrets, credentials, `.env` files, or private data.
- Large generated data and SQLite files may be omitted from Git if the portal does not require them; retain reproducible commands and reports.
- Open the public repository in a private/incognito browser to confirm it is accessible.
- Submit the repository URL on the YottaFlex portal only after reviewing the scope limitations and requirements.

## Important scope note

The five negative cases are isolated labelled fixtures. The ordinary baseline models assignment, response, resolution and escalation. It does not yet fully model multi-agent transfer chains or multiple historical resolution records after reopening. Do not claim these are fully simulated end-to-end unless you extend that implementation.
