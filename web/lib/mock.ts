/**
 * The mock backend. It keeps the demo data in memory and changes it on each
 * write, with the same role rules and HTTP statuses as the real API.
 */

import {formatCount} from './format';
import {createDemo} from '../mock/demo';
import type {DemoData} from '../mock/demo';

import {ApiError} from './errors';
import type {
  CaseView,
  Correction,
  Decision,
  Email,
  EmailEdit,
  Approval,
  LineguardState,
  LogEvent,
  Person,
  SyncResult,
} from './types';

let data: DemoData | null = null;

function demo(): DemoData {
  data ??= createDemo();
  return data;
}

function stamp(): string {
  return demo().state.at ?? new Date().toISOString();
}

function log(type: string, payload: Record<string, unknown>): void {
  const events = demo().events;
  const id = Math.max(0, ...events.map((event) => event.id)) + 1;
  events.unshift({
    id,
    type,
    status: 'done',
    created_at: stamp(),
    handled_by: null,
    payload,
  });
}

function person(personId: string | null, roles: string[]): Person {
  const found = demo().state.people.find(
    (candidate) => candidate.person_id === personId,
  );
  if (found === undefined) {
    throw new ApiError(401, null);
  }
  const role = roles[0];
  if (role !== undefined && !roles.some((name) => found.roles.includes(name))) {
    throw new ApiError(403, `This approval needs the role ${role}`);
  }
  return found;
}

interface Found<T> {
  view: CaseView;
  item: T;
}

function find<T extends {id: number}>(
  id: number,
  pick: (view: CaseView) => T[],
): Found<T> {
  for (const view of demo().cases.values()) {
    const item = pick(view).find((candidate) => candidate.id === id);
    if (item !== undefined) {
      return {view, item};
    }
  }
  throw new ApiError(404, null);
}

function requireStatus(item: {status: string}, status: string): void {
  if (item.status !== status) {
    throw new ApiError(409, null);
  }
}

/** Writes the counters of a case and of the state after a change. */
function recount(view: CaseView): void {
  const {state, cases} = demo();
  view.case.pending = {
    decisions: view.decisions.filter((entry) => entry.status === 'open').length,
    corrections: view.corrections.filter((entry) => entry.status === 'proposed')
      .length,
    emails: view.emails.filter((entry) => entry.status === 'draft').length,
  };
  const replace = (list: LineguardState['cases_now']) =>
    list.map((entry) => (entry.id === view.case.id ? view.case : entry));
  state.cases_now = replace(state.cases_now);
  state.cases_later = replace(state.cases_later);
  const all = [...cases.values()].map((entry) => entry.case.pending);
  const sum = (key: keyof CaseView['case']['pending']) =>
    all.reduce((total, pending) => total + pending[key], 0);
  state.counters = {
    ...state.counters,
    open_decisions: sum('decisions'),
    open_corrections: sum('corrections'),
    open_emails: sum('emails'),
  };
}

function decisionRoles(decision: Decision): string[] {
  if (decision.needs_roles.length > 0) {
    return decision.needs_roles;
  }
  return decision.approver_role === null ? [] : [decision.approver_role];
}

/** The demo has no server, so the waiting approvals come from its cases. */
function waitingApprovals(): Approval[] {
  const found: Approval[] = [];
  const empty = {
    cost_unknown: false,
    supplier_id: null,
    arrives_at: null,
    condition: null,
    conflict: null,
    note: null,
    after_deadline: false,
    correction_payload: null,
    erp_writer: null,
  };
  for (const view of demo().cases.values()) {
    for (const decision of view.decisions) {
      if (decision.status !== 'open') {
        continue;
      }
      const option = view.options.find(
        (entry) => entry.id === decision.recommended_option,
      );
      const draft = view.emails.find((entry) => entry.status === 'draft');
      found.push({
        ...empty,
        id: `decision:${decision.id}`,
        type: 'decision',
        object_id: decision.id,
        case_id: view.case.id,
        kind: decision.kind ?? option?.kind ?? null,
        title: option?.title ?? decision.title,
        summary: decision.explanation,
        needs_roles: decisionRoles(decision),
        approver_name: decision.approver_name,
        deadline: decision.deadline,
        cost_eur: option?.cost_eur ?? null,
        commits_money: (option?.cost_eur ?? 0) > 0,
        supplier_id: option?.supplier_id ?? null,
        arrives_at: option?.arrives_at ?? null,
        email: draft === undefined ? null : draft,
      });
    }
    for (const correction of view.corrections) {
      const id = `correction:${correction.id}`;
      // Two demo cases show the same correction. It waits one time.
      if (correction.status !== 'proposed' || found.some((entry) => entry.id === id)) {
        continue;
      }
      const booked = correction.payload.booked_qty;
      const documented = correction.payload.proposed_qty;
      found.push({
        ...empty,
        id,
        type: 'correction',
        object_id: correction.id,
        case_id: view.case.id,
        kind: 'erp_correction',
        title: `Correct goods receipt ${view.finding?.gr_number ?? ''}`,
        summary:
          typeof booked === 'number' && typeof documented === 'number'
            ? `The ERP booked ${formatCount(booked)} pieces ${view.case.component_id ?? ''}. The documents show ${formatCount(documented)}.`
            : view.case.title,
        needs_roles: correction.approver_role === null ? [] : [correction.approver_role],
        approver_name: null,
        deadline: null,
        cost_eur: 0,
        commits_money: false,
        email: null,
        correction_payload: correction.payload,
        erp_writer: 'browser_demo',
      });
    }
  }
  return found;
}

