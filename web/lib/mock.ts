/**
 * The mock backend. It keeps the demo data in memory and changes it on each
 * write, with the same role rules and HTTP statuses as the real API.
 */

import {createDemo} from '../mock/demo';
import type {DemoData} from '../mock/demo';

import {ApiError} from './errors';
import type {
  ApprovalMail,
  CaseView,
  Correction,
  Decision,
  Email,
  EmailEdit,
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
    throw new ApiError(403, `Diese Freigabe braucht die Rolle ${role}`);
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

/** Moves a clicked inbox item into the short history. */
function finishApproval(
  type: string,
  objectId: number,
  status: string,
  actor: Person,
  mail: ApprovalMail | null,
): void {
  const state = demo().state;
  const index = state.approvals.findIndex(
    (item) => item.type === type && item.object_id === objectId,
  );
  if (index < 0) {
    return;
  }
  const item = state.approvals[index];
  if (item === undefined) {
    return;
  }
  state.approvals.splice(index, 1);
  const sent = mail === null ? null : state.mail_mode === 'LIVE' ? 'sent' : 'dry_run';
  state.approvals_done.unshift({
    id: item.id,
    type: item.type,
    case_id: item.case_id,
    title: item.title,
    status,
    decided_by: actor.name,
    decided_at: stamp(),
    mail_status: sent,
    mail_to: mail?.to_addr ?? null,
  });
  state.approvals_done = state.approvals_done.slice(0, 5);
}

function decisionRoles(decision: Decision): string[] {
  if (decision.needs_roles.length > 0) {
    return decision.needs_roles;
  }
  return decision.approver_role === null ? [] : [decision.approver_role];
}

export function getState(): LineguardState {
  return structuredClone(demo().state);
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
  const draft = demo().state.approvals.find(
    (entry) => entry.type === 'decision' && entry.object_id === id,
  )?.email ?? null;
  const chosenId = optionId ?? item.recommended_option;
  const chosen = view.options.find((entry) => entry.id === chosenId);
  if (chosen === undefined || !chosen.feasible) {
    throw new ApiError(422, 'Diese Option ist nicht machbar');
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
  if (draft !== null) {
    const email = view.emails.find((entry) => entry.id === draft.id);
    if (email !== undefined && email.status === 'draft') {
      email.status = demo().state.mail_mode === 'LIVE' ? 'sent' : 'dry_run';
      email.approved_by = actor.person_id;
      email.sent_at = stamp();
    }
  }
  recount(view);
  finishApproval('decision', id, 'approved', actor, draft);
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
    throw new ApiError(422, 'Der Grund ist Pflicht');
  }
  item.status = 'rejected';
  item.reject_reason = reason.trim();
  item.decided_by = actor.person_id;
  item.decided_at = stamp();
  view.case.state = 'open';
  recount(view);
  finishApproval('decision', id, 'rejected', actor, null);
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
  finishApproval('correction', id, item.status, actor, null);
  log('correction.approved', {correction_id: id});
}

export function rejectCorrection(
  id: number,
  reason: string,
  personId: string | null,
): void {
  const {view, item} = find<Correction>(id, (entry) => entry.corrections);
  const actor = person(personId, ['erp_owner']);
  requireStatus(item, 'proposed');
  if (reason.trim() === '') {
    throw new ApiError(422, 'Der Grund ist Pflicht');
  }
  item.status = 'rejected';
  item.reject_reason = reason.trim();
  recount(view);
  finishApproval('correction', id, 'rejected', actor, null);
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
