/**
 * Turns raw JSON from the API into the shapes of `lib/types.ts`.
 *
 * The backend grows step by step. A missing list becomes an empty list, a
 * missing object becomes an object with defaults, and a leaf with the wrong
 * type becomes `null`. The page never reads raw JSON.
 */

import type {
  Action,
  Approval,
  ApprovalDone,
  ApprovalMail,
  Block,
  CaseDetail,
  CaseSummary,
  CaseView,
  Check,
  Correction,
  Decision,
  Email,
  Evidence,
  EvidenceFile,
  Finding,
  FirstStop,
  LineguardState,
  LogEvent,
  Option,
  Person,
  Problem,
  Product,
  ShortLine,
  SyncResult,
} from './types';

type Json = Record<string, unknown>;

function isRecord(value: unknown): value is Json {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function record(value: unknown): Json {
  return isRecord(value) ? value : {};
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function numberOrNull(value: unknown): number | null {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function numberOrZero(value: unknown): number {
  return numberOrNull(value) ?? 0;
}

function textOrNull(value: unknown): string | null {
  if (typeof value === 'string') {
    return value.trim() === '' ? null : value;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}

/** SQLite sends booleans as 0 and 1. */
function flag(value: unknown): boolean {
  return value === true || value === 1 || value === '1' || value === 'true';
}

function textList(value: unknown): string[] {
  return list(value).flatMap((item) => {
    const text = textOrNull(item);
    return text === null ? [] : [text];
  });
}

function numberList(value: unknown): number[] {
  return list(value).flatMap((item) => {
    const parsed = numberOrNull(item);
    return parsed === null ? [] : [parsed];
  });
}

/** Keeps the entries that carry a usable id. */
function withId<T>(value: unknown, build: (raw: Json, id: number) => T): T[] {
  return list(value).flatMap((item) => {
    const raw = record(item);
    const id = numberOrNull(raw.id);
    return id === null ? [] : [build(raw, id)];
  });
}

function caseSummary(raw: Json, id: number): CaseSummary {
  const pending = record(raw.pending);
  return {
    id,
    kind: textOrNull(raw.kind) ?? 'gap',
    rule: textOrNull(raw.rule),
    title: textOrNull(raw.title) ?? `Fall ${id}`,
    impact: textOrNull(raw.impact),
    state: textOrNull(raw.state) ?? 'open',
    rank: numberOrNull(raw.rank),
    component_id: textOrNull(raw.component_id),
    product_id: textOrNull(raw.product_id),
    supplier_id: textOrNull(raw.supplier_id),
    po_number: textOrNull(raw.po_number),
    due_at: textOrNull(raw.due_at),
    act_by: textOrNull(raw.act_by),
    breaks_at: textOrNull(raw.breaks_at),
    owner_role: textOrNull(raw.owner_role),
    gap_qty: numberOrNull(raw.gap_qty),
    units_at_risk: numberOrNull(raw.units_at_risk),
    residual_qty: numberOrNull(raw.residual_qty),
    pending: {
      decisions: numberOrZero(pending.decisions),
      corrections: numberOrZero(pending.corrections),
      emails: numberOrZero(pending.emails),
    },
    updated_at: textOrNull(raw.updated_at),
  };
}

function product(value: unknown): Product[] {
  const raw = record(value);
  const productId = textOrNull(raw.product_id);
  if (productId === null) {
    return [];
  }
  const units = record(raw.units);
  return [
    {
      product_id: productId,
      description: textOrNull(raw.description),
      demand: numberOrNull(raw.demand),
      packed: numberOrNull(raw.packed),
      still_to_pack: numberOrNull(raw.still_to_pack),
      rate_per_hour: numberOrNull(raw.rate_per_hour),
      hours_left: numberOrNull(raw.hours_left),
      coverage_system: numberOrNull(raw.coverage_system),
      coverage_secured: numberOrNull(raw.coverage_secured),
      units: {
        secured: Math.max(numberOrZero(units.secured), 0),
        planned: Math.max(numberOrZero(units.planned), 0),
        open: Math.max(numberOrZero(units.open), 0),
        unclosable: Math.max(numberOrZero(units.unclosable), 0),
      },
      limiting_component: textOrNull(raw.limiting_component),
    },
  ];
}

function firstStop(value: unknown): FirstStop | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    component_id: textOrNull(value.component_id),
    description: textOrNull(value.description),
    breaks_at: textOrNull(value.breaks_at),
  };
}

function person(value: unknown): Person[] {
  const raw = record(value);
  const personId = textOrNull(raw.person_id);
  if (personId === null) {
    return [];
  }
  return [
    {
      person_id: personId,
      name: textOrNull(raw.name) ?? personId,
      roles: textList(raw.roles),
    },
  ];
}

function problem(value: unknown): Problem {
  const raw = record(value);
  return {
    event_id: numberOrNull(raw.event_id),
    type: textOrNull(raw.type),
    error: textOrNull(raw.error),
  };
}

/** Reads the answer of `GET /state`. */
function approvalMail(value: unknown): ApprovalMail | null {
  const raw = record(value);
  const id = numberOrNull(raw.id);
  if (id === null) {
    return null;
  }
  return {
    id,
    to_addr: textOrNull(raw.to_addr),
    subject: textOrNull(raw.subject),
    body: textOrNull(raw.body),
    language: textOrNull(raw.language),
  };
}

function approval(value: unknown): Approval[] {
  const raw = record(value);
  const id = textOrNull(raw.id);
  const objectId = numberOrNull(raw.object_id);
  if (id === null || objectId === null) {
    return [];
  }
  return [
    {
      id,
      type: textOrNull(raw.type) ?? 'decision',
      object_id: objectId,
      case_id: numberOrNull(raw.case_id),
      kind: textOrNull(raw.kind),
      title: textOrNull(raw.title) ?? 'Freigabe',
      summary: textOrNull(raw.summary),
      needs_roles: textList(raw.needs_roles),
      approver_name: textOrNull(raw.approver_name),
      deadline: textOrNull(raw.deadline),
      cost_eur: numberOrNull(raw.cost_eur),
      cost_unknown: flag(raw.cost_unknown),
      commits_money: flag(raw.commits_money),
      supplier_id: textOrNull(raw.supplier_id),
      arrives_at: textOrNull(raw.arrives_at),
      condition: textOrNull(raw.condition),
      conflict: textOrNull(raw.conflict),
      note: textOrNull(raw.note),
      after_deadline: flag(raw.after_deadline),
      email: approvalMail(raw.email),
      correction_payload: isRecord(raw.correction_payload) ? raw.correction_payload : null,
      erp_writer: textOrNull(raw.erp_writer),
    },
  ];
}

function approvalDone(value: unknown): ApprovalDone[] {
  const raw = record(value);
  const id = textOrNull(raw.id);
  if (id === null) {
    return [];
  }
  return [
    {
      id,
      type: textOrNull(raw.type) ?? 'decision',
      case_id: numberOrNull(raw.case_id),
      title: textOrNull(raw.title) ?? 'Freigabe',
      status: textOrNull(raw.status) ?? 'approved',
      decided_by: textOrNull(raw.decided_by),
      decided_at: textOrNull(raw.decided_at),
      mail_status: textOrNull(raw.mail_status),
      mail_to: textOrNull(raw.mail_to),
    },
  ];
}

export function normalizeState(value: unknown): LineguardState {
  const raw = record(value);
  const labels = record(raw.labels);
  const files = record(raw.import);
  const counters = record(raw.counters);
  const review = record(raw.booking_review);
  const casesNow = withId(raw.cases_now, caseSummary);
  const casesLater = withId(raw.cases_later, caseSummary);
  return {
    customer: textOrNull(raw.customer),
    labels: {
      deadline: textOrNull(labels.deadline) ?? 'Termin',
      product: textOrNull(labels.product) ?? 'Produkt',
      line: textOrNull(labels.line) ?? 'Linie',
      units: textOrNull(labels.units) ?? 'Einheiten',
    },
    at: textOrNull(raw.at),
    next_due: textOrNull(raw.next_due),
    timezone: textOrNull(raw.timezone) ?? 'Europe/Berlin',
    import: {
      files_total: numberOrZero(files.files_total),
      files_read: numberOrZero(files.files_read),
      failed: numberOrZero(files.failed),
      manual: numberOrZero(files.manual),
    },
    products: list(raw.products).flatMap(product),
    first_stop: firstStop(raw.first_stop),
    cases_now: casesNow,
    cases_later: casesLater,
    counters: {
      now_total: numberOrNull(counters.now_total) ?? casesNow.length,
      later_total: numberOrNull(counters.later_total) ?? casesLater.length,
      open_decisions: numberOrZero(counters.open_decisions),
      open_corrections: numberOrZero(counters.open_corrections),
      open_emails: numberOrZero(counters.open_emails),
    },
    booking_review: {
      receipts_checked: numberOrZero(review.receipts_checked),
      findings: numberOrZero(review.findings),
    },
    problems: list(raw.problems).map(problem),
    approvals: list(raw.approvals).flatMap(approval),
    approvals_done: list(raw.approvals_done).flatMap(approvalDone),
    people: list(raw.people).flatMap(person),
    mail_mode: textOrNull(raw.mail_mode) ?? 'DRY_RUN',
  };
}

function block(value: unknown): Block {
  const raw = record(value);
  return {
    reason: textOrNull(raw.reason),
    qty: numberOrNull(raw.qty),
    text: textOrNull(raw.text),
    fact_ids: numberList(raw.fact_ids),
  };
}

function shortLine(value: unknown): ShortLine {
  const raw = record(value);
  return {
    product_id: textOrNull(raw.product_id),
    demand_class: textOrNull(raw.class),
    due_at: textOrNull(raw.due_at),
    gap_qty: numberOrNull(raw.gap_qty),
    units_at_risk: numberOrNull(raw.units_at_risk),
  };
}

function caseDetail(value: unknown): CaseDetail {
  const raw = record(value);
  return {
    erp_stock: numberOrNull(raw.erp_stock),
    stock_as_of: textOrNull(raw.stock_as_of),
    used_since_snapshot: numberOrNull(raw.used_since_snapshot),
    usable: numberOrNull(raw.usable),
    need: numberOrNull(raw.need),
    inbound_secured: numberOrNull(raw.inbound_secured),
    gap_system: numberOrNull(raw.gap_system),
    latest_useful_arrival: textOrNull(raw.latest_useful_arrival),
    blocks: list(raw.blocks).map(block),
    short_lines: list(raw.short_lines).map(shortLine),
  };
}

function evidenceFile(value: unknown): EvidenceFile | null {
  const raw = record(value);
  const id = numberOrNull(raw.id);
  if (id === null) {
    return null;
  }
  return {
    id,
    path: textOrNull(raw.path),
    version: numberOrNull(raw.version),
  };
}

/** `data.printed_value` and `data.corrected` mark a handwritten correction. */
function noteMarks(value: unknown): {printed_value: number | null; corrected: boolean} {
  const data = record(value);
  return {
    printed_value: numberOrNull(data.printed_value),
    corrected: flag(data.corrected),
  };
}

function evidence(value: unknown): Evidence[] {
  const raw = record(value);
  const factId = numberOrNull(raw.fact_id);
  if (factId === null) {
    return [];
  }
  return [
    {
      fact_id: factId,
      fact_type: textOrNull(raw.fact_type),
      label: textOrNull(raw.label) ?? textOrNull(raw.fact_type) ?? 'Beleg',
      qty: numberOrNull(raw.qty),
      value_num: numberOrNull(raw.value_num),
      value_text: textOrNull(raw.value_text),
      rev: textOrNull(raw.rev),
      batch: textOrNull(raw.batch),
      ref: textOrNull(raw.ref),
      po_number: textOrNull(raw.po_number),
      eta: textOrNull(raw.eta),
      valid_until: textOrNull(raw.valid_until),
      doc_date: textOrNull(raw.doc_date),
      as_of: textOrNull(raw.as_of),
      source_rank: numberOrNull(raw.source_rank),
      confidence: numberOrNull(raw.confidence),
      extracted_by: textOrNull(raw.extracted_by),
      suspicious: flag(raw.suspicious),
      ...noteMarks(raw.data),
      file: evidenceFile(raw.file),
      locator: textOrNull(raw.locator),
    },
  ];
}

function checks(value: unknown): Check[] {
  return Object.entries(record(value)).map(([name, entry]) => {
    const raw = record(entry);
    const checkValue =
      typeof raw.value === 'number' ? raw.value : textOrNull(raw.value);
    return {
      name,
      status: textOrNull(raw.status),
      value: checkValue,
      fact_ids: numberList(raw.fact_ids),
    };
  });
}

function finding(value: unknown): Finding | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    gr_number: textOrNull(value.gr_number),
    booked_qty: numberOrNull(value.booked_qty),
    proposed_qty: numberOrNull(value.proposed_qty),
    delta_qty: numberOrNull(value.delta_qty),
    cause: textOrNull(value.cause),
    checks: checks(value.checks),
    agreeing_sources: numberOrNull(value.agreeing_sources),
    status: textOrNull(value.status),
  };
}

