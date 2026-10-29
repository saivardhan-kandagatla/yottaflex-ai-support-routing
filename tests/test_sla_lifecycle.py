import unittest
from datetime import datetime
from support_routing.sla import add_business_minutes, calculate_deadlines, assess_sla
from support_routing.lifecycle import TicketLifecycle

class SLATests(unittest.TestCase):
    def test_email_business_hours_skip_weekend(self):
        start = datetime.fromisoformat("2026-01-02T16:00:00")  # Friday
        result = add_business_minutes(start, 120)
        self.assertEqual(result.isoformat(), "2026-01-05T10:00:00")

    def test_chat_uses_elapsed_time(self):
        ticket = {"ticket_id": "T1", "channel": "chat", "priority": "high", "created_at": "2026-01-01T10:00:00"}
        deadlines = calculate_deadlines(ticket)
        self.assertEqual(deadlines["first_response_deadline"], "2026-01-01T10:15:00")

    def test_response_breach_is_recorded(self):
        ticket = {"ticket_id": "T1", "channel": "chat", "priority": "high", "created_at": "2026-01-01T10:00:00"}
        events = assess_sla(ticket, first_response_at="2026-01-01T10:16:00")
        self.assertEqual(events[0]["event_type"], "first_response_breached")

class LifecycleTests(unittest.TestCase):
    def test_reopen_preserves_history(self):
        life = TicketLifecycle("T1")
        life.transition("assigned", at="2026-01-01T10:00:00")
        life.transition("resolved", at="2026-01-01T11:00:00")
        life.transition("reopened", at="2026-01-02T09:00:00")
        self.assertEqual(len(life.events), 3)
        self.assertEqual(life.events[1]["event_type"], "resolved")

    def test_overdue_ticket_escalates(self):
        life = TicketLifecycle("T1")
        life.transition("assigned", at="2026-01-01T10:00:00")
        event = life.escalate_if_overdue(now="2026-01-01T10:30:00", deadline="2026-01-01T10:15:00")
        self.assertEqual(event["event_type"], "escalated")

    def test_invalid_transition_rejected(self):
        life = TicketLifecycle("T1")
        with self.assertRaises(ValueError):
            life.transition("resolved", at="2026-01-01T10:00:00")

if __name__ == "__main__":
    unittest.main()
