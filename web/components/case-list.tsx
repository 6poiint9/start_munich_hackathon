'use client';

import {formatCount, plural} from '../lib/format';
import type {CaseSummary, LineguardState} from '../lib/types';
import {caseKindWord, caseStateTone, caseStateWord} from '../lib/words';

import {usePage} from './page-context';
import {Clock, Tag, cx} from './ui';

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

function Row({entry, selected, onSelect}: RowProps) {
  const {labels} = usePage();
  const pending = pendingParts(entry);
  return (
    <li>
      <button
        type="button"
        aria-current={selected ? 'true' : undefined}
        onClick={() => onSelect(entry.id)}
        className={cx(
          'flex w-full gap-3 border-l-2 px-3 py-2 text-left',
          selected ? 'border-stamp bg-stamp-wash' : 'border-transparent hover:bg-well',
        )}
      >
        <span className="num w-5 shrink-0 pt-0.5 text-right text-meta text-ink-3">
          {entry.rank ?? '–'}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-medium text-ink">{entry.title}</span>
          <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-ink-2">
            <Tag>{caseKindWord(entry.kind)}</Tag>
            <Tag tone={caseStateTone(entry.state)}>{caseStateWord(entry.state)}</Tag>
            {entry.breaks_at !== null ? (
              <span>
                {labels.line} steht ab <Clock iso={entry.breaks_at} />
              </span>
            ) : entry.act_by !== null ? (
              <span>
                handeln bis <Clock iso={entry.act_by} />
              </span>
            ) : null}
            {entry.units_at_risk !== null && entry.units_at_risk > 0 && (
              <span>
                <span className="num font-medium text-stop">{formatCount(entry.units_at_risk)}</span>{' '}
                {labels.units} in Gefahr
              </span>
            )}
          </span>
          {pending.length > 0 && (
            <span className="mt-1 block text-meta font-medium text-stamp-deep">
              Wartet auf Freigabe: {pending.join(' · ')}
            </span>
          )}
        </span>
      </button>
    </li>
  );
}

interface GroupProps {
  title: string;
  entries: CaseSummary[];
  total: number;
  empty: string;
  selectedId: number | null;
  onSelect: (id: number) => void;
}

function Group({title, entries, total, empty, selectedId, onSelect}: GroupProps) {
  const more = total - entries.length;
  return (
    <section className="rounded-sheet border border-rule bg-sheet">
      <header className="flex items-baseline justify-between border-b border-rule px-3 py-2">
        <h2 className="text-lead font-semibold">{title}</h2>
        <p className="num text-meta text-ink-3">{plural(Math.max(total, entries.length), 'Fall', 'Fälle')}</p>
      </header>
      {entries.length === 0 ? (
        <p className="px-3 py-3 text-ink-3">{empty}</p>
      ) : (
        <ul className="divide-y divide-rule">
          {entries.map((entry) => (
            <Row key={entry.id} entry={entry} selected={entry.id === selectedId} onSelect={onSelect} />
          ))}
        </ul>
      )}
      {more > 0 && (
        <p className="border-t border-rule px-3 py-2 text-meta text-ink-3">
          {more === 1 ? '1 weiterer Fall' : `${formatCount(more)} weitere Fälle`}
        </p>
      )}
    </section>
  );
}

interface CaseListProps {
  state: LineguardState;
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export function CaseList({state, selectedId, onSelect}: CaseListProps) {
  const {counters, booking_review: review} = state;
  const waiting = [
    plural(counters.open_decisions, 'Entscheidung', 'Entscheidungen'),
    plural(counters.open_corrections, 'Korrektur', 'Korrekturen'),
    plural(counters.open_emails, 'Mailentwurf', 'Mailentwürfe'),
  ];
  return (
    <nav aria-label="Fälle" className="space-y-3">
      <p className="text-meta text-ink-2">
        <span className="field-name">Offen </span>
        {waiting.join(' · ')}
      </p>
      <Group
        title="Jetzt"
        entries={state.cases_now}
        total={counters.now_total}
        empty="Keine Lücke. Jede Linie ist gedeckt."
        selectedId={selectedId}
        onSelect={onSelect}
      />
      <Group
        title="Danach"
        entries={state.cases_later}
        total={counters.later_total}
        empty="Nichts, was später droht."
        selectedId={selectedId}
        onSelect={onSelect}
      />
      <p className="px-1 text-meta text-ink-3">
        <span className="num text-ink">{formatCount(review.receipts_checked)}</span> Wareneingänge
        geprüft, <span className="num text-ink">{formatCount(review.findings)}</span>{' '}
        {review.findings === 1 ? 'Befund' : 'Befunde'}
      </p>
    </nav>
  );
}
