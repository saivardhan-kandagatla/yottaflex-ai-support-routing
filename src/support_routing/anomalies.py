"""Create controlled anomaly fixtures and check whether each is detected.

These fixtures are deliberately separate from baseline tickets so invalid examples
never contaminate the normal dataset. The records are synthetic test cases.
"""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path

FIELDS = ["case_id", "issue_type", "observed_condition", "details"]
CASES = [
    {"case_id":"ANOM-001", "issue_type":"agent_over_capacity", "observed_condition":"active_count_exceeds_capacity", "details":"capacity=4;active_count=5"},
    {"case_id":"ANOM-002", "issue_type":"sla_calendar_mismatch", "observed_condition":"email_deadline_uses_elapsed_time", "details":"channel=email;calendar=business_hours;deadline_method=elapsed_time"},
    {"case_id":"ANOM-003", "issue_type":"reopen_history_lost", "observed_condition":"reopen_without_prior_resolution_event", "details":"prior_resolution_exists=true;resolution_event_preserved=false"},
    {"case_id":"ANOM-004", "issue_type":"transfer_loop", "observed_condition":"agent_sequence_repeats", "details":"agent_sequence=AGT-001|AGT-002|AGT-001"},
    {"case_id":"ANOM-005", "issue_type":"unsafe_priority", "observed_condition":"safety_intent_has_low_priority", "details":"intent=safety;priority=low;required_priority=critical"},
]
EXPECTED = {
    "agent_over_capacity": "Reject assignment when agent is at max concurrent capacity",
    "sla_calendar_mismatch": "Flag SLA deadline calculated against the wrong channel calendar",
    "reopen_history_lost": "Reopening must append an event and preserve the prior resolution",
    "transfer_loop": "Detect repeated A-to-B-to-A ticket transfers",
    "unsafe_priority": "Critical safety intent must not be assigned low priority",
}

def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields or list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)

def create_fixtures(output: Path) -> list[dict]:
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "anomaly_cases.csv", CASES, FIELDS)
    truth = [{"case_id": c["case_id"], "issue_type": c["issue_type"],
              "expected_behavior": EXPECTED[c["issue_type"]], "is_deliberate_anomaly":"true"} for c in CASES]
    write_csv(output / "ground_truth.csv", truth)
    return CASES

def detect(case: dict) -> bool:
    """Return True if the observed condition indicates its declared anomaly."""
    kind, condition, details = case["issue_type"], case["observed_condition"], case.get("details", "")
    if kind == "agent_over_capacity":
        parts = dict(p.split("=", 1) for p in details.split(";") if "=" in p)
        try: return condition == "active_count_exceeds_capacity" and int(parts["active_count"]) > int(parts["capacity"])
        except (KeyError, ValueError): return False
    if kind == "sla_calendar_mismatch":
        parts = dict(p.split("=", 1) for p in details.split(";") if "=" in p)
        return condition == "email_deadline_uses_elapsed_time" and parts.get("channel") == "email" and parts.get("calendar") == "business_hours" and parts.get("deadline_method") == "elapsed_time"
    if kind == "reopen_history_lost":
        parts = dict(p.split("=", 1) for p in details.split(";") if "=" in p)
        return condition == "reopen_without_prior_resolution_event" and parts.get("prior_resolution_exists") == "true" and parts.get("resolution_event_preserved") == "false"
    if kind == "transfer_loop":
        parts = dict(p.split("=", 1) for p in details.split(";") if "=" in p)
        sequence = parts.get("agent_sequence", "").split("|")
        return condition == "agent_sequence_repeats" and len(sequence) >= 3 and sequence[-1] == sequence[-3] and sequence[-1] != sequence[-2]
    if kind == "unsafe_priority":
        parts = dict(p.split("=", 1) for p in details.split(";") if "=" in p)
        return condition == "safety_intent_has_low_priority" and parts.get("intent") == "safety" and parts.get("priority") == "low" and parts.get("required_priority") == "critical"
    return False

def validate_anomalies(data_dir: Path) -> dict:
    with (data_dir / "anomaly_cases.csv").open(newline="", encoding="utf-8") as f:
        cases = list(csv.DictReader(f))
    with (data_dir / "ground_truth.csv").open(newline="", encoding="utf-8") as f:
        truth = {r["case_id"]: r for r in csv.DictReader(f)}
    results = []
    for case in cases:
        expected = truth.get(case["case_id"], {}).get("issue_type") == case["issue_type"]
        detected = detect(case)
        results.append({"case_id":case["case_id"], "issue_type":case["issue_type"], "detected":detected,
                        "ground_truth_matches":expected, "passed":detected and expected})
    return {"cases_checked":len(results), "detected":sum(r["detected"] for r in results),
            "passed":all(r["passed"] for r in results) and len(results) == 5, "results":results}

def main() -> None:
    parser = argparse.ArgumentParser(description="Create and validate the five controlled anomaly fixtures")
    parser.add_argument("--data", type=Path, default=Path("data/starter"))
    parser.add_argument("--report", type=Path, default=Path("reports/anomaly_validation.json"))
    parser.add_argument("--create", action="store_true", help="write the five isolated anomaly fixtures and ground truth")
    args = parser.parse_args()
    if args.create: create_fixtures(args.data)
    report = validate_anomalies(args.data)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["passed"]: raise SystemExit(1)

if __name__ == "__main__": main()
