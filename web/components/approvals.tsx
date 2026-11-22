'use client';

import {useState} from 'react';

import * as api from '../lib/api';
import {formatClock, formatCount, formatMoney, plural} from '../lib/format';
import type {Approval, ApprovalDone, CaseSummary, LineguardState} from '../lib/types';
import {emailStatusWord, languageWord, optionKindWord, roleWord} from '../lib/words';

import {holdsRole, useAction, usePage} from './page-context';
import {ErpPreview, erpEffect} from './erp-preview';
import {ApproverNote, Button, Clock, ErrorNote, RejectForm, Tag} from './ui';

function costText(entry: Approval): string {
  if (entry.cost_unknown) {
    return 'Not known yet';
  }
  return entry.cost_eur !== null && entry.cost_eur > 0 ? formatMoney(entry.cost_eur) : 'None';
}

/** What Lineguard does after the click, in one or two sentences. */
function approveEffect(entry: Approval, live: boolean): string {
  if (entry.kind === 'unclosable_gap') {
    return 'Lineguard records that you saw the shortage. It does not arrange a delivery or send an email.';
  }
  if (entry.type !== 'decision') {
    return erpEffect(entry.erp_writer);
  }
  if (entry.email === null) {
    return 'Lineguard records the decision under your name and starts this step.';
  }
  const to = entry.email.to_addr ?? 'the supplier';
  return live
    ? `Lineguard sends the mail to ${to} one time.`
    : `Lineguard writes the mail to ${to} to the log. Mail mode is "log only", so no mail leaves the company.`;
}

function rejectEffect(entry: Approval): string {
  return entry.type === 'decision'
    ? 'Lineguard discards the mail draft and looks for another option. The case stays open.'
    : 'Lineguard calculates with the ERP quantity again.';
}

interface ItemProps {
  entry: Approval;
  related: CaseSummary | null;
  live: boolean;
  onSelect: (id: number) => void;
}

function Item({entry, related, live, onSelect}: ItemProps) {
  const {person, labels} = usePage();
  const action = useAction();
  const allowed = holdsRole(person, entry.needs_roles);
  const isDecision = entry.type === 'decision';
  const isAlert = entry.kind === 'unclosable_gap';
  const atRisk = related?.units_at_risk ?? 0;
  const text = entry.condition !== null && entry.note !== null ? entry.note : entry.summary;

  const approve = () =>
    void action.run((personId) =>
      isDecision
        ? api.approveDecision(entry.object_id, null, personId)
        : api.approveCorrection(entry.object_id, personId),
    );
  const reject = (reason: string) =>
    void action.run((personId) =>
      isDecision
        ? api.rejectDecision(entry.object_id, reason, personId)
        : api.rejectCorrection(entry.object_id, reason, personId),
    );

  return (
    <li className="lg-approval">
      <div>
        <p className="lg-label">
          {optionKindWord(entry.kind)}
          {entry.supplier_id !== null && ` · ${entry.supplier_id}`}
        </p>
        <h3>{entry.title}</h3>
        {text !== null && <p className="lg-approval-text">{text}</p>}
        {(entry.commits_money || entry.after_deadline) && (
          <p className="lg-approval-flags">
            {entry.commits_money && <Tag tone="stop">Commits the company to pay</Tag>}
            {entry.after_deadline && <Tag tone="wait">Arrives after the deadline</Tag>}
          </p>
        )}
        <dl className="lg-effects">
          {entry.condition !== null && (
            <div>
              <dt className="lg-label">Condition of the supplier</dt>
              <dd>{entry.condition}</dd>
            </div>
          )}
          {entry.conflict !== null && (
            <div>
              <dt className="lg-label">Differs from the purchase order</dt>
              <dd className="lg-conflict">{entry.conflict}</dd>
            </div>
          )}
          <div>
            <dt className="lg-label">If you approve</dt>
            <dd>{approveEffect(entry, live)}</dd>
          </div>
          {!isAlert && <div>
            <dt className="lg-label">If you reject</dt>
            <dd>{rejectEffect(entry)}</dd>
          </div>}
          {related !== null && (related.breaks_at !== null || atRisk > 0) && (
            <div>
              <dt className="lg-label">If nobody decides</dt>
              <dd>
                {related.breaks_at !== null && (
                  <>
                    The {labels.line} stops <Clock iso={related.breaks_at} distance />.{' '}
                  </>
                )}
                {atRisk > 0 && (
                  <span className="lg-hot">
                    {formatCount(atRisk)} {labels.units} at risk.
                  </span>
                )}
              </dd>
            </div>
          )}
          {entry.email !== null && (
            <div>
              <dt className="lg-label">Mail that goes with the approval</dt>
              <dd>
                <details className="lg-mail">
                  <summary>
                    Read the mail to {entry.email.to_addr ?? 'the supplier'} (
                    {languageWord(entry.email.language)})
                  </summary>
                  <div className="lg-mail-body">
                    <p className="font-medium">{entry.email.subject}</p>
                    <p className="mt-2">{entry.email.body}</p>
                  </div>
                </details>
              </dd>
            </div>
          )}
        </dl>
        {entry.correction_payload !== null && (
          <ErpPreview payload={entry.correction_payload} writer={entry.erp_writer} />
        )}
      </div>

      <dl className="lg-pairs">
        <div>
          <dt className="lg-label">Who decides</dt>
          <dd>
            {entry.approver_name ?? (entry.needs_roles.map(roleWord).join(' or ') || 'Any person')}
            {entry.approver_name !== null && entry.needs_roles.length > 0 && (
              <span className="font-normal text-ink-3">
                {' '}
                · {entry.needs_roles.map(roleWord).join(' or ')}
              </span>
            )}
          </dd>
        </div>
        {entry.deadline !== null && (
          <div>
            <dt className="lg-label">Decide by</dt>
            <dd>
              <Clock iso={entry.deadline} distance />
            </dd>
          </div>
        )}
        {entry.arrives_at !== null && (
          <div>
            <dt className="lg-label">Goods arrive</dt>
            <dd>
              <Clock iso={entry.arrives_at} />
            </dd>
          </div>
        )}
        <div>
          <dt className="lg-label">Cost</dt>
          <dd>{costText(entry)}</dd>
        </div>
        {related !== null && related.component_id !== null && (
          <div>
            <dt className="lg-label">Part</dt>
            <dd className="lg-id">{related.component_id}</dd>
          </div>
        )}
      </dl>

      <div className="lg-approval-actions">
        <Button variant="primary" disabled={!allowed || action.busy} onClick={approve}>
          {action.busy ? 'Working …' : isAlert ? 'Acknowledge' : 'Approve'}
        </Button>
        {!isAlert && <RejectForm label="Reject" busy={action.busy || !allowed} onReject={reject} />}
        {!allowed && <ApproverNote roles={entry.needs_roles} name={entry.approver_name} />}
        <ErrorNote message={action.error} />
        {entry.case_id !== null && (
          <button
            type="button"
            className="lg-link"
            onClick={() => onSelect(entry.case_id as number)}
          >
            Open the case with its documents
          </button>
        )}
      </div>
    </li>
  );
}

