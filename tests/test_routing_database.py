import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path
from support_routing.routing import route_ticket
from support_routing.generate import generate
from support_routing.database import create_database

class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.ticket = {"ticket_id": "TKT-1", "intent": "payment", "language": "en", "priority": "high"}
        self.agents = [
            {"agent_id": "AGT-2", "skills": "payment|refund", "languages": "en|hi", "available": "true", "max_concurrent": "3"},
            {"agent_id": "AGT-1", "skills": "payment", "languages": "en", "available": "true", "max_concurrent": "3"},
        ]

    def test_routes_to_lowest_load_then_agent_id(self):
        result = route_ticket(self.ticket, self.agents, {"AGT-2": 1, "AGT-1": 0})
        self.assertEqual(result.agent_id, "AGT-1")
        self.assertEqual(result.eligible_agent_count, 2)

    def test_rejects_agent_at_capacity(self):
        result = route_ticket(self.ticket, [self.agents[1]], {"AGT-1": 3})
        self.assertIsNone(result.agent_id)

    def test_requires_skill_and_language(self):
        result = route_ticket({**self.ticket, "language": "te"}, self.agents, {})
        self.assertIsNone(result.agent_id)

    def test_rejects_agent_outside_shift_when_timestamp_provided(self):
        ticket = {**self.ticket, "created_at": "2026-01-01T02:00:00+00:00"}
        agents = [{**self.agents[0], "shift_start_hour": "8", "shift_end_hour": "18"}]
        result = route_ticket(ticket, agents, {})
        self.assertIsNone(result.agent_id)

    def test_blocks_safety_with_invalid_priority(self):
        result = route_ticket({**self.ticket, "intent": "safety", "priority": "low"}, self.agents, {})
        self.assertIsNone(result.agent_id)
        self.assertEqual(result.reason, "blocked_invalid_safety_priority")

class DatabaseTests(unittest.TestCase):
    def test_database_loads_and_foreign_keys_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data, db = root / "data", root / "support.db"
            generate(data, "starter", 123, ticket_count=10, agent_count=5, message_count=30)
            report = create_database(data, db)
            self.assertEqual(report["counts"]["tickets"], 10)
            self.assertEqual(report["foreign_key_errors"], [])
            # sqlite3 connection context managers commit/rollback but do not close.
            # Explicitly close the handle so TemporaryDirectory cleanup works on Windows.
            with closing(sqlite3.connect(db)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 30)

if __name__ == "__main__":
    unittest.main()
