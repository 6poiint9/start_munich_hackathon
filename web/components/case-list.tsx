'use client';

import {useState} from 'react';
import type {KeyboardEvent} from 'react';

import {formatCount, plural} from '../lib/format';
import type {CaseSummary, LineguardState, LogEvent} from '../lib/types';
import {caseKindWord, caseStateWord, roleWord} from '../lib/words';

import {usePage} from './page-context';
import {Strips} from './strips';
import {Clock} from './ui';

type BoardTab = 'now' | 'later' | 'log';

type Signal = 'ok' | 'warn' | 'risk';

interface RowProps {
  entry: CaseSummary;
  selected: boolean;
  onSelect: (id: number) => void;
}

function pendingParts(entry: CaseSummary): string[] {
  const {decisions, corrections, emails} = entry.pending;
  return [
    decisions > 0 ? plural(decisions, 'decision', 'decisions') : null,
    corrections > 0 ? plural(corrections, 'ERP correction', 'ERP corrections') : null,
    emails > 0 ? plural(emails, 'mail draft', 'mail drafts') : null,
  ].filter((part) => part !== null);
}

function rowSignal(entry: CaseSummary): Signal {
  if (entry.state === 'unclosable' || (entry.units_at_risk ?? 0) > 0) {
    return 'risk';
  }
  if (
    entry.pending.decisions > 0 ||
    entry.pending.corrections > 0 ||
    entry.pending.emails > 0
  ) {
    return 'warn';
  }
  if (entry.state === 'confirmed' || entry.state === 'closed') {
    return 'ok';
  }
  return 'warn';
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

/** The next thing that happens in a case, in one short sentence. */
function nextStep(entry: CaseSummary): string | null {
  const pending = pendingParts(entry);
  if (pending.length > 0) {
    return `Waits for approval: ${pending.join(', ')}.`;
  }
  if (entry.state === 'unclosable') {
    return entry.residual_qty !== null && entry.residual_qty > 0
      ? `No option arrives in time. ${formatCount(entry.residual_qty)} stay short.`
      : 'No option arrives in time.';
  }
  if (entry.state === 'in_execution' || entry.state === 'approved') {
    return 'Approved. The step is running.';
  }
  return null;
}

function Row({entry, selected, onSelect}: RowProps) {
  const {labels} = usePage();
  const next = nextStep(entry);
  const signal = rowSignal(entry);
  const atRisk = entry.units_at_risk !== null && entry.units_at_risk > 0;
  const owner = entry.owner_role === null ? null : roleWord(entry.owner_role);
  return (
    <li>
      <button
        type="button"
        aria-current={selected ? 'true' : undefined}
        onClick={() => onSelect(entry.id)}
        className="lg-row"
      >
        <span className="lg-rank">{entry.rank ?? '–'}</span>
        <span className="lg-row-main">
          <span className="lg-row-meta">
            <span className="lg-signal" data-state={signal}>
              {caseKindWord(entry.kind)}
            </span>
            <span>· {caseStateWord(entry.state)}</span>
            {entry.component_id !== null && <span className="lg-id">· {entry.component_id}</span>}
          </span>
          <span className="lg-row-title">{entry.title}</span>
          <span className="lg-row-meta">
            {entry.breaks_at !== null ? (
              <span>
                Line stops <Clock iso={entry.breaks_at} distance />
              </span>
            ) : entry.act_by !== null ? (
              <span>
                Act by <Clock iso={entry.act_by} distance />
              </span>
            ) : entry.due_at !== null ? (
              <span>
                Demand date <Clock iso={entry.due_at} />
              </span>
            ) : null}
            {owner !== null && <span>· Owner: {owner}</span>}
          </span>
          {next !== null && <span className="lg-row-next">{next}</span>}
        </span>
        {atRisk ? (
          <span className="lg-row-risk">
            {formatCount(entry.units_at_risk)}
            <span className="lg-row-risk-label">{labels.units} at risk</span>
          </span>
        ) : (
          <span />
        )}
      </button>
    </li>
  );
}

interface GroupProps {
  entries: CaseSummary[];
  total: number;
  empty: string;
  selectedId: number | null;
  onSelect: (id: number) => void;
}

function Group({entries, total, empty, selectedId, onSelect}: GroupProps) {
  const ordered = [...entries].sort(byImpact);
  const more = total - entries.length;
  if (ordered.length === 0) {
    return <p className="lg-empty">{empty}</p>;
  }
  return (
    <>
      <ul className="lg-rows">
        {ordered.map((entry) => (
          <Row key={entry.id} entry={entry} selected={entry.id === selectedId} onSelect={onSelect} />
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
            entries={state.cases_now}
            total={counters.now_total}
            empty="No shortage. Each line is covered."
            selectedId={selectedId}
            onSelect={onSelect}
          />
        )}
        {tab === 'later' && (
          <Group
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
