'use client';

import {useEffect, useRef, useState} from 'react';
import type {ReactNode} from 'react';

import * as api from '../lib/api';
import {formatCount, formatDistance, formatMoney, formatStamp} from '../lib/format';
import {storePersonId} from '../lib/use-person';
import type {
  Person,
  CaseSummary,
  CaseView,
  Correction,
  Decision,
  Email,
  Evidence,
  EvidenceFile,
  LineguardState,
} from '../lib/types';
import {languageWord} from '../lib/words';
import type {Tone} from '../lib/words';

import {FileDialog} from './evidence';
import {holdsRole, useAction, usePage} from './page-context';
import {ErrorNote} from './ui';

import './case-flow.css';

/**
 * The selected case as a flow, in the style of mockup/index.html: what does
 * not match, the proposal, and what the agents do. A booking error and the
 * shortage it hides show as one flow. Every value and button uses the API.
 */

/** `Grand Heist 6 – Collector's Edition` becomes `Collector's Edition`. */
function shortProduct(description: string | null): string | null {
  if (description === null) {
    return null;
  }
  const parts = description.split(/\s[–-]\s/);
  return parts[parts.length - 1] ?? description;
}

/** `Art Book Grand Heist 6 (96 p, hardcover): 5,900 short` becomes `Art Book Grand Heist 6`. */
function partName(title: string): string {
  const cut = title.indexOf(':');
  const name = cut > 0 ? title.slice(0, cut) : title;
  return name.replace(/\s*\([^)]*\)\s*$/, '').trim() || name;
}

/** `suppliers/SUP-0028_Karton_Nowak/...` gives `Karton Nowak`. */
function supplierName(evidence: Evidence[], supplierId: string | null): string | null {
  for (const fact of evidence) {
    const match = /(?:^|\/)suppliers\/([^/_]+)_([^/]+)\//.exec(fact.file?.path ?? '');
    if (match !== null && (supplierId === null || match[1] === supplierId)) {
      return (match[2] ?? '').replace(/_/g, ' ');
    }
  }
  return supplierId;
}

/** A mail body splits into the original and the English copy. */
function splitMail(body: string | null): {original: string; english: string | null} {
  const text = body ?? '';
  const parts = text.split(/\n-{2,}\s*English\s*-{2,}\n/i);
  return parts.length > 1
    ? {original: (parts[0] ?? '').trim(), english: parts.slice(1).join('\n').trim()}
    : {original: text.trim(), english: null};
}

function Pill({tone, children}: {tone: Tone; children: ReactNode}) {
  return <span className={`bd-pill bd-${tone}`}>{children}</span>;
}

/* Small line icons in the style of the mockup. */
const ICONS: Record<string, string> = {
  doc: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h6',
  scale: 'M12 3v18M7 21h10M5 7h14M5 7l-3 7a4 4 0 0 0 6 0zM19 7l-3 7a4 4 0 0 0 6 0z',
  person: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M16 11l2 2 4-4',
  send: 'M22 2 11 13M22 2l-7 20-4-9-9-4z',
  db: 'M12 8c4.4 0 8-1.3 8-3s-3.6-3-8-3-8 1.3-8 3 3.6 3 8 3M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
  truck: 'M1 3h15v13H1zM16 8h4l3 3v5h-7M5.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5M18.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5',
  book: 'M2 4h7a3 3 0 0 1 3 3v14a2 2 0 0 0-2-2H2zM22 4h-7a3 3 0 0 0-3 3v14a2 2 0 0 1 2-2h8z',
  mail: 'M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2M22 6l-10 7L2 6',
  table: 'M3 3h18v18H3zM3 9h18M3 15h18M9 3v18',
};

function Icon({name}: {name: string}) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={ICONS[name] ?? ICONS.doc} />
    </svg>
  );
}