function correction(raw: Json, id: number): Correction {
  return {
    id,
    status: textOrNull(raw.status) ?? 'proposed',
    payload: record(raw.payload),
    writer: textOrNull(raw.writer),
    approver_role: textOrNull(raw.approver_role),
    approved_by: textOrNull(raw.approved_by),
    approved_at: textOrNull(raw.approved_at),
    reject_reason: textOrNull(raw.reject_reason),
    created_at: textOrNull(raw.created_at),
  };
}

/** `units_gained` is a number in `docs/api.md` and a map in the database. */
function unitsGained(value: unknown): Record<string, number> {
  const single = numberOrNull(value);
  if (single !== null) {
    return {'': single};
  }
  const gained: Record<string, number> = {};
  for (const [productId, units] of Object.entries(record(value))) {
    const parsed = numberOrNull(units);
    if (parsed !== null) {
      gained[productId] = parsed;
    }
  }
  return gained;
}

function option(raw: Json, id: number): Option {
  return {
    id,
    kind: textOrNull(raw.kind),
    title: textOrNull(raw.title) ?? `Option ${id}`,
    qty_gain: numberOrNull(raw.qty_gain),
    units_gained: unitsGained(raw.units_gained),
    arrives_at: textOrNull(raw.arrives_at),
    cost_eur: numberOrNull(raw.cost_eur),
    confidence: numberOrNull(raw.confidence),
    valid_until: textOrNull(raw.valid_until),
    feasible: raw.feasible === undefined ? true : flag(raw.feasible),
    infeasible_reason: textOrNull(raw.infeasible_reason),
    role_in_plan: textOrNull(raw.role_in_plan),
    status: textOrNull(raw.status),
    needs_roles: textList(raw.needs_roles),
    supplier_id: textOrNull(raw.supplier_id),
  };
}

