/**
 * Shapes of the Lineguard API after `lib/normalize.ts` cleaned them.
 *
 * The field names are the names of `docs/api.md`. Lists are always arrays and
 * nested objects always exist. A leaf that the backend did not send is `null`.
 */

export interface Labels {
  deadline: string;
  product: string;
  line: string;
  units: string;
}

export interface UnitsByState {
  secured: number;
  planned: number;
  open: number;
  unclosable: number;
}

export interface Product {
  product_id: string;
  description: string | null;
  demand: number | null;
  packed: number | null;
  still_to_pack: number | null;
  rate_per_hour: number | null;
  hours_left: number | null;
  coverage_system: number | null;
  coverage_secured: number | null;
  units: UnitsByState;
  limiting_component: string | null;
}

export interface FirstStop {
  component_id: string | null;
  description: string | null;
  breaks_at: string | null;
}

export interface Pending {
  decisions: number;
  corrections: number;
  emails: number;
}

export type CaseKind = 'gap' | 'booking_finding' | 'watch';

export interface CaseSummary {
  id: number;
  /** One of `CaseKind`, or a kind that a newer backend added. */
  kind: string;
  rule: string | null;
  title: string;
  impact: string | null;
  state: string;
  rank: number | null;
  component_id: string | null;
  product_id: string | null;
  supplier_id: string | null;
  po_number: string | null;
  due_at: string | null;
  act_by: string | null;
  breaks_at: string | null;
  owner_role: string | null;
  gap_qty: number | null;
  units_at_risk: number | null;
  residual_qty: number | null;
  pending: Pending;
  updated_at: string | null;
}

export interface Counters {
  now_total: number;
  later_total: number;
  open_decisions: number;
  open_corrections: number;
  open_emails: number;
}

export interface ImportStatus {
  files_total: number;
  files_read: number;
  failed: number;
  manual: number;
}

export interface BookingReview {
  receipts_checked: number;
  findings: number;
}

export interface Problem {
  event_id: number | null;
  type: string | null;
  error: string | null;
}

export interface Person {
  person_id: string;
  name: string;
  roles: string[];
}

/** The draft that goes out when the person approves. */
export interface ApprovalMail {
  id: number;
  to_addr: string | null;
  subject: string | null;
  body: string | null;
  language: string | null;
  commits_money: boolean;
}

/**
 * One item waiting for a click. `id` is `decision:<id>` or `correction:<id>`.
 * The list on the state is already sorted, most urgent first.
 */
export interface Approval {
  id: string;
  type: string;
  object_id: number | null;
  case_id: number | null;
  kind: string | null;
  title: string;
  summary: string | null;
  needs_roles: string[];
  approver_name: string | null;
  deadline: string | null;
  cost_eur: number | null;
  cost_unknown: boolean;
  commits_money: boolean;
  supplier_id: string | null;
  arrives_at: string | null;
  condition: string | null;
  conflict: string | null;
  note: string | null;
  after_deadline: boolean;
  email: ApprovalMail | null;
  created_at: string | null;
}

/** One of the last approvals or rejections. Newest first. */
export interface ApprovalDone {
  id: string;
  type: string;
  case_id: number | null;
  title: string;
  status: string | null;
  decided_by: string | null;
  decided_at: string | null;
  mail_status: string | null;
  mail_to: string | null;
}

export interface LineguardState {
  customer: string | null;
  labels: Labels;
  at: string | null;
  next_due: string | null;
  timezone: string;
  import: ImportStatus;
  products: Product[];
  first_stop: FirstStop | null;
  cases_now: CaseSummary[];
  cases_later: CaseSummary[];
  counters: Counters;
  booking_review: BookingReview;
  problems: Problem[];
  people: Person[];
  mail_mode: string;
  /** Empty when the backend does not send the inbox yet. */
  approvals: Approval[];
  approvals_done: ApprovalDone[];
}

export interface Block {
  reason: string | null;
  qty: number | null;
  text: string | null;
  fact_ids: number[];
}