function fileIcon(path: string | null): string {
  const name = (path ?? '').toLowerCase();
  if (name.includes('approval_policy')) {
    return 'book';
  }
  if (name.endsWith('.csv') || name.endsWith('.xlsx')) {
    return 'table';
  }
  if (name.includes('/notices/') || name.includes('oferta') || name.includes('offer')) {
    return 'mail';
  }
  return 'doc';
}

/** One card on the board: a case, or a booking error with its shortage. */
interface Group {
  key: string;
  cases: CaseSummary[];
  main: CaseSummary;
  finding: CaseSummary | null;
  gap: CaseSummary | null;
}

function groupCases(cases: CaseSummary[]): Group[] {
  const groups: Group[] = [];
  const byPart = new Map<string, Group>();
  for (const entry of cases) {
    const joinable = entry.component_id !== null && (entry.kind === 'gap' || entry.kind === 'booking_finding');
    const known = joinable ? byPart.get(entry.component_id ?? '') : undefined;
    const group: Group = known ?? {key: `case-${entry.id}`, cases: [], main: entry, finding: null, gap: null};
    group.cases.push(entry);
    if (entry.kind === 'booking_finding' && group.finding === null) {
      group.finding = entry;
    }
    if (entry.kind === 'gap' && group.gap === null) {
      group.gap = entry;
      group.main = entry;
    }
    if (known === undefined) {
      groups.push(group);
      if (joinable) {
        byPart.set(entry.component_id ?? '', group);
      }
    }
  }
  return groups;
}

function groupHeadline(group: Group): string {
  const part = partName(group.main.title);
  if (group.finding !== null && group.finding.rule === 'decimal_shift') {
    return `${part}: one zero too many`;
  }
  if (group.finding !== null) {
    return `${part}: booking does not match`;
  }
  if (group.gap !== null) {
    return `${part}: ${formatCount(Math.abs(group.gap.gap_qty ?? 0))} short`;
  }
  return group.main.title;
}

/** The group of the selected case: a booking error and its shortage belong together. */
function groupFor(state: LineguardState, caseId: number | null): Group | null {
  if (caseId === null) {
    return null;
  }
  const groups = groupCases([...state.cases_now, ...state.cases_later]);
  return groups.find((group) => group.cases.some((entry) => entry.id === caseId)) ?? null;
}

interface CaseFlowProps {
  state: LineguardState;
  caseId: number | null;
}

/** The selected case as a flow: what does not match, the proposal, the agents. */
export function CaseFlow({state, caseId}: CaseFlowProps) {
  const group = groupFor(state, caseId);
  if (group === null) {
    return <p className="bd-empty">Select a case on the left.</p>;
  }
  return <Story key={group.key} group={group} state={state} />;
}

/** Loads a case again after each poll of the state. */
function useCaseView(id: number | null, stamp: unknown): CaseView | null {
  const [view, setView] = useState<CaseView | null>(null);
  useEffect(() => {
    if (id === null) {
      return;
    }
    let current = true;
    api
      .getCase(id)
      .then((next) => {
        if (current) {
          setView(next);
        }
      })
      .catch(() => undefined);
    return () => {
      current = false;
    };
  }, [id, stamp]);
  return id === null || view?.case.id !== id ? null : view;
}

interface OpenFile {
  file: EvidenceFile;
  locator: string | null;
}