function decision(raw: Json, id: number): Decision {
  return {
    id,
    kind: textOrNull(raw.kind),
    title: textOrNull(raw.title) ?? `Entscheidung ${id}`,
    explanation: textOrNull(raw.explanation),
    status: textOrNull(raw.status) ?? 'open',
    options: numberList(raw.options),
    recommended_option: numberOrNull(raw.recommended_option),
    needs_roles: textList(raw.needs_roles),
    approver_role: textOrNull(raw.approver_role),
    approver_name: textOrNull(raw.approver_name),
    policy_ref: textOrNull(raw.policy_ref),
    deadline: textOrNull(raw.deadline),
    decided_by: textOrNull(raw.decided_by),
    decided_at: textOrNull(raw.decided_at),
    reject_reason: textOrNull(raw.reject_reason),
  };
}

function email(raw: Json, id: number): Email {
  return {
    id,
    direction: textOrNull(raw.direction) ?? 'out',
    from_addr: textOrNull(raw.from_addr),
    to_addr: textOrNull(raw.to_addr),
    subject: textOrNull(raw.subject),
    body: textOrNull(raw.body),
    language: textOrNull(raw.language),
    status: textOrNull(raw.status) ?? 'draft',
    routine: flag(raw.routine),
    commits_money: flag(raw.commits_money),
    reason: textOrNull(raw.reason),
    approved_by: textOrNull(raw.approved_by),
    sent_at: textOrNull(raw.sent_at),
    created_at: textOrNull(raw.created_at),
  };
}

