'use client';

import type {ReactNode} from 'react';

import {formatClock} from '../lib/format';
import type {LogEvent, Problem} from '../lib/types';
import {eventStatusTone, eventStatusWord, eventTypeWord} from '../lib/words';

import {usePage} from './page-context';
import {Tag} from './ui';

const PAYLOAD_LIMIT = 140;

function payloadText(payload: unknown): string | null {
  if (payload === null || payload === undefined) {
    return null;
  }
  const text = typeof payload === 'string' ? payload : JSON.stringify(payload);
  if (text === '{}' || text === '') {
    return null;
  }
  return text.length > PAYLOAD_LIMIT ? `${text.slice(0, PAYLOAD_LIMIT)} …` : text;
}

interface StripProps {
  title: string;
  count: number;
  alert?: boolean;
  children: ReactNode;
}

function Strip({title, count, alert = false, children}: StripProps) {
  return (
    <details className="group rounded-sheet border border-rule bg-sheet">
      <summary className="flex list-none items-center gap-2 px-4 py-2">
        <span className="num w-3 text-ink-3 group-open:hidden" aria-hidden="true">+</span>
        <span className="num hidden w-3 text-ink-3 group-open:inline" aria-hidden="true">−</span>
        <span className="font-medium">{title}</span>
        <Tag tone={alert ? 'stop' : 'neutral'}>{count}</Tag>
      </summary>
      <div className="border-t border-rule px-4 py-2">{children}</div>
    </details>
  );
}

interface StripsProps {
  problems: Problem[];
  events: LogEvent[];
}

export function Strips({problems, events}: StripsProps) {
  const {timezone, now} = usePage();
  return (
    <section aria-label="Probleme und Protokoll" className="space-y-2">
      <Strip title="Probleme" count={problems.length} alert={problems.length > 0}>
        {problems.length === 0 ? (
          <p className="text-ink-3">Kein Problem. Jedes Ereignis wurde verarbeitet.</p>
        ) : (
          <ul className="space-y-1">
            {problems.map((problem, index) => (
              <li key={problem.event_id ?? index} className="flex flex-wrap gap-x-3">
                <span className="font-medium">{eventTypeWord(problem.type)}</span>
                <span className="text-stop">{problem.error ?? 'Fehler ohne Text'}</span>
                {problem.event_id !== null && <span className="num text-ink-3">Ereignis {problem.event_id}</span>}
              </li>
            ))}
          </ul>
        )}
      </Strip>
      <Strip title="Protokoll" count={events.length}>
        {events.length === 0 ? (
          <p className="text-ink-3">Noch kein Ereignis.</p>
        ) : (
          <ol className="divide-y divide-rule">
            {events.map((event) => {
              const payload = payloadText(event.payload);
              return (
                <li key={event.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-1">
                  <span className="num w-24 shrink-0 text-ink-3">{formatClock(event.created_at, timezone, now)}</span>
                  <span className="font-medium">{eventTypeWord(event.type)}</span>
                  <Tag tone={eventStatusTone(event.status)}>{eventStatusWord(event.status)}</Tag>
                  {payload !== null && <span className="num min-w-0 break-all text-meta text-ink-3">{payload}</span>}
                </li>
              );
            })}
          </ol>
        )}
      </Strip>
    </section>
  );
}
