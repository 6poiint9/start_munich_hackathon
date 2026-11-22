'use client';

import {useState} from 'react';
import type {KeyboardEvent} from 'react';

import {formatCount, plural} from '../lib/format';
import type {CaseSummary, LineguardState, LogEvent} from '../lib/types';
import {caseStateWord} from '../lib/words';
import type {Tone} from '../lib/words';

import {Strips} from './strips';
import {Tag} from './ui';

type BoardTab = 'now' | 'later' | 'log';

interface RowProps {
  entry: CaseSummary;
  selected: boolean;
  onSelect: (id: number) => void;
}

/** Open decisions first, then copies at risk, then the line-stop time. */
function byImpact(left: CaseSummary, right: CaseSummary): number {
  const weight = (entry: CaseSummary) => {
    if (entry.pending.decisions > 0) {
      return 0;
    }
    if (entry.pending.corrections > 0 || entry.pending.emails > 0) {
      return 1;
    }
    return 2;
  };
  const pending = weight(left) - weight(right);
  if (pending !== 0) {
    return pending;
  }
  const risk = (right.units_at_risk ?? 0) - (left.units_at_risk ?? 0);
  if (risk !== 0) {
    return risk;
  }
  const leftStop = left.breaks_at ?? left.act_by ?? '';
  const rightStop = right.breaks_at ?? right.act_by ?? '';
  if (leftStop !== rightStop) {
    return leftStop < rightStop ? -1 : 1;
  }
  return (left.rank ?? 9999) - (right.rank ?? 9999);
}

/** A short title: the part for a shortage, the receipt for a booking error. */
function rowTitle(entry: CaseSummary): string {
  const cut = entry.title.indexOf(':');
  const head = cut > 0 ? entry.title.slice(0, cut) : entry.title;
  if (entry.kind === 'gap') {
    return head.replace(/\s*\([^)]*\)\s*$/, '').trim() || head;
  }
  if (entry.kind === 'booking_finding') {
    return head;
  }
  return entry.title;
}

function rowPill(entry: CaseSummary, waiting: boolean): {tone: Tone; text: string} {
  if (waiting) {
    return {tone: 'wait', text: 'Your turn'};
  }
  if (entry.state === 'unclosable') {
    return {tone: 'stop', text: 'No fix'};
  }
  if (entry.state === 'approved' || entry.state === 'in_execution') {
    return {tone: 'go', text: 'Approved'};
  }
  return {tone: 'neutral', text: caseStateWord(entry.state)};
}

function Row({entry, selected, onSelect, state, partners}: RowProps & {state: LineguardState; partners: number[]}) {
  const ids = [entry.id, ...partners];
  const waiting = state.approvals.some((item) => item.case_id !== null && ids.includes(item.case_id));
  const pill = rowPill(entry, waiting);
  return (
    <li>
      <button
        type="button"
        aria-current={selected ? 'true' : undefined}
        onClick={() => onSelect(entry.id)}
        className="lg-row lg-row-card lg-row-min"
      >
        <span className="lg-row-title">{rowTitle(entry)}</span>
        <Tag tone={pill.tone}>{pill.text}</Tag>
      </button>
    </li>
  );
}

interface GroupProps {
  state: LineguardState;
  entries: CaseSummary[];
  total: number;
  empty: string;
  selectedId: number | null;
  onSelect: (id: number) => void;
}

function Group({state, entries, total, empty, selectedId, onSelect}: GroupProps) {
  const gapParts = new Map(
    entries.filter((entry) => entry.kind === 'gap' && entry.component_id !== null).map((entry) => [entry.component_id, entry.id]),
  );
  const partnersOf = (entry: CaseSummary) =>
    entry.kind === 'gap'
      ? entries.filter((other) => other.kind === 'booking_finding' && other.component_id === entry.component_id).map((other) => other.id)
      : [];
  const ordered = [...entries]
    .filter((entry) => !(entry.kind === 'booking_finding' && gapParts.has(entry.component_id)))
    .sort(byImpact);
  const more = total - entries.length;
  if (ordered.length === 0) {
    return <p className="lg-empty">{empty}</p>;
  }
  return (
    <>
      <ul className="lg-rows">
        {ordered.map((entry) => (
          <Row key={entry.id} entry={entry} selected={entry.id === selectedId || partnersOf(entry).includes(selectedId ?? -1)} onSelect={onSelect} state={state} partners={partnersOf(entry)} />
        ))}
      </ul>
      {more > 0 && (
        <p className="lg-more">
          {more === 1 ? '1 more case' : `${formatCount(more)} more cases`}
        </p>
      )}
    </>
  );
}

