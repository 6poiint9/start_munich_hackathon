"""Initial schema.

Every table carries workspace_id, and every UNIQUE key starts with it
(docs/skalierung.md N3). An applied migration is never changed. A fix is a
new file (docs/betrieb-und-wartung.md W2).
"""

import sqlite3

_WS = "workspace_id TEXT NOT NULL"

_TABLES = f"""
CREATE TABLE files (
    id INTEGER PRIMARY KEY, {_WS},
    path TEXT NOT NULL, sha256 TEXT NOT NULL, version INTEGER NOT NULL,
    bytes INTEGER, blob_key TEXT, doc_class TEXT, parser TEXT, kind TEXT,
    priority INTEGER NOT NULL DEFAULT 3,
    first_seen_at TEXT NOT NULL, replaced_at TEXT,
    is_current INTEGER NOT NULL DEFAULT 1,
    parse_status TEXT NOT NULL DEFAULT 'new', parse_error TEXT,
    UNIQUE (workspace_id, path, sha256)
);
CREATE TABLE facts (
    id INTEGER PRIMARY KEY, {_WS},
    fact_type TEXT NOT NULL,
    component_id TEXT, product_id TEXT, supplier_id TEXT,
    po_number TEXT, po_line TEXT, batch TEXT, rev TEXT, ref TEXT,
    qty REAL, unit TEXT, value_num REAL, value_text TEXT, data TEXT,
    eta TEXT, valid_until TEXT, doc_date TEXT, as_of TEXT,
    source_file_id INTEGER, source_locator TEXT,
    source_rank INTEGER NOT NULL DEFAULT 5,
    confidence REAL NOT NULL DEFAULT 1.0,
    extracted_by TEXT NOT NULL DEFAULT 'parser',
    site_id TEXT,
    suspicious INTEGER NOT NULL DEFAULT 0, suspicious_reason TEXT,
    needs_review INTEGER NOT NULL DEFAULT 0,
    source_removed INTEGER NOT NULL DEFAULT 0,
    superseded_by INTEGER, created_at TEXT NOT NULL
);
CREATE INDEX facts_type ON facts (workspace_id, fact_type, component_id);
CREATE INDEX facts_file ON facts (workspace_id, source_file_id);
CREATE TABLE products (
    {_WS}, product_id TEXT NOT NULL, description TEXT,
    demand_units REAL, packed REAL, still_to_pack REAL, rate_per_hour REAL,
    PRIMARY KEY (workspace_id, product_id)
);
CREATE TABLE bom_lines (
    {_WS}, product_id TEXT NOT NULL, component_id TEXT NOT NULL,
    qty_per REAL NOT NULL, valid_from TEXT, valid_to TEXT,
    PRIMARY KEY (workspace_id, product_id, component_id)
);
CREATE TABLE components (
    {_WS}, component_id TEXT NOT NULL, description TEXT, category TEXT,
    need_remaining REAL, single_source INTEGER,
    stocked INTEGER NOT NULL DEFAULT 1, carrier_component_id TEXT,
    released_rev TEXT, erp_stock REAL, usable_stock REAL, inbound_ok REAL,
    gap_qty REAL, status TEXT, updated_at TEXT,
    PRIMARY KEY (workspace_id, component_id)
);
CREATE TABLE demand_lines (
    id INTEGER PRIMARY KEY, {_WS},
    product_id TEXT NOT NULL, class TEXT NOT NULL, units REAL NOT NULL,
    due_at TEXT NOT NULL, source TEXT NOT NULL,
    UNIQUE (workspace_id, product_id, class, due_at)
);
CREATE TABLE build_status (
    {_WS}, as_of TEXT NOT NULL, product_id TEXT NOT NULL,
    packed REAL, still_to_pack REAL, rate_per_hour REAL,
    source_file_id INTEGER,
    PRIMARY KEY (workspace_id, product_id, as_of)
);
CREATE TABLE cases (
    id INTEGER PRIMARY KEY, {_WS},
    kind TEXT NOT NULL, rule TEXT,
    component_id TEXT, product_id TEXT, supplier_id TEXT, po_number TEXT,
    title TEXT NOT NULL, impact TEXT NOT NULL DEFAULT 'deadline_blocker',
    due_at TEXT, act_by TEXT, owner_role TEXT,
    state TEXT NOT NULL DEFAULT 'open', rank INTEGER,
    evidence_fact_ids TEXT, detail TEXT, dedupe_key TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE (workspace_id, dedupe_key)
);
CREATE TABLE gaps (
    id INTEGER PRIMARY KEY, {_WS},
    case_id INTEGER, component_id TEXT NOT NULL, product_id TEXT,
    site_id TEXT, due_at TEXT, gap_qty REAL NOT NULL,
    units_at_risk REAL, residual_qty REAL, breaks_at TEXT, act_by TEXT,
    impact TEXT NOT NULL DEFAULT 'deadline_blocker', rank INTEGER,
    explanation TEXT, evidence_fact_ids TEXT, detail TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    is_current INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE contradictions (
    id INTEGER PRIMARY KEY, {_WS},
    component_id TEXT, fact_a_id INTEGER, fact_b_id INTEGER, kind TEXT,
    winner_fact_id INTEGER, rule TEXT, status TEXT NOT NULL DEFAULT 'open',
    dedupe_key TEXT NOT NULL, created_at TEXT NOT NULL,
    UNIQUE (workspace_id, dedupe_key)
);
CREATE TABLE booking_findings (
    id INTEGER PRIMARY KEY, {_WS},
    case_id INTEGER, gr_fact_id INTEGER, gr_number TEXT NOT NULL,
    component_id TEXT, supplier_id TEXT, po_number TEXT, po_line TEXT,
    booked_qty REAL, proposed_qty REAL, delta_qty REAL, cause TEXT,
    checks TEXT, agreeing_sources INTEGER, confidence REAL,
    status TEXT NOT NULL, booked_at TEXT, detected_at TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    UNIQUE (workspace_id, idempotency_key)
);
CREATE TABLE corrections (
    id INTEGER PRIMARY KEY, {_WS},
    finding_id INTEGER NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL,
    approver_role TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'proposed',
    approved_by TEXT, approved_at TEXT, reject_reason TEXT,
    writer TEXT, external_ref TEXT, idempotency_key TEXT NOT NULL,
    verified_at TEXT, created_at TEXT NOT NULL,
    UNIQUE (workspace_id, idempotency_key)
);
CREATE TABLE options (
    id INTEGER PRIMARY KEY, {_WS},
    gap_id INTEGER, case_id INTEGER, kind TEXT NOT NULL,
    title TEXT, qty_gain REAL, units_gained TEXT, arrives_at TEXT,
    cost_eur REAL NOT NULL DEFAULT 0, confidence REAL NOT NULL DEFAULT 0.3,
    valid_until TEXT, feasible INTEGER NOT NULL DEFAULT 1,
    infeasible_reason TEXT, role_in_plan TEXT NOT NULL DEFAULT 'none',
    status TEXT NOT NULL DEFAULT 'candidate',
    needs_roles TEXT, evidence_fact_ids TEXT, supplier_id TEXT,
    action_kind TEXT, action_id INTEGER, decision_id INTEGER,
    dedupe_key TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE (workspace_id, dedupe_key)
);
CREATE TABLE decisions (
    id INTEGER PRIMARY KEY, {_WS},
    case_id INTEGER, gap_id INTEGER, title TEXT NOT NULL,
    options TEXT, recommended_option INTEGER, explanation TEXT,
    approver_role TEXT, approver_name TEXT, needs_roles TEXT,
    policy_ref TEXT, deadline TEXT, escalation_level INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open', decided_by TEXT, decided_at TEXT,
    reject_reason TEXT, dedupe_key TEXT NOT NULL, created_at TEXT NOT NULL,
    UNIQUE (workspace_id, dedupe_key)
);
CREATE TABLE actions (
    id INTEGER PRIMARY KEY, {_WS},
    case_id INTEGER, gap_id INTEGER, decision_id INTEGER, option_id INTEGER,
    type TEXT NOT NULL, kind TEXT, target TEXT,
    status TEXT NOT NULL DEFAULT 'proposed',
    idempotency_key TEXT NOT NULL, due_at TEXT, result TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (workspace_id, idempotency_key)
);
CREATE TABLE emails (
    id INTEGER PRIMARY KEY, {_WS},
    action_id INTEGER, case_id INTEGER, direction TEXT NOT NULL,
    from_addr TEXT, to_addr TEXT, subject TEXT, body TEXT, language TEXT,
    message_id TEXT, in_reply_to TEXT, po_ref TEXT,
    status TEXT NOT NULL, routine INTEGER NOT NULL DEFAULT 0,
    commits_money INTEGER NOT NULL DEFAULT 0, reason TEXT,
    approved_by TEXT, sent_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY, {_WS},
    type TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 2,
    payload TEXT NOT NULL DEFAULT '{{}}',
    dedupe_key TEXT, coalesce_key TEXT, partition_key TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0, available_at TEXT NOT NULL,
    locked_by TEXT, locked_until TEXT, created_at TEXT NOT NULL,
    handled_by TEXT, finished_at TEXT, error TEXT,
    UNIQUE (workspace_id, dedupe_key)
);
CREATE UNIQUE INDEX events_coalesce ON events (workspace_id, coalesce_key)
    WHERE status = 'pending' AND coalesce_key IS NOT NULL;
CREATE INDEX events_claim ON events (status, priority, id);
CREATE TABLE aliases (
    {_WS}, supplier_id TEXT NOT NULL DEFAULT '',
    supplier_part TEXT NOT NULL, component_id TEXT NOT NULL,
    PRIMARY KEY (workspace_id, supplier_id, supplier_part)
);
CREATE TABLE contacts (
    {_WS}, supplier_id TEXT NOT NULL, name TEXT, contact_name TEXT,
    email TEXT, language TEXT, source_file_id INTEGER, as_of TEXT,
    PRIMARY KEY (workspace_id, supplier_id)
);
CREATE TABLE schema_maps (
    {_WS}, signature TEXT NOT NULL, kind TEXT NOT NULL,
    mapping TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, signature, kind)
);
CREATE TABLE llm_calls (
    id INTEGER PRIMARY KEY, {_WS},
    file_id INTEGER, purpose TEXT, model TEXT,
    tokens_in INTEGER, tokens_out INTEGER, ms INTEGER,
    cache_hit INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE llm_cache (
    {_WS}, cache_key TEXT NOT NULL, response TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, cache_key)
);
"""


def up(conn: sqlite3.Connection) -> None:
    """Creates all tables of the first version."""
    conn.executescript(_TABLES)
