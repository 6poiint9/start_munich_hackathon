'use client';

import {useState} from 'react';

import * as api from '../lib/api';
import {formatClock, formatMoney, plural} from '../lib/format';
import type {Approval, ApprovalDone, LineguardState} from '../lib/types';
import {emailStatusWord, languageWord, optionKindWord, roleWord} from '../lib/words';

import {holdsRole, useAction, usePage} from './page-context';
import {ApproverNote, Button, Clock, ErrorNote, RejectForm, Tag} from './ui';

function costText(entry: Approval): string | null {
  if (entry.cost_unknown) {
    return 'Kosten offen';
  }
  return entry.cost_eur !== null && entry.cost_eur > 0 ? formatMoney(entry.cost_eur) : null;
}

interface ItemProps {
  entry: Approval;
  live: boolean;
  selected: boolean;
  onSelect: (id: number) => void;
}

function Item({entry, live, selected, onSelect}: ItemProps) {
  const {person} = usePage();
  const action = useAction();
  const allowed = holdsRole(person, entry.needs_roles);
  const isDecision = entry.type === 'decision';
  const cost = costText(entry);
  const sends = entry.email !== null;

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

  let approveLabel = 'Freigeben';
  if (sends) {
    approveLabel = live ? 'Freigeben und Mail senden' : 'Freigeben (Mail nur im Protokoll)';
  }

  return (
    <li className="lg-approval" data-selected={selected}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Tag tone="wait">{optionKindWord(entry.kind)}</Tag>
        {entry.commits_money && <Tag tone="stop">bindet die Firma</Tag>}
        {entry.after_deadline && <Tag tone="neutral">kommt nach dem Termin</Tag>}
        {entry.supplier_id !== null && <span className="lg-id text-meta">{entry.supplier_id}</span>}
      </div>
      <h3 className="text-lead font-semibold">{entry.title}</h3>
      {entry.condition !== null && (
        <p className="text-body">
          <span className="field-name">Bedingung laut Lieferant: </span>
          {entry.condition}
        </p>
      )}
      {entry.conflict !== null && (
        <p className="rounded-ctl border border-stop/30 bg-stop-wash px-2 py-1 text-meta text-stop">
          <span className="font-semibold">Abweichung zur Bestellung: </span>
          {entry.conflict}
        </p>
      )}
      {entry.condition !== null && entry.note !== null ? (
        <p className="text-meta text-ink-2">{entry.note}</p>
      ) : (
        entry.summary !== null && <p className="text-meta text-ink-2">{entry.summary}</p>
      )}
      <dl className="flex flex-wrap gap-x-5 gap-y-1 text-meta">
        <div>
          <dt className="field-name">Entscheidet</dt>
          <dd>
            {entry.approver_name ?? (entry.needs_roles.map(roleWord).join(' oder ') || '–')}
          </dd>
        </div>
        {entry.deadline !== null && (
          <div>
            <dt className="field-name">Bis</dt>
            <dd>
              <Clock iso={entry.deadline} distance />
            </dd>
          </div>
        )}
        {entry.arrives_at !== null && (
          <div>
            <dt className="field-name">Ankunft</dt>
            <dd>
              <Clock iso={entry.arrives_at} />
            </dd>
          </div>
        )}
        {cost !== null && (
          <div>
            <dt className="field-name">Kosten</dt>
            <dd className="num">{cost}</dd>
          </div>
        )}
      </dl>
      {entry.email !== null && (
        <details>
          <summary className="cursor-pointer text-meta font-semibold">
            Mail an {entry.email.to_addr ?? 'Lieferant'} ({languageWord(entry.email.language)})
            lesen
          </summary>
          <p className="mt-1 text-meta font-semibold">{entry.email.subject}</p>
          <p className="lg-approval-mail">{entry.email.body}</p>
        </details>
      )}
      <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
        <Button variant="primary" disabled={!allowed || action.busy} onClick={approve}>
          {action.busy ? 'Sende …' : approveLabel}
        </Button>
        <RejectForm label="Ablehnen" busy={action.busy || !allowed} onReject={reject} />
        {entry.case_id !== null && (
          <Button onClick={() => onSelect(entry.case_id as number)}>Fall mit Belegen öffnen</Button>
        )}
      </div>
      {!allowed && <ApproverNote roles={entry.needs_roles} name={entry.approver_name} />}
      <ErrorNote message={action.error} />
    </li>
  );
}

function doneText(entry: ApprovalDone): string {
  const who = entry.decided_by === null ? '' : ` durch ${entry.decided_by}`;
  if (entry.status === 'rejected') {
    return `abgelehnt${who}`;
  }
  const mail =
    entry.mail_status === null
      ? ''
      : `, Mail an ${entry.mail_to ?? 'Lieferant'}: ${emailStatusWord(entry.mail_status)}`;
  return `freigegeben${who}${mail}`;
}

interface ApprovalsProps {
  state: LineguardState;
  selectedId: number | null;
  onSelect: (id: number) => void;
}

/** Everything that waits for a person, above the cases. */
export function Approvals({state, selectedId, onSelect}: ApprovalsProps) {
  const {person, timezone, now} = usePage();
  const [open, setOpen] = useState(true);
  const waiting = state.approvals;
  const mine = waiting.filter((entry) => holdsRole(person, entry.needs_roles)).length;
  const done = state.approvals_done;

  return (
    <section
      className="lg-approvals"
      aria-labelledby="lg-approvals-title"
      data-empty={waiting.length === 0}
    >
      <div className="lg-approvals-head">
        <h2 id="lg-approvals-title">Freigaben</h2>
        {waiting.length > 0 && <span className="lg-approvals-count">{waiting.length}</span>}
        <p className="lg-approvals-sub" role="status">
          {waiting.length === 0
            ? 'Nichts wartet auf eine Person. Der Agent arbeitet allein weiter.'
            : `Der Agent hat ${plural(waiting.length, 'Schritt', 'Schritte')} vorbereitet und wartet auf eine Person.` +
              (person === null ? '' : ` ${mine} davon für ${person.name}.`)}
        </p>
        {waiting.length > 0 && (
          <button
            type="button"
            className="lg-approvals-toggle"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            {open ? 'Einklappen' : 'Anzeigen'}
          </button>
        )}
      </div>
      {open && waiting.length > 0 && (
        <ul className="lg-approvals-list">
          {waiting.map((entry) => (
            <Item
              key={entry.id}
              entry={entry}
              live={state.mail_mode === 'LIVE'}
              selected={entry.case_id !== null && entry.case_id === selectedId}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
      {done.length > 0 && (
        <ul className="lg-approvals-done" aria-label="Zuletzt erledigt">
          {done.slice(0, 3).map((entry) => (
            <li key={entry.id}>
              <strong>{entry.status === 'rejected' ? '✕' : '✓'}</strong>{' '}
              <span className="lg-id">{formatClock(entry.decided_at, timezone, now)}</span>{' '}
              {entry.title}: {doneText(entry)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