interface CaseListProps {
  state: LineguardState;
  events: LogEvent[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

/** The open work over all cases, next to the section title. */
export function CaseCounters({state}: {state: LineguardState}) {
  const {counters, labels} = state;
  return (
    <p className="lg-section-sub">
      Open:{' '}
      <span className={counters.open_decisions > 0 ? 'lg-hot' : undefined}>
        {plural(counters.open_decisions, 'decision', 'decisions')}
      </span>
      , {plural(counters.open_corrections, 'ERP correction', 'ERP corrections')},{' '}
      {plural(counters.open_emails, 'mail draft', 'mail drafts')}. Cases with an open decision
      come first, then the cases with the most {labels.units} at risk.
    </p>
  );
}

export function CaseList({state, events, selectedId, onSelect}: CaseListProps) {
  const [tab, setTab] = useState<BoardTab>(
    () => state.cases_later.some((entry) => entry.id === selectedId) ? 'later' : 'now',
  );
  const {counters, booking_review: review, problems} = state;
  const firstProblem = problems.length > 0 ? problems[0] : undefined;
  const tabs: {id: BoardTab; label: string; count: number}[] = [
    {id: 'now', label: 'Now', count: Math.max(counters.now_total, state.cases_now.length)},
    {id: 'later', label: 'Later', count: Math.max(counters.later_total, state.cases_later.length)},
    {id: 'log', label: 'Log', count: events.length},
  ];

  const onTabsKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const order: BoardTab[] = ['now', 'later', 'log'];
    const index = order.indexOf(tab);
    let next = index;
    if (event.key === 'ArrowRight') {
      next = (index + 1) % order.length;
    } else if (event.key === 'ArrowLeft') {
      next = (index - 1 + order.length) % order.length;
    } else {
      return;
    }
    event.preventDefault();
    const id = order[next];
    if (id === undefined) {
      return;
    }
    setTab(id);
    document.getElementById(`tab-${id}`)?.focus();
  };

  return (
    <nav aria-label="Cases" className="lg-cases">
      <div role="tablist" aria-label="Case groups" className="lg-tabs" onKeyDown={onTabsKey}>
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={tab === item.id}
            aria-controls={`panel-${item.id}`}
            tabIndex={tab === item.id ? 0 : -1}
            className="lg-tab"
            onClick={() => setTab(item.id)}
          >
            {item.label}
            <span className="lg-tab-count">{formatCount(item.count)}</span>
            {item.id === 'log' && problems.length > 0 && (
              <span className="lg-dot" aria-hidden="true" />
            )}
          </button>
        ))}
      </div>
      {firstProblem !== undefined && tab !== 'log' && (
        <button type="button" className="lg-problem" onClick={() => setTab('log')}>
          <span className="lg-hot">{plural(problems.length, 'problem', 'problems')}. </span>
          {firstProblem.error ?? 'Error without a text'}
        </button>
      )}
      <div
        role="tabpanel"
        id={`panel-${tab}`}
        aria-labelledby={`tab-${tab}`}
        className="lg-cases-scroll"
      >
        {tab === 'now' && (
          <Group
            state={state}
            entries={state.cases_now}
            total={counters.now_total}
            empty="No shortage. Each line is covered."
            selectedId={selectedId}
            onSelect={onSelect}
          />
        )}
        {tab === 'later' && (
          <Group
            state={state}
            entries={state.cases_later}
            total={counters.later_total}
            empty="No risk for a later date."
            selectedId={selectedId}
            onSelect={onSelect}
          />
        )}
        {tab === 'log' && (
          <div className="lg-log">
            <p className="text-meta text-ink-2">
              Lineguard checked <span className="num">{formatCount(review.receipts_checked)}</span>{' '}
              goods receipts and found{' '}
              <span className="num">
                {plural(review.findings, 'booking error', 'booking errors')}
              </span>
              .
            </p>
            <Strips problems={problems} events={events} />
          </div>
        )}
      </div>
    </nav>
  );
}