export function getState(): LineguardState {
  return structuredClone({...demo().state, approvals: waitingApprovals()});
}

export function getCase(id: number): CaseView | null {
  const view = demo().cases.get(id);
  return view === undefined ? null : structuredClone(view);
}

export function getEvents(limit: number): LogEvent[] {
  return structuredClone(demo().events.slice(0, limit));
}

export function sync(personId: string | null): SyncResult {
  person(personId, []);
  log('sync.requested', {});
  return {changes: []};
}

export function approveDecision(
  id: number,
  optionId: number | null,
  personId: string | null,
): void {
  const {view, item} = find<Decision>(id, (entry) => entry.decisions);
  const actor = person(personId, decisionRoles(item));
  requireStatus(item, 'open');
  if (item.kind === 'unclosable_gap') {
    item.status = 'approved';
    item.decided_by = actor.person_id;
    item.decided_at = stamp();
    recount(view);
    log('decision.approved', {decision_id: id});
    return;
  }
  const chosenId = optionId ?? item.recommended_option;
  const chosen = view.options.find((entry) => entry.id === chosenId);
  if (chosen === undefined || !chosen.feasible) {
    throw new ApiError(422, 'This option is not possible');
  }
  chosen.status = 'approved';
  item.status = 'approved';
  item.decided_by = actor.person_id;
  item.decided_at = stamp();
  view.case.state = 'approved';
  const product = demo().state.products.find(
    (entry) => entry.product_id === view.case.product_id,
  );
  if (product !== undefined) {
    const moved = Math.min(product.units.open, view.case.units_at_risk ?? 0);
    product.units.open -= moved;
    product.units.planned += moved;
  }
  recount(view);
  log('decision.approved', {decision_id: id, option_id: chosen.id});
}

export function rejectDecision(
  id: number,
  reason: string,
  personId: string | null,
): void {
  const {view, item} = find<Decision>(id, (entry) => entry.decisions);
  const actor = person(personId, decisionRoles(item));
  requireStatus(item, 'open');
  if (reason.trim() === '') {
    throw new ApiError(422, 'The reason is required');
  }
  item.status = 'rejected';
  item.reject_reason = reason.trim();
  item.decided_by = actor.person_id;
  item.decided_at = stamp();
  view.case.state = 'open';
  recount(view);
  log('decision.rejected', {decision_id: id});
}

function mailRoles(view: CaseView): string[] {
  return [...new Set(view.decisions.flatMap(decisionRoles))];
}

export function approveEmail(
  id: number,
  edit: EmailEdit,
  personId: string | null,
): void {
  const {view, item} = find<Email>(id, (entry) => entry.emails);
  const actor = person(personId, mailRoles(view));
  requireStatus(item, 'draft');
  item.subject = edit.subject ?? item.subject;
  item.body = edit.body ?? item.body;
  item.status = demo().state.mail_mode === 'LIVE' ? 'sent' : 'dry_run';
  item.approved_by = actor.person_id;
  item.sent_at = stamp();
  recount(view);
  log('email.sent', {email_id: id});
}

export function discardEmail(id: number, personId: string | null): void {
  const {view, item} = find<Email>(id, (entry) => entry.emails);
  person(personId, mailRoles(view));
  requireStatus(item, 'draft');
  item.status = 'discarded';
  recount(view);
  log('email.discarded', {email_id: id});
}

export function approveCorrection(id: number, personId: string | null): void {
  const {view, item} = find<Correction>(id, (entry) => entry.corrections);
  const actor = person(personId, ['erp_owner']);
  requireStatus(item, 'proposed');
  item.status = 'handed_over';
  item.approved_by = actor.person_id;
  item.approved_at = stamp();
  view.case.state = 'approved';
  recount(view);
  log('correction.approved', {correction_id: id});
}

export function rejectCorrection(
  id: number,
  reason: string,
  personId: string | null,
): void {
  const {view, item} = find<Correction>(id, (entry) => entry.corrections);
  person(personId, ['erp_owner']);
  requireStatus(item, 'proposed');
  if (reason.trim() === '') {
    throw new ApiError(422, 'The reason is required');
  }
  item.status = 'rejected';
  item.reject_reason = reason.trim();
  recount(view);
  log('correction.rejected', {correction_id: id});
}

export function requestCount(id: number, personId: string | null): void {
  const {view, item} = find<Correction>(id, (entry) => entry.corrections);
  person(personId, ['erp_owner', 'site_lead']);
  requireStatus(item, 'proposed');
  if (view.finding !== null) {
    view.finding.status = 'needs_count';
  }
  const actionId = Math.max(0, ...view.actions.map((entry) => entry.id)) + 1;
  view.actions.push({
    id: actionId,
    type: 'count_request',
    kind: 'count_request',
    target: view.case.component_id,
    status: 'sent',
    due_at: null,
    created_at: stamp(),
  });
  log('count.requested', {correction_id: id});
}