/** The case as a flow, in the style of the mockup. */
function Story({group, state}: {group: Group; state: LineguardState}) {
  const {timezone, people} = usePage();
  const findingView = useCaseView(group.finding?.id ?? null, state);
  const gapView = useCaseView(group.gap?.id ?? null, state);
  const mainView = useCaseView(group.finding === null && group.gap === null ? group.main.id : null, state);
  const views = [findingView, gapView, mainView].filter((view): view is CaseView => view !== null);
  const [mail, setMail] = useState<Email | null>(null);
  const [file, setFile] = useState<OpenFile | null>(null);


  const ids = new Set(group.cases.map((entry) => entry.id));
  const approvals = state.approvals.filter((item) => item.case_id !== null && ids.has(item.case_id));
  const evidence = views.flatMap((view) => view.evidence);
  const finding = views.find((view) => view.finding !== null)?.finding ?? null;
  const note = evidence.find((fact) => fact.fact_type === 'delivery_note_qty') ?? null;
  const check = (name: string) => {
    const found = finding?.checks.find((entry) => entry.name === name);
    return typeof found?.value === 'number' ? found.value : null;
  };
  const factOf = (type: string) => evidence.find((fact) => fact.fact_type === type && fact.file !== null) ?? null;
  const emails = dedupe(views.flatMap((view) => view.emails));
  const decisions = views.flatMap((view) => view.decisions);
  const options = views.flatMap((view) => view.options);
  const corrections: Correction[] = dedupe(views.flatMap((view) => view.corrections));
  const detailView = gapView ?? mainView;
  const product = state.products.find((item) => item.product_id === group.main.product_id);
  const productName = shortProduct(product?.description ?? null) ?? state.labels.units;
  const atRisk = group.gap?.units_at_risk ?? group.main.units_at_risk;

  const decisionItem = approvals.find((item) => item.type === 'decision') ?? null;
  const correctionItem = approvals.find((item) => item.type === 'correction') ?? null;
  const approvedDecision: Decision | null = decisions.find((entry) => entry.status === 'approved') ?? null;
  const decision: Decision | null =
    (decisionItem !== null ? decisions.find((entry) => entry.id === decisionItem.object_id) : undefined) ?? approvedDecision;
  const option = options.find((entry) => entry.id === decision?.recommended_option) ?? null;
  const orderMail =
    emails.find((entry) => entry.direction === 'out' && entry.commits_money) ??
    emails.find((entry) => entry.direction === 'out') ??
    null;
  const replies = emails.filter((entry) => entry.direction === 'in');
  const correction = corrections[0] ?? null;
  const correctionDone = correction !== null && ['approved', 'handed_over', 'posted', 'verified'].includes(correction.status);
  const erpOwner = people.find((entry) => entry.roles.includes(correction?.approver_role ?? 'erp_owner')) ?? null;
  const approved = approvedDecision !== null;
  const supplier = supplierName(evidence, option?.supplier_id ?? decisionItem?.supplier_id ?? null);

  const headline = groupHeadline(group);

  type Row = {key: string; icon: string; name: string; tone: 'done' | 'run' | 'wait'; state: ReactNode};
  const rows: Row[] = [];
  if (note !== null || evidence.some((fact) => fact.extracted_by === 'llm' || fact.extracted_by === 'vision')) {
    rows.push({key: 'read', icon: 'doc', name: 'Reader agent', tone: 'done', state: note?.corrected ? 'Scan read, including handwriting' : 'Documents read'});
  }
  if (finding !== null) {
    rows.push({key: 'check', icon: 'scale', name: 'Check agent', tone: 'done', state: `${formatCount(finding.booked_qty)} → ${formatCount(finding.proposed_qty)}`});
  }
  if (decision !== null) {
    rows.push({key: 'approval', icon: 'person', name: 'Approval', tone: approved ? 'done' : 'wait', state: approved ? (approvedDecision?.decided_by ?? 'Approved') : `Waits for ${decision.approver_name ?? 'a person'}`});
  }
  if (orderMail !== null) {
    const sent = orderMail.status === 'sent' || orderMail.status === 'dry_run';
    rows.push({
      key: 'order',
      icon: 'send',
      name: 'Order agent',
      tone: sent ? 'done' : 'wait',
      state: (
        <button type="button" className="bd-link" onClick={() => setMail(orderMail)}>
          {sent ? (orderMail.status === 'dry_run' ? 'View mail (test mode)' : 'View mail') : 'Draft ready · view'}
        </button>
      ),
    });
  }
  if (correction !== null) {
    rows.push({
      key: 'correction',
      icon: 'db',
      name: 'Correction agent',
      tone: correctionDone ? 'done' : 'wait',
      state: correctionDone ? `Handed to ${correction.approved_by ?? erpOwner?.name ?? 'the ERP owner'}` : `Waits for ${erpOwner?.name ?? 'the ERP owner'}`,
    });
  }
  if (orderMail !== null && orderMail.status === 'sent') {
    const reminders = emails.filter((entry) => entry.direction === 'out' && (entry.reason ?? '').startsWith('Follow-up'));
    const lastReminder = reminders[reminders.length - 1] ?? null;
    rows.push({
      key: 'follow',
      icon: 'truck',
      name: 'Follow-up agent',
      tone: replies.length > 0 ? 'done' : 'run',
      state:
        replies.length > 0 ? (
          <button type="button" className="bd-link" onClick={() => setMail(replies[replies.length - 1] ?? null)}>
            Reply received · view
          </button>
        ) : lastReminder !== null ? (
          `Reminder sent ${formatStamp(lastReminder.sent_at ?? lastReminder.created_at, timezone)}`
        ) : (
          `Waits for a reply since ${formatStamp(orderMail.sent_at, timezone)}`
        ),
    });
  }
  const doneCount = rows.filter((row) => row.tone === 'done').length;
  const open = rows.filter((row) => row.tone !== 'done');
  const statusPill =
    approvals.length > 0 ? (
      <Pill tone="wait">Waits for you</Pill>
    ) : open.length === 1 && open[0]?.key === 'follow' ? (
      <Pill tone="work">Waits for the supplier</Pill>
    ) : open.length > 0 ? (
      <Pill tone="work">Agents at work</Pill>
    ) : rows.length > 0 ? (
      <Pill tone="go">Approved</Pill>
    ) : (
      <Pill tone="neutral">Open</Pill>
    );

  const chips = dedupe(
    evidence.filter((fact) => fact.file !== null).map((fact) => ({id: fact.file?.id ?? 0, fact})),
  ).map((entry) => entry.fact);

  const decisionTarget =
    decisionItem === null
      ? null
      : (people.find((entry) => decisionItem.approver_name !== null && entry.name === decisionItem.approver_name) ??
        people.find((entry) => decisionItem.needs_roles.some((role) => entry.roles.includes(role))) ??
        null);
  const gain = option?.qty_gain ?? null;
  const isAlert = decisionItem?.kind === 'unclosable_gap';
  const fixText =
    gain !== null && supplier !== null ? `Order ${formatCount(gain)} from ${supplier}` : (decisionItem?.title ?? option?.title ?? null);
  const proposalMail = decisionItem?.email == null ? null : (emails.find((entry) => entry.id === decisionItem.email?.id) ?? null);

  return (
    <div className="bd bd-flow">
      <article aria-label={headline}>
        <header className="bd-flow-head">
          <h2>{headline}</h2>
          {statusPill}
        </header>

        {views.length === 0 ? (
          <p className="bd-empty">Loading the case …</p>
        ) : (
          <div className="bd-card-l bd-mini">
            {finding !== null && (
              <div className="bd-mini-match">
                {note !== null && (
                  <button
                    type="button"
                    className="bd-paper"
                    title="Open the scan"
                    onClick={() => note.file !== null && setFile({file: note.file, locator: note.locator})}
                  >
                    <span className="bd-paper-top">
                      <span>{note.ref ?? 'Delivery note'}</span>
                      <span>{supplier ?? ''}</span>
                    </span>
                    <span className="bd-paper-qty">
                      {note.corrected && note.printed_value !== null && (
                        <span className="bd-printed">{formatCount(note.printed_value)}</span>
                      )}
                      <span className={note.corrected ? 'bd-hand' : 'bd-typed'}>{formatCount(note.qty)}</span>
                    </span>
                  </button>
                )}
                <p className="bd-mini-line">
                  The ERP says <SourceNumber fact={factOf('gr_qty')} onOpen={setFile} className="bd-red">{formatCount(finding.booked_qty)}</SourceNumber>.
                  <br />
                  Order and delivery note say{' '}
                  <SourceNumber fact={factOf('po_line') ?? note} onOpen={setFile}>{formatCount(finding.proposed_qty ?? check('gr_vs_po'))}</SourceNumber>.
                </p>
              </div>
            )}
            {finding === null && detailView !== null && (
              <p className="bd-mini-line bd-mini-pad">
                Usable <b>{formatCount(detailView.detail.usable)}</b>, needed until the {state.labels.deadline}{' '}
                <b>{formatCount(detailView.detail.need)}</b>.
              </p>
            )}

            {atRisk !== null && atRisk > 0 && (
              <p className="bd-mini-impact">
                {formatCount(atRisk)} {productName} missing at the {state.labels.deadline}.
              </p>
            )}

            {chips.length > 0 && (
              <div className="bd-sources">
                <span className="bd-mini-label">Sources</span>
                {chips.map((fact) => (
                  <button
                    type="button"
                    key={fact.fact_id}
                    className="bd-chip"
                    title={fact.file?.path ?? undefined}
                    onClick={() => fact.file !== null && setFile({file: fact.file, locator: fact.locator})}
                  >
                    <Icon name={fileIcon(fact.file?.path ?? null)} />
                    {fact.label}
                  </button>
                ))}
              </div>
            )}

            {decisionItem !== null && (
              <div className="bd-mini-fix">
                <p className="bd-mini-label">{isAlert ? 'No option arrives in time' : 'Fix'}</p>
                <p className="bd-mini-title">{isAlert ? decisionItem.summary?.split('. ')[0] : fixText}</p>
                {!isAlert && (
                  <p className="bd-muted">
                    {decisionItem.cost_eur !== null && decisionItem.cost_eur > 0 ? formatMoney(decisionItem.cost_eur) : 'No cost'}
                    {decisionItem.arrives_at !== null && ` · arrives ${formatDistance(decisionItem.arrives_at, state.at) ?? ''}`}
                    {proposalMail !== null && (
                      <>
                        {' · '}
                        <button type="button" className="bd-link" onClick={() => setMail(proposalMail)}>
                          mail in {languageWord(proposalMail.language)}
                        </button>
                      </>
                    )}
                  </p>
                )}
                <ActButton
                  label={isAlert ? 'Acknowledge' : 'Approve'}
                  roles={decisionItem.needs_roles}
                  target={decisionTarget}
                  onRun={(personId) => api.approveDecision(decisionItem.object_id, null, personId)}
                />
              </div>
            )}
            {decisionItem === null && approvedDecision !== null && (
              <p className="bd-mini-done">
                ✓ {fixText ?? approvedDecision.title} · approved by {approvedDecision.decided_by ?? 'a person'},{' '}
                {formatStamp(approvedDecision.decided_at, timezone)}
              </p>
            )}

            {correction !== null && correctionDone && (
              <p className="bd-mini-done">
                ✓ ERP correction {formatCount(finding?.booked_qty ?? null)} → {formatCount(finding?.proposed_qty ?? null)} · approved by{' '}
                {correction.approved_by ?? erpOwner?.name ?? 'the ERP owner'}
              </p>
            )}
            {correctionItem !== null && decisionItem === null && (
              <div className="bd-mini-fix">
                <p className="bd-mini-label">Correct the ERP</p>
                <p className="bd-mini-title">
                  {formatCount(finding?.booked_qty ?? null)} → {formatCount(finding?.proposed_qty ?? null)}
                </p>
                <ActButton
                  label="Approve"
                  roles={correctionItem.needs_roles}
                  target={erpOwner}
                  onRun={(personId) => api.approveCorrection(correctionItem.object_id, personId)}
                />
              </div>
            )}

            {rows.length > 0 && (
              <details className="bd-mini-agents">
                <summary>
                  <span>
                    {doneCount === rows.length ? '✓' : '…'} {doneCount} of {rows.length} agent steps done
                  </span>
                  <span className="bd-link">Show steps</span>
                </summary>
                <ol className="bd-rows">
                  {rows.map((row) => (
                    <li key={row.key} className={`bd-row ${row.tone}`}>
                      <span className="bd-ico">
                        <Icon name={row.icon} />
                      </span>
                      <span className="bd-name">{row.name}</span>
                      <span className="bd-state">{row.state}</span>
                    </li>
                  ))}
                </ol>
              </details>
            )}
          </div>
        )}
      </article>
      {mail !== null && <MailDialog email={mail} onClose={() => setMail(null)} />}
      {file !== null && <FileDialog file={file.file} locator={file.locator} onClose={() => setFile(null)} />}
    </div>
  );
}