function action(raw: Json, id: number): Action {
  return {
    id,
    type: textOrNull(raw.type),
    kind: textOrNull(raw.kind),
    target: textOrNull(raw.target),
    status: textOrNull(raw.status),
    due_at: textOrNull(raw.due_at),
    created_at: textOrNull(raw.created_at),
  };
}

/** Reads the answer of `GET /cases/{id}`. Returns `null` without a case. */
export function normalizeCase(value: unknown): CaseView | null {
  const raw = record(value);
  const rawCase = record(raw.case);
  const id = numberOrNull(rawCase.id);
  if (id === null) {
    return null;
  }
  return {
    case: caseSummary(rawCase, id),
    detail: caseDetail(rawCase.detail),
    evidence: list(raw.evidence).flatMap(evidence),
    finding: finding(raw.finding),
    corrections: withId(raw.corrections, correction),
    options: withId(raw.options, option),
    decisions: withId(raw.decisions, decision),
    emails: withId(raw.emails, email),
    actions: withId(raw.actions, action),
  };
}

/** Reads the answer of `GET /events`. Accepts a list or `{events: [...]}`. */
export function normalizeEvents(value: unknown): LogEvent[] {
  const entries = Array.isArray(value) ? value : record(value).events;
  return withId(entries, (raw, id) => ({
    id,
    type: textOrNull(raw.type),
    status: textOrNull(raw.status),
    created_at: textOrNull(raw.created_at),
    handled_by: textOrNull(raw.handled_by),
    payload: raw.payload ?? null,
  }));
}

/** Reads the answer of `POST /sync`. */
export function normalizeSync(value: unknown): SyncResult {
  return {changes: list(record(value).changes)};
}

/** Reads `detail` from an error answer of FastAPI. */
export function errorDetail(value: unknown): string | null {
  const detail = record(value).detail;
  if (typeof detail === 'string') {
    return detail;
  }
  // FastAPI sends a list of problems when the body of a request is wrong.
  const messages = list(detail).flatMap((item) => {
    const message = textOrNull(record(item).msg);
    return message === null ? [] : [message];
  });
  return messages.length > 0 ? messages.join(' ') : null;
}
