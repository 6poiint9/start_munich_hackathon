/**
 * English words for the codes of the API.
 *
 * A code that this file does not know is shown as it is, with spaces for
 * underscores. A new code of the backend is therefore never hidden.
 */

/** The meaning that a color and a glyph repeat next to a word. */
export type Tone = 'neutral' | 'go' | 'work' | 'wait' | 'stop';

function readable(code: string): string {
  return code.replaceAll('_', ' ').replaceAll('.', ': ');
}

function lookup(words: ReadonlyMap<string, string>, code: string | null): string {
  if (code === null) {
    return '–';
  }
  return words.get(code) ?? readable(code);
}

const CASE_KINDS = new Map([
  ['gap', 'Shortage'],
  ['booking_finding', 'Booking error'],
  ['watch', 'Early warning'],
]);

export function caseKindWord(kind: string | null): string {
  return lookup(CASE_KINDS, kind);
}

const CASE_STATES = new Map([
  ['open', 'Open'],
  ['plan_proposed', 'Plan ready'],
  ['approved', 'Approved'],
  ['in_execution', 'In progress'],
  ['confirmed', 'Confirmed'],
  ['closed', 'Closed'],
  ['unclosable', 'Cannot be closed'],
  ['dismissed', 'Dismissed'],
]);

const CASE_STATE_TONES = new Map<string, Tone>([
  ['open', 'wait'],
  ['plan_proposed', 'wait'],
  ['approved', 'work'],
  ['in_execution', 'work'],
  ['confirmed', 'go'],
  ['closed', 'go'],
  ['unclosable', 'stop'],
  ['dismissed', 'neutral'],
]);

export function caseStateWord(state: string | null): string {
  return lookup(CASE_STATES, state);
}

export function caseStateTone(state: string | null): Tone {
  return CASE_STATE_TONES.get(state ?? '') ?? 'neutral';
}

const RULES = new Map([
  ['thin_and_stale', 'Small reserve and old stock count'],
]);

export function ruleWord(rule: string | null): string {
  return lookup(RULES, rule);
}

const CAUSES = new Map([
  ['decimal_shift', 'one zero too many or too few'],
  ['unit_mismatch', 'wrong unit'],
  ['duplicate_booking', 'booked twice'],
  ['unreferenced_receipt', 'goods receipt without a purchase order'],
  ['content_mismatch', 'content differs from the booked part'],
  ['quantity_mismatch', 'quantity differs'],
]);

export function causeWord(cause: string | null): string {
  return lookup(CAUSES, cause);
}

const CHECK_NAMES = new Map([
  ['gr_vs_po', 'Ordered quantity'],
  ['gr_vs_delivery_note', 'Quantity on the delivery note'],
  ['gr_vs_weight', 'Quantity from the weight'],
  ['gr_vs_packages', 'Quantity from the packages'],
  ['gr_vs_history', 'Earlier goods receipts'],
  ['duplicate', 'Double booking'],
  ['unreferenced', 'Link to a purchase order'],
  ['gr_note_exception', 'Note on the booking'],
]);

export function checkNameWord(name: string): string {
  return lookup(CHECK_NAMES, name);
}

const CHECK_STATUSES = new Map([
  ['pass', 'matches'],
  ['fail', 'differs'],
  ['no_data', 'no data'],
]);

const CHECK_STATUS_TONES = new Map<string, Tone>([
  ['pass', 'go'],
  ['fail', 'stop'],
  ['no_data', 'neutral'],
]);

export function checkStatusWord(status: string | null): string {
  return lookup(CHECK_STATUSES, status);
}

export function checkStatusTone(status: string | null): Tone {
  return CHECK_STATUS_TONES.get(status ?? '') ?? 'neutral';
}

const FINDING_STATUSES = new Map([
  ['proposed', 'Correction proposed'],
  ['needs_count', 'Stock count needed'],
  ['dismissed', 'Dismissed'],
  ['corrected', 'Corrected'],
]);

export function findingStatusWord(status: string | null): string {
  return lookup(FINDING_STATUSES, status);
}

const CORRECTION_STATUSES = new Map([
  ['proposed', 'Waiting for approval'],
  ['approved', 'Approved'],
  ['rejected', 'Rejected'],
  ['handed_over', 'Handed to the ERP owner'],
  ['posted', 'Booked in the ERP'],
  ['verified', 'Confirmed in the ERP'],
  ['failed', 'Failed'],
]);

const CORRECTION_STATUS_TONES = new Map<string, Tone>([
  ['proposed', 'wait'],
  ['approved', 'work'],
  ['rejected', 'neutral'],
  ['handed_over', 'work'],
  ['posted', 'work'],
  ['verified', 'go'],
  ['failed', 'stop'],
]);