interface SourceNumberProps {
  fact: Evidence | null;
  onOpen: (file: OpenFile) => void;
  className?: string;
  children: ReactNode;
}

/** A number that opens the document it comes from. */
function SourceNumber({fact, onOpen, className, children}: SourceNumberProps) {
  if (fact === null || fact.file === null) {
    return <b className={className}>{children}</b>;
  }
  const file = fact.file;
  return (
    <button
      type="button"
      className={`bd-num ${className ?? ''}`}
      title={`Open ${file.path ?? 'the source'}`}
      onClick={() => onOpen({file, locator: fact.locator})}
    >
      {children}
    </button>
  );
}

interface ActButtonProps {
  label: string;
  roles: string[];
  target: Person | null;
  onRun: (personId: string | null) => Promise<unknown>;
}

/**
 * The one big button. If the selected person may not click it, the button
 * acts as the person whom the approval rules name, and says so.
 */
function ActButton({label, roles, target, onRun}: ActButtonProps) {
  const {person} = usePage();
  const action = useAction();
  const allowed = holdsRole(person, roles);
  const actor = allowed ? person : target;
  return (
    <div className="bd-mini-act">
      <button
        type="button"
        className="bd-btn primary"
        disabled={action.busy || actor === null}
        onClick={() => {
          if (actor === null) {
            return;
          }
          if (!allowed) {
            storePersonId(actor.person_id);
          }
          void action.run(() => onRun(actor.person_id));
        }}
      >
        {action.busy ? 'Working …' : `${label} as ${actor?.name ?? 'a person with the role'}`}
      </button>
      <ErrorNote message={action.error} />
    </div>
  );
}

