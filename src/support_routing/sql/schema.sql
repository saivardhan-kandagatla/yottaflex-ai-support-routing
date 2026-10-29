PRAGMA foreign_keys = ON;

-- Master data
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    language TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    available INTEGER NOT NULL CHECK (available IN (0, 1)),
    max_concurrent INTEGER NOT NULL CHECK (max_concurrent > 0),
    shift_start_hour INTEGER NOT NULL CHECK (shift_start_hour BETWEEN 0 AND 23),
    shift_end_hour INTEGER NOT NULL CHECK (shift_end_hour BETWEEN 0 AND 24)
);
CREATE TABLE IF NOT EXISTS skills (
    skill_name TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS languages (
    language_code TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS agent_skills (
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    skill_name TEXT NOT NULL REFERENCES skills(skill_name),
    PRIMARY KEY (agent_id, skill_name)
);
CREATE TABLE IF NOT EXISTS agent_languages (
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    language_code TEXT NOT NULL REFERENCES languages(language_code),
    PRIMARY KEY (agent_id, language_code)
);

-- Domain dimensions and routing taxonomy
CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY,
    channel_name TEXT NOT NULL UNIQUE CHECK (channel_name IN ('email','chat','phone'))
);
CREATE TABLE IF NOT EXISTS intents (
    intent_id TEXT PRIMARY KEY,
    intent_name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS priority_rules (
    priority_rule_id TEXT PRIMARY KEY,
    intent_name TEXT NOT NULL UNIQUE REFERENCES intents(intent_name),
    required_priority TEXT NOT NULL CHECK (required_priority IN ('low','normal','high','critical','urgent')),
    rule_description TEXT NOT NULL,
    UNIQUE(intent_name, required_priority)
);
CREATE TABLE IF NOT EXISTS queues (
    queue_id TEXT PRIMARY KEY,
    queue_name TEXT NOT NULL,
    intent_name TEXT NOT NULL REFERENCES intents(intent_name),
    UNIQUE(queue_name, intent_name)
);

-- Tickets and conversation history
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    channel TEXT NOT NULL REFERENCES channels(channel_name),
    intent TEXT NOT NULL REFERENCES intents(intent_name),
    queue_id TEXT NOT NULL REFERENCES queues(queue_id),
    language TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('low', 'normal', 'high', 'critical', 'urgent')),
    created_at TEXT NOT NULL,
    sla_deadline TEXT NOT NULL,
    status TEXT NOT NULL,
    assigned_agent_id TEXT REFERENCES agents(agent_id),
    FOREIGN KEY (intent, priority) REFERENCES priority_rules(intent_name, required_priority)
);
CREATE INDEX IF NOT EXISTS idx_tickets_status_priority ON tickets(status, priority);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at);
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
    channel TEXT NOT NULL REFERENCES channels(channel_name),
    sender_type TEXT NOT NULL CHECK (sender_type IN ('customer', 'agent', 'system')),
    language TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    body TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_ticket_time ON messages(ticket_id, sent_at);
CREATE TABLE IF NOT EXISTS assignment_events (
    assignment_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    queue_id TEXT NOT NULL REFERENCES queues(queue_id),
    assigned_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('assigned', 'transferred', 'unassigned'))
);
CREATE INDEX IF NOT EXISTS idx_assignments_ticket_time ON assignment_events(ticket_id, assigned_at);
CREATE TABLE IF NOT EXISTS sla_events (
    sla_event_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
    target_response_minutes INTEGER NOT NULL CHECK (target_response_minutes > 0),
    started_at TEXT NOT NULL,
    deadline_at TEXT NOT NULL,
    sla_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS resolutions (
    resolution_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL UNIQUE REFERENCES tickets(ticket_id),
    resolved_at TEXT NOT NULL,
    resolution_type TEXT NOT NULL,
    customer_satisfaction INTEGER CHECK (customer_satisfaction BETWEEN 1 AND 5)
);
CREATE TABLE IF NOT EXISTS ticket_events (
    event_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
    event_type TEXT NOT NULL,
    event_at TEXT NOT NULL,
    actor_id TEXT,
    details TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket_time ON ticket_events(ticket_id, event_at);

-- SLA outcome audit trail (append-only event records)

CREATE TABLE IF NOT EXISTS sla_audit_events (
    audit_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
    event_type TEXT NOT NULL CHECK (event_type IN ('first_response_met','first_response_breached','resolution_met','resolution_breached')),
    deadline_at TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sla_audit_ticket_time ON sla_audit_events(ticket_id, occurred_at);