export function correctionStatusWord(status: string | null): string {
  return lookup(CORRECTION_STATUSES, status);
}

export function correctionStatusTone(status: string | null): Tone {
  return CORRECTION_STATUS_TONES.get(status ?? '') ?? 'neutral';
}

const DECISION_STATUSES = new Map([
  ['open', 'Open'],
  ['approved', 'Approved'],
  ['rejected', 'Rejected'],
  ['expired', 'Expired'],
]);

const DECISION_STATUS_TONES = new Map<string, Tone>([
  ['open', 'wait'],
  ['approved', 'go'],
  ['rejected', 'neutral'],
  ['expired', 'stop'],
]);

export function decisionStatusWord(status: string | null): string {
  return lookup(DECISION_STATUSES, status);
}

export function decisionStatusTone(status: string | null): Tone {
  return DECISION_STATUS_TONES.get(status ?? '') ?? 'neutral';
}

const OPTION_KINDS = new Map([
  ['release_held', 'Collect held shipment'],
  ['accept_offer', 'Accept offer'],
  ['expedite_inbound', 'Speed up delivery'],
  ['rework_sort', 'Sort blocked batch'],
  ['reallocate', 'Reallocate stock'],
  ['count_request', 'Stock count'],
  ['confirm_terms', 'Confirm supplier condition'],
  ['erp_correction', 'ERP correction'],
  ['alt_source', 'Other supplier'],
  ['add_capacity', 'More capacity'],
  ['deliver_after_deadline', 'Deliver after the deadline'],
  ['unclosable_gap', 'Shortage alert'],
]);

export function optionKindWord(kind: string | null): string {
  return lookup(OPTION_KINDS, kind);
}

const PLAN_ROLES = new Map([
  ['primary', 'Recommended'],
  ['backup', 'Backup'],
]);

/** The part an option plays in the plan. `null` when it plays none. */
export function planRoleWord(role: string | null): string | null {
  return PLAN_ROLES.get(role ?? '') ?? null;
}

const EMAIL_STATUSES = new Map([
  ['draft', 'Draft'],
  ['approved', 'Approved, sending'],
  ['sent', 'Sent'],
  ['dry_run', 'Logged, not sent'],
  ['received', 'Reply'],
  ['failed', 'Sending failed'],
  ['discarded', 'Discarded'],
]);

const EMAIL_STATUS_TONES = new Map<string, Tone>([
  ['draft', 'wait'],
  ['approved', 'work'],
  ['sent', 'go'],
  ['dry_run', 'neutral'],
  ['received', 'neutral'],
  ['failed', 'stop'],
  ['discarded', 'neutral'],
]);

export function emailStatusWord(status: string | null): string {
  return lookup(EMAIL_STATUSES, status);
}

export function emailStatusTone(status: string | null): Tone {
  return EMAIL_STATUS_TONES.get(status ?? '') ?? 'neutral';
}

const MAIL_MODES = new Map([
  ['DRY_RUN', 'Mail: log only'],
  ['LIVE', 'Mail: sending'],
  ['REPLAY', 'Mail: replay'],
]);

export function mailModeWord(mode: string | null): string {
  return lookup(MAIL_MODES, mode);
}

const ROLES = new Map([
  ['buyer', 'Purchasing'],
  ['category_lead', 'Category lead'],
  ['erp_owner', 'ERP owner'],
  ['site_lead', 'Site lead'],
  ['procurement_head', 'Head of purchasing'],
  ['head_of_procurement', 'Head of purchasing'],
  ['cpo', 'Chief procurement officer'],
  ['cfo', 'Chief financial officer'],
  ['quality_compliance', 'Quality and compliance'],
  ['supplier_quality_lead', 'Supplier quality lead'],
]);

export function roleWord(role: string | null): string {
  return lookup(ROLES, role);
}

const SOURCE_RANKS = new Map([
  [1, 'Signed document'],
  [2, 'Document'],
  [3, 'ERP movement'],
  [4, 'ERP stock'],
  [5, 'List'],
]);

export function sourceRankWord(rank: number | null): string {
  if (rank === null) {
    return 'Source unknown';
  }
  return SOURCE_RANKS.get(rank) ?? `Rank ${rank}`;
}

const READERS = new Map([
  ['parser', 'Parser'],
  ['llm', 'Language model'],
  ['ocr', 'Text recognition'],
  ['vision', 'Image recognition'],
  ['human', 'Person'],
]);