function dedupe<T extends {id: number}>(items: T[]): T[] {
  return items.filter((item, index) => items.findIndex((other) => other.id === item.id) === index);
}

function MailDialog({email, onClose}: {email: Email; onClose: () => void}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const {timezone} = usePage();
  const {original, english} = splitMail(email.body);
  useEffect(() => {
    const element = dialog.current;
    if (element !== null && !element.open) {
      element.showModal();
    }
  }, []);
  return (
    <dialog
      ref={dialog}
      className="bd-mail"
      aria-label={email.subject ?? 'Mail'}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialog.current) {
          dialog.current.close();
        }
      }}
    >
      <div className="bd-mail-head">
        <b>{email.subject ?? '(no subject)'}</b>
        <p>
          {email.direction === 'in' ? `From ${email.from_addr ?? 'unknown'}` : `To ${email.to_addr ?? 'unknown'}`}
          {' · '}
          {languageWord(email.language)}
          {email.sent_at !== null && ` · ${formatStamp(email.sent_at, timezone)}`}
          {email.status === 'dry_run' && ' · test mode, not sent'}
          {email.approved_by !== null && ` · approved by ${email.approved_by}`}
        </p>
      </div>
      <div className={english !== null ? 'bd-mail-body two' : 'bd-mail-body'}>
        <div>
          <small>{languageWord(email.language)}</small>
          {original}
        </div>
        {english !== null && (
          <div>
            <small>English</small>
            {english}
          </div>
        )}
      </div>
      <div className="bd-mail-foot">
        <button type="button" className="bd-btn ghost" autoFocus onClick={() => dialog.current?.close()}>
          Close
        </button>
      </div>
    </dialog>
  );
}
