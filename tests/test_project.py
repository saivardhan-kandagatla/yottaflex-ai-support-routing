import tempfile
import unittest
from pathlib import Path
from support_routing.generate import generate
from support_routing.validate import validate

class GeneratorTests(unittest.TestCase):
    def test_small_dataset_is_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "data"
            manifest = generate(out, "starter", 123, ticket_count=20, agent_count=10, message_count=60)
            report = validate(out)
            self.assertEqual(manifest["tickets"], 20)
            self.assertEqual(manifest["messages"], 60)
            self.assertTrue(report["passed"], report["integrity_errors"][:5])

    def test_seed_is_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp)/"one", Path(temp)/"two"
            generate(first, "starter", 456, ticket_count=12, agent_count=8, message_count=36)
            generate(second, "starter", 456, ticket_count=12, agent_count=8, message_count=36)
            self.assertEqual((first/"tickets.csv").read_bytes(), (second/"tickets.csv").read_bytes())
            self.assertEqual((first/"messages.csv").read_bytes(), (second/"messages.csv").read_bytes())

    def test_integrated_generation_writes_sla_and_lifecycle_events(self):
        import csv
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "data"
            generate(out, "starter", 789, ticket_count=12, agent_count=8, message_count=36)
            for filename in ("ticket_events.csv", "sla_audit_events.csv"):
                self.assertTrue((out / filename).exists(), filename)
                with (out / filename).open(newline="", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                self.assertGreater(len(rows), 0, filename)
            with (out / "tickets.csv").open(newline="", encoding="utf-8") as f:
                tickets = list(csv.DictReader(f))
            self.assertTrue(all("first_response_deadline" in t and "resolution_deadline" in t for t in tickets))
            with (out / "messages.csv").open(newline="", encoding="utf-8") as f:
                messages = list(csv.DictReader(f))
            with (out / "resolutions.csv").open(newline="", encoding="utf-8") as f:
                resolutions = list(csv.DictReader(f))
            latest_message = {}
            for message in messages:
                latest_message[message["ticket_id"]] = max(
                    latest_message.get(message["ticket_id"], message["sent_at"]), message["sent_at"]
                )
            for resolution in resolutions:
                self.assertGreater(resolution["resolved_at"], latest_message[resolution["ticket_id"]])
            with (out / "sla_events.csv").open(newline="", encoding="utf-8") as f:
                sla_rows = list(csv.DictReader(f))
            self.assertTrue(all(row["sla_status"] in {"open", "met", "breached"} for row in sla_rows))
            self.assertTrue((out / "channels.json").exists())

if __name__ == "__main__": unittest.main()