export interface ShortLine {
  product_id: string | null;
  demand_class: string | null;
  due_at: string | null;
  gap_qty: number | null;
  units_at_risk: number | null;
}

export interface CaseDetail {
  erp_stock: number | null;
  stock_as_of: string | null;
  used_since_snapshot: number | null;
  usable: number | null;
  need: number | null;
  inbound_secured: number | null;
  gap_system: number | null;
  latest_useful_arrival: string | null;
  blocks: Block[];
  short_lines: ShortLine[];
}

export interface EvidenceFile {
  id: number;
  path: string | null;
  version: number | null;
}

export interface Evidence {
  fact_id: number;
  fact_type: string | null;
  label: string;
  qty: number | null;
  value_num: number | null;
  value_text: string | null;
  rev: string | null;
  batch: string | null;
  ref: string | null;
  po_number: string | null;
  eta: string | null;
  valid_until: string | null;
  doc_date: string | null;
  as_of: string | null;
  source_rank: number | null;
  confidence: number | null;
  extracted_by: string | null;
  suspicious: boolean;
  /**
   * The printed number a handwritten correction replaced.
   * It comes from `data.printed_value` on the fact.
   */
  printed_value: number | null;
  /** True when the reader set `data.corrected` on the fact. */
  corrected: boolean;
  file: EvidenceFile | null;
  locator: string | null;
}

export interface Check {
  name: string;
  status: string | null;
  value: number | string | null;
  fact_ids: number[];
}

export interface Finding {
  gr_number: string | null;
  booked_qty: number | null;
  proposed_qty: number | null;
  delta_qty: number | null;
  cause: string | null;
  checks: Check[];
  agreeing_sources: number | null;
  status: string | null;
}

export interface Correction {
  id: number;
  status: string;
  payload: Record<string, unknown>;
  approver_role: string | null;
  approved_by: string | null;
  approved_at: string | null;
  reject_reason: string | null;
  created_at: string | null;
}

export interface Option {
  id: number;
  kind: string | null;
  title: string;
  qty_gain: number | null;
  /** Units gained per `product_id`. A plain number arrives under the key `''`. */
  units_gained: Record<string, number>;
  arrives_at: string | null;
  cost_eur: number | null;
  confidence: number | null;
  valid_until: string | null;
  feasible: boolean;
  infeasible_reason: string | null;
  role_in_plan: string | null;
  status: string | null;
  needs_roles: string[];
  supplier_id: string | null;
}

export interface Decision {
  id: number;
  title: string;
  explanation: string | null;
  status: string;
  options: number[];
  recommended_option: number | null;
  needs_roles: string[];
  approver_role: string | null;
  approver_name: string | null;
  policy_ref: string | null;
  deadline: string | null;
  decided_by: string | null;
  decided_at: string | null;
  reject_reason: string | null;
}

export interface Email {
  id: number;
  direction: string;
  from_addr: string | null;
  to_addr: string | null;
  subject: string | null;
  body: string | null;
  language: string | null;
  status: string;
  routine: boolean;
  commits_money: boolean;
  reason: string | null;
  approved_by: string | null;
  sent_at: string | null;
  created_at: string | null;
}

export interface Action {
  id: number;
  type: string | null;
  kind: string | null;
  target: string | null;
  status: string | null;
  due_at: string | null;
  created_at: string | null;
}

export interface CaseView {
  case: CaseSummary;
  detail: CaseDetail;
  evidence: Evidence[];
  finding: Finding | null;
  corrections: Correction[];
  options: Option[];
  decisions: Decision[];
  emails: Email[];
  actions: Action[];
}

export interface LogEvent {
  id: number;
  type: string | null;
  status: string | null;
  created_at: string | null;
  handled_by: string | null;
  payload: unknown;
}

export interface SyncResult {
  changes: unknown[];
}

/** Text that a person can edit in a mail draft before the approval. */
export interface EmailEdit {
  subject?: string;
  body?: string;
}