function doneText(entry: ApprovalDone): string {
  const who = entry.decided_by === null ? '' : ` by ${entry.decided_by}`;
  if (entry.status === 'rejected') {
    return `rejected${who}`;
  }
  const mail =
    entry.mail_status === null
      ? ''
      : `. Mail to ${entry.mail_to ?? 'the supplier'}: ${emailStatusWord(entry.mail_status).toLowerCase()}`;
  const warning = entry.mail_status === 'failed'
    ? '. Check the mailbox before sending again.'
    : '';
  return `approved${who}${mail}${warning}`;
}

interface ApprovalsProps {
  state: LineguardState;
  selectedId: number | null;
  onSelect: (id: number) => void;
}

/** Everything that waits for a person, above the cases. */
export function Approvals({state, onSelect}: ApprovalsProps) {
  const {person, timezone, now} = usePage();
  const [open, setOpen] = useState(true);
  const waiting = state.approvals;
  const mine = waiting.filter((entry) => holdsRole(person, entry.needs_roles)).length;
  const done = state.approvals_done;
  const cases = [...state.cases_now, ...state.cases_later];

  return (
    <section className="lg-section lg-wrap" aria-labelledby="approvals-title">
      <header className="lg-section-head">
        <h2 id="approvals-title">
          {waiting.length === 0 ? 'Approvals' : `${plural(waiting.length, 'approval', 'approvals')} waiting`}
        </h2>
        <p className="lg-section-sub" role="status">
          {waiting.length === 0
            ? 'Nothing waits for a person.'
            : 'Lineguard prepared each step. Nothing happens until a person approves it.' +
              (person === null ? '' : ` ${person.name} can approve ${mine} of ${waiting.length}.`)}
        </p>
        {waiting.length > 0 && (
          <button
            type="button"
            className="lg-link"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            {open ? 'Hide' : 'Show'}
          </button>
        )}
      </header>
      {open && waiting.length > 0 && (
        <ul>
          {waiting.map((entry) => (
            <Item
              key={entry.id}
              entry={entry}
              related={cases.find((item) => item.id === entry.case_id) ?? null}
              live={state.mail_mode === 'LIVE'}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
      {done.length > 0 && (
        <ul className="lg-done" aria-label="Last decisions">
          {done.slice(0, 3).map((entry) => (
            <li key={entry.id}>
              <span className="num">{formatClock(entry.decided_at, timezone, now)}</span> ·{' '}
              {entry.title}: {doneText(entry)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
