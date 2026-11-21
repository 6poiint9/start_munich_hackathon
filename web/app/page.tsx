'use client';

import {useMemo} from 'react';

import {CaseDetail} from '../components/case-detail';
import {CaseList} from '../components/case-list';
import {Coverage} from '../components/coverage';
import {PageProvider} from '../components/page-context';
import type {PageContextValue} from '../components/page-context';
import {Strips} from '../components/strips';
import {TopBar} from '../components/top-bar';
import {useLineguard} from '../lib/use-lineguard';
import {usePersonId} from '../lib/use-person';

// Next.js needs the page as the default export.
export default function Page() {
  const {state, view, events, selectedId, mock, offline, select, reload} = useLineguard();
  const personId = usePersonId();

  const context = useMemo<PageContextValue | null>(() => {
    if (state === null) {
      return null;
    }
    return {
      timezone: state.timezone,
      now: state.at,
      labels: state.labels,
      people: state.people,
      person: state.people.find((entry) => entry.person_id === personId) ?? null,
      reload,
    };
  }, [state, personId, reload]);

  if (state === null || context === null) {
    return (
      <main id="inhalt" className="mx-auto max-w-[1440px] px-4 py-10">
        <h1 className="text-lead font-semibold">Lineguard</h1>
        <p role="status" className="mt-2 text-ink-3">
          {offline === null ? 'Lade die Lage …' : 'Keine Verbindung zum Server.'}
        </p>
      </main>
    );
  }

  return (
    <PageProvider value={context}>
      <TopBar state={state} mock={mock} offline={offline} />
      <main id="inhalt" className="mx-auto max-w-[1440px] space-y-4 px-4 py-4">
        <h1 className="sr-only">Lineguard: Lage der {state.labels.line}</h1>
        <Coverage state={state} />
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(320px,400px)_minmax(0,1fr)]">
          <CaseList state={state} selectedId={selectedId} onSelect={select} />
          <CaseDetail view={view} selectedId={selectedId} live={state.mail_mode === 'LIVE'} />
        </div>
        <Strips problems={state.problems} events={events} />
      </main>
    </PageProvider>
  );
}
