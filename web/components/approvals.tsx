'use client';

import * as api from '../lib/api';
import {formatMoney, formatStamp} from '../lib/format';
import type {Approval, ApprovalDone} from '../lib/types';
import {
  decisionStatusWord,
  emailStatusWord,
  languageWord,
  optionKindWord,
  roleWord,
} from '../lib/words';

import {holdsRole, useAction, usePage} from './page-context';
import {ApproverNote, Button, Clock, ErrorNote} from './ui';

function costText(item: Approval): string {
  if (item.cost_unknown) {
    return 'Kosten unbekannt';
  }
  return formatMoney(item.cost_eur);
}

function warningText(item: Approval): string | null {
  const parts = [
    item.conflict === null ? null : `Konflikt: ${item.conflict}`,
    item.condition === null ? null : `Bedingung: ${item.condition}`,
  ].filter((part) => part !== null);
  return parts.length === 0 ? null : parts.join(' · ');
}

function doneMail(item: ApprovalDone): string | null {
  if (item.mail_status === null && item.mail_to === null) {
    return null;
  }
  const status = emailStatusWord(item.mail_status);
  return item.mail_to === null ? `Mail ${status}` : `Mail an ${item.mail_to}, ${status}`;
}

interface QueueProps {
  items: Approval[];
  done: ApprovalDone[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/** The inbox in the left column, plus the short history under it. */
export function ApprovalQueue({items, done, selectedId, onSelect}: QueueProps) {
  const {timezone} = usePage();
  return (
    <div className="lg-inbox">
      {items.length === 0 ? (
        <p className="lg-empty">Keine Freigabe offen.</p>
      ) : (
        <ul className="lg-rows">
          {items.map((item) => {
            const warning = warningText(item);
            return (
              <li key={item.id}>
                <button
                  type="button"
                  className="lg-row lg-approval-row"
                  aria-current={item.id === selectedId ? 'true' : undefined}
                  onClick={() => onSelect(item.id)}
                >
                  <span className="lg-row-main">
                    <span className="lg-row-title">{item.title}</span>
                    {item.summary !== null && <span className="lg-row-meta">{item.summary}</span>}
                    <span className="lg-row-meta">
                      <span>{item.approver_name ?? (item.needs_roles.map(roleWord).join(', ') || '–')}</span>
                      {item.deadline !== null && (
                        <span>
                          {' · '}
                          <Clock iso={item.deadline} distance />
                        </span>
                      )}
                      <span> · {costText(item)}</span>
                      {item.commits_money && <span> · bindet Geld</span>}
                      {item.after_deadline && <span className="lg-warn-text"> · nach der Frist</span>}
                    </span>
                    {warning !== null && <span className="lg-row-warn">{warning}</span>}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <section className="lg-done" aria-label="Zuletzt freigegeben">
        <h3>Zuletzt freigegeben</h3>
        {done.length === 0 ? (
          <p className="lg-empty">Noch keine Freigabe.</p>
        ) : (
          <ul>
            {done.map((item) => {
              const mail = doneMail(item);
              return (
                <li key={item.id}>
                  <p className="lg-done-title">{item.title}</p>
                  <p className="lg-done-meta">
                    <span>{decisionStatusWord(item.status)}</span>
                    {item.decided_by !== null && <span> · {item.decided_by}</span>}
                    {item.decided_at !== null && (
                      <span>
                        {' · '}
                        <time dateTime={item.decided_at} className="num">
                          {formatStamp(item.decided_at, timezone)}
                        </time>
                      </span>
                    )}
                    {mail !== null && <span> · {mail}</span>}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

interface ViewProps {
  item: Approval;
  onOpenCase: (caseId: number) => void;
}

/** The selected approval: the draft, then one approve button. */
export function ApprovalView({item, onOpenCase}: ViewProps) {
  const action = useAction();
  const {person} = usePage();
  const allowed = holdsRole(person, item.needs_roles);
  const warning = warningText(item);
  const objectId = item.object_id;
  const caseId = item.case_id;
  const mail = item.email;
  const approve = () => {
    if (objectId === null) {
      return;
    }
    void action.run((personId) =>
      item.type === 'correction'
        ? api.approveCorrection(objectId, personId)
        : api.approveDecision(objectId, null, personId),
    );
  };
  return (
    <article className="lg-approval" aria-label={`Freigabe: ${item.title}`}>
      <header className="lg-approval-head">
        {item.kind !== null && <p className="lg-approval-kicker">{optionKindWord(item.kind)}</p>}
        <h2>{item.title}</h2>
        {item.summary !== null && <p className="lg-approval-summary">{item.summary}</p>}
        <p className="lg-approval-meta">
          <span>
            Freigabe durch {item.approver_name ?? (item.needs_roles.map(roleWord).join(' oder ') || 'jede Rolle')}
          </span>
          {item.deadline !== null && (
            <span>
              {' · bis '}
              <Clock iso={item.deadline} distance />
            </span>
          )}
          <span> · {costText(item)}</span>
          {item.commits_money && <span> · bindet Geld</span>}
          {item.after_deadline && <span className="lg-warn-text"> · nach der Frist</span>}
          {item.arrives_at !== null && (
            <span>
              {' · Ankunft '}
              <Clock iso={item.arrives_at} distance />
            </span>
          )}
          {item.supplier_id !== null && <span className="lg-id"> · {item.supplier_id}</span>}
        </p>
        {warning !== null && <p className="lg-approval-warn">{warning}</p>}
        {item.note !== null && <p className="lg-approval-note">{item.note}</p>}
      </header>
      <section className="lg-mail-draft" aria-label="Mailentwurf">
        <h3>Mailentwurf</h3>
        {mail === null ? (
          <p className="lg-approval-note">Keine Mail zu dieser Freigabe.</p>
        ) : (
          <>
            <p>
              An <span className="lg-approval-strong">{mail.to_addr ?? 'unbekannt'}</span>
              {mail.language !== null && <span className="lg-approval-note"> · {languageWord(mail.language)}</span>}
              {mail.commits_money && <span> · bindet Geld</span>}
            </p>
            <p className="lg-approval-strong">{mail.subject ?? '(ohne Betreff)'}</p>
            {mail.body !== null && <pre className="lg-mail-body">{mail.body}</pre>}
          </>
        )}
      </section>
      <div className="lg-approval-actions">
        {allowed && objectId !== null ? (
          <Button variant="primary" large disabled={action.busy} onClick={approve}>
            {action.busy ? 'Wird freigegeben …' : 'Freigeben'}
          </Button>
        ) : (
          objectId !== null && <ApproverNote roles={item.needs_roles} name={item.approver_name} />
        )}
        {caseId !== null && <Button onClick={() => onOpenCase(caseId)}>Fall öffnen</Button>}
        <ErrorNote message={action.error} />
      </div>
    </article>
  );
}
