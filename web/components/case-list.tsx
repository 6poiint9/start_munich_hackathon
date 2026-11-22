'use client';

import type {KeyboardEvent} from 'react';

import {formatCount, plural} from '../lib/format';
import type {CaseSummary, LineguardState, LogEvent} from '../lib/types';
import {caseStateWord} from '../lib/words';

import {ApprovalQueue} from './approvals';
import {usePage} from './page-context';
import {Strips} from './strips';
import {Clock} from './ui';

export type BoardTab = 'now' | 'later' | 'approvals' | 'log';

type Signal = 'ok' | 'warn' | 'risk';

const SIGNAL_WORD: Record<Signal, string> = {
  ok: 'Gedeckt',
  warn: 'Achtung',
  risk: 'Risiko',
};

interface RowProps {
  entry: CaseSummary;
  selected: boolean;
  onSelect: (id: number) => void;
}

function pendingParts(entry: CaseSummary): string[] {
  const {decisions, corrections, emails} = entry.pending;
  return [
    decisions > 0 ? plural(decisions, 'Entscheidung', 'Entscheidungen') : null,
    corrections > 0 ? plural(corrections, 'Korrektur', 'Korrekturen') : null,
    emails > 0 ? plural(emails, 'Mailentwurf', 'Mailentwürfe') : null,
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

function Secondary({entry}: {entry: CaseSummary}) {
  const waiting = pendingParts(entry).length > 0;
  if (!waiting && entry.breaks_at === null && entry.act_by === null) {
    return caseStateWord(entry.state);
  }
  return (
    <>
      {waiting && 'Wartet auf Freigabe'}
      {entry.breaks_at !== null && (
        <>
          {waiting && ' · '}
          <span className="lg-nowrap">
            steht ab <Clock iso={entry.breaks_at} />
          </span>
        </>
      )}
      {entry.breaks_at === null && entry.act_by !== null && (
        <>
          {waiting && ' · '}
          <span className="lg-nowrap">
            handeln bis <Clock iso={entry.act_by} />
          </span>
        </>
      )}
    </>
  );
}

function Row({entry, selected, onSelect}: RowProps) {
  const {labels} = usePage();
  const signal = rowSignal(entry);
  const atRisk = entry.units_at_risk !== null && entry.units_at_risk > 0;
  return (
    <li>
      <button
        type="button"
        aria-current={selected ? 'true' : undefined}
        onClick={() => onSelect(entry.id)}
        className="lg-row"
      >
        <span className="lg-signal" data-signal={signal} aria-hidden="true" />
        <span className="lg-row-main">
          <span className="sr-only">{SIGNAL_WORD[signal]}. </span>
          <span className="lg-row-title">{entry.title}</span>
          <span className="lg-row-meta">
            <Secondary entry={entry} />
          </span>
        </span>
        {atRisk ? (
          <span className="lg-row-figure">
            {formatCount(entry.units_at_risk)}
            <span className="sr-only"> {labels.units}</span>
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
          {more === 1 ? '1 weiterer Fall' : `${formatCount(more)} weitere Fälle`}
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
  tab: BoardTab;
  onTab: (tab: BoardTab) => void;
  approvalId: string | null;
  onApproval: (id: string) => void;
}

export function CaseList({
  state,
  events,
  selectedId,
  onSelect,
  tab,
  onTab,
  approvalId,
  onApproval,
}: CaseListProps) {
  const {counters, booking_review: review, problems, approvals, approvals_done: done} = state;
  const firstProblem = problems.length > 0 ? problems[0] : undefined;
  const tabs: {id: BoardTab; label: string; count: number}[] = [
    {id: 'now', label: 'Jetzt', count: Math.max(counters.now_total, state.cases_now.length)},
    {id: 'later', label: 'Danach', count: Math.max(counters.later_total, state.cases_later.length)},
    {id: 'approvals', label: 'Freigaben', count: approvals.length},
    {id: 'log', label: 'Protokoll', count: events.length},
  ];

  const onTabsKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const order: BoardTab[] = ['now', 'later', 'approvals', 'log'];
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
    onTab(id);
    document.getElementById(`tab-${id}`)?.focus();
  };

  return (
    <nav aria-label="Fälle" className="lg-list">
      <div className="lg-panel-head">
        <div className="lg-panel-title">
          <h2>{tab === 'approvals' ? 'Freigaben' : 'Fälle'}</h2>
          <p className="lg-open-line">
            Offen:{' '}
            <span className={counters.open_decisions > 0 ? 'lg-hot' : undefined}>
              {plural(counters.open_decisions, 'Entscheidung', 'Entscheidungen')}
            </span>
            {' · '}
            {plural(counters.open_corrections, 'Korrektur', 'Korrekturen')}
            {' · '}
            {plural(counters.open_emails, 'Mailentwurf', 'Mailentwürfe')}
          </p>
        </div>
        <div role="tablist" aria-label="Fallgruppen" className="lg-tabs" onKeyDown={onTabsKey}>
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
              onClick={() => onTab(item.id)}
            >
              {item.label}
              <span className="lg-tab-count">{formatCount(item.count)}</span>
              {item.id === 'log' && problems.length > 0 && (
                <span className="lg-alert-dot" aria-hidden="true" />
              )}
            </button>
          ))}
        </div>
      </div>
      {firstProblem !== undefined && tab !== 'log' && (
        <button type="button" className="lg-problem" onClick={() => onTab('log')}>
          <span className="lg-hot">{plural(problems.length, 'Problem', 'Probleme')}: </span>
          {firstProblem.error ?? 'Fehler ohne Text'}
        </button>
      )}
      <div
        role="tabpanel"
        id={`panel-${tab}`}
        aria-labelledby={`tab-${tab}`}
        className="lg-panel-scroll"
      >
        {tab === 'now' && (
          <Group
            entries={state.cases_now}
            total={counters.now_total}
            empty="Keine Lücke. Jede Linie ist gedeckt."
            selectedId={selectedId}
            onSelect={onSelect}
          />
        )}
        {tab === 'later' && (
          <Group
            entries={state.cases_later}
            total={counters.later_total}
            empty="Nichts, was später droht."
            selectedId={selectedId}
            onSelect={onSelect}
          />
        )}
        {tab === 'approvals' && (
          <ApprovalQueue
            items={approvals}
            done={done}
            selectedId={approvalId}
            onSelect={onApproval}
          />
        )}
        {tab === 'log' && (
          <div className="lg-log">
            <p className="lg-receipts">
              <span className="lg-id">{formatCount(review.receipts_checked)}</span> Wareneingänge
              geprüft, <span className="lg-id">{formatCount(review.findings)}</span>{' '}
              {review.findings === 1 ? 'Befund' : 'Befunde'}
            </p>
            <Strips problems={problems} events={events} />
          </div>
        )}
      </div>
    </nav>
  );
}
