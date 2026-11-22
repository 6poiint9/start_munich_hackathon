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
        <h3 className="lg-label">Problems · {problems.length}</h3>
        {problems.length === 0 ? (
          <p className="lg-empty">No problem. Lineguard processed each event.</p>
        ) : (
          <ul>
            {problems.map((problem, index) => (
              <li key={problem.event_id ?? index}>
                <span className="font-medium">{eventTypeWord(problem.type)}</span>{' '}
                <span className="lg-log-error">{problem.error ?? 'Error without a text'}</span>
                {problem.event_id !== null && (
                  <span className="lg-id"> event {problem.event_id}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h3 className="lg-label">Events · {events.length}</h3>
        {events.length === 0 ? (
          <p className="lg-empty">No event yet.</p>
        ) : (
          <ol>
            {events.map((event) => {
              const payload = payloadText(event.payload);
              return (
                <li key={event.id}>
                  <span className="lg-log-time">{formatClock(event.created_at, timezone, now)}</span>{' '}
                  <span className="font-medium">{eventTypeWord(event.type)}</span>{' '}
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
