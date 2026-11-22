'use client';

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

interface StripsProps {
  problems: Problem[];
  events: LogEvent[];
}

export function Strips({problems, events}: StripsProps) {
  const {timezone, now} = usePage();
  return (
    <>
      <section>
        <h3>
          Probleme
          <span className="lg-log-count">{problems.length}</span>
        </h3>
        {problems.length === 0 ? (
          <p className="lg-empty">Kein Problem. Jedes Ereignis wurde verarbeitet.</p>
        ) : (
          <ul>
            {problems.map((problem, index) => (
              <li key={problem.event_id ?? index}>
                <span className="font-semibold">{eventTypeWord(problem.type)}</span>{' '}
                <span className="lg-log-error">{problem.error ?? 'Fehler ohne Text'}</span>
                {problem.event_id !== null && (
                  <span className="lg-id"> Ereignis {problem.event_id}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h3>
          Protokoll
          <span className="lg-log-count">{events.length}</span>
        </h3>
        {events.length === 0 ? (
          <p className="lg-empty">Noch kein Ereignis.</p>
        ) : (
          <ol>
            {events.map((event) => {
              const payload = payloadText(event.payload);
              return (
                <li key={event.id}>
                  <span className="lg-log-time">{formatClock(event.created_at, timezone, now)}</span>{' '}
                  <span className="font-semibold">{eventTypeWord(event.type)}</span>{' '}
                  <Tag tone={eventStatusTone(event.status)}>
                    {eventStatusWord(event.status)}
                  </Tag>
                  {payload !== null && <span className="lg-log-payload"> {payload}</span>}
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </>
  );
}