export function readerWord(reader: string | null): string {
  return lookup(READERS, reader);
}

const BLOCK_REASONS = new Map([
  ['booking_finding', 'Booking error'],
  ['quality_hold', 'Quality hold'],
  ['inspection_failed', 'Inspection failed'],
  ['wrong_revision', 'Wrong revision'],
  ['expired', 'Expired'],
  ['not_released', 'Not released'],
]);

export function blockReasonWord(reason: string | null): string {
  return lookup(BLOCK_REASONS, reason);
}

const DEMAND_CLASSES = new Map([
  ['preorder', 'Pre-order'],
  ['open_sale', 'Open sale'],
]);

export function demandClassWord(demandClass: string | null): string {
  return lookup(DEMAND_CLASSES, demandClass);
}

const ACTION_TYPES = new Map([
  ['count_request', 'Stock count'],
  ['email', 'Mail'],
  ['pickup_request', 'Pickup'],
  ['purchase_order', 'Purchase order'],
  ['erp_correction', 'ERP correction'],
]);

export function actionTypeWord(type: string | null): string {
  return lookup(ACTION_TYPES, type);
}

const ACTION_STATUSES = new Map([
  ['awaiting_approval', 'Waiting for approval'],
  ['proposed', 'Proposed'],
  ['approved', 'Approved'],
  ['sent', 'Sent'],
  ['done', 'Done'],
  ['failed', 'Failed'],
]);

export function actionStatusWord(status: string | null): string {
  return lookup(ACTION_STATUSES, status);
}

const EVENT_TYPES = new Map([
  ['file.added', 'File added'],
  ['file.changed', 'File changed'],
  ['file.removed', 'File removed'],
  ['facts.updated', 'Facts read'],
  ['finding.created', 'Booking error found'],
  ['correction.proposed', 'Correction proposed'],
  ['correction.approved', 'Correction approved'],
  ['correction.rejected', 'Correction rejected'],
  ['correction.verified', 'Correction confirmed in the ERP'],
  ['count.requested', 'Stock count requested'],
  ['gap.changed', 'Shortage recalculated'],
  ['gap.unclosable', 'Shortage cannot be closed'],
  ['gap.closed', 'Shortage closed'],
  ['option.created', 'Option found'],
  ['option.changed', 'Option changed'],
  ['decision.created', 'Decision prepared'],
  ['decision.approved', 'Decision approved'],
  ['decision.rejected', 'Decision rejected'],
  ['decision.escalated', 'Decision escalated'],
  ['email.drafted', 'Mail drafted'],
  ['email.sent', 'Mail sent'],
  ['email.discarded', 'Mail discarded'],
  ['email.received', 'Mail received'],
  ['sync.requested', 'Source check'],
  ['tick', 'Timer'],
]);

export function eventTypeWord(type: string | null): string {
  return lookup(EVENT_TYPES, type);
}

const EVENT_STATUSES = new Map([
  ['pending', 'Waiting'],
  ['processing', 'Running'],
  ['done', 'Done'],
  ['failed', 'Failed'],
]);

const EVENT_STATUS_TONES = new Map<string, Tone>([
  ['pending', 'wait'],
  ['processing', 'work'],
  ['done', 'neutral'],
  ['failed', 'stop'],
]);

export function eventStatusWord(status: string | null): string {
  return lookup(EVENT_STATUSES, status);
}

export function eventStatusTone(status: string | null): Tone {
  return EVENT_STATUS_TONES.get(status ?? '') ?? 'neutral';
}

let languageNames: Intl.DisplayNames | null = null;

/** `de` becomes `German`. */
export function languageWord(code: string | null): string {
  if (code === null) {
    return 'language unknown';
  }
  try {
    languageNames ??= new Intl.DisplayNames('en', {type: 'language'});
    return languageNames.of(code) ?? code;
  } catch {
    return code;
  }
}

/** How sure an option is, in words. The limits follow docs/lueckenschluss.md. */
export function confidenceWord(confidence: number | null): string {
  if (confidence === null) {
    return 'unknown';
  }
  if (confidence >= 0.85) {
    return 'with a document';
  }
  if (confidence >= 0.5) {
    return 'statement without a document';
  }
  return 'no answer yet';
}

const IMPACTS = new Map([
  ['deadline_blocker', 'blocks the deadline'],
]);

/** What a case does to the plan. `null` when the backend names no impact. */
export function impactWord(impact: string | null): string | null {
  return impact === null ? null : lookup(IMPACTS, impact);
}

/** A locator of the backend, for example `row 3, column qty`. It is English already. */
export function locatorWord(locator: string | null): string | null {
  return locator;
}
