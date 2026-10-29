# Controlled anomaly scenarios

These fixtures are deliberately separate from baseline ticket data. Each fixture describes an observed invalid condition, and `ground_truth.csv` records the expected scenario label.

| Case | Scenario | Detector expectation |
|---|---|---|
| ANOM-001 | Agent over capacity | Active workload is greater than capacity |
| ANOM-002 | SLA calendar mismatch | Email uses elapsed-time deadline rather than configured business-hours calendar |
| ANOM-003 | Reopening history lost | Prior resolution existed but is not preserved in event history |
| ANOM-004 | Transfer loop | Agent sequence repeats A → B → A |
| ANOM-005 | Unsafe priority | Safety intent has low priority instead of critical |

Run the fixture generator and validator:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m support_routing.anomalies --data data/starter --create --report reports/anomaly_validation.json
```

The report includes one result per case and an overall pass flag. The current implementation validates controlled fixtures; it does not yet claim to detect these anomalies automatically across every generated ticket/event record.
