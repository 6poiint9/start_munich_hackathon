'use client';

import {useEffect, useMemo, useRef} from 'react';

import {Approvals} from '../components/approvals';
import {CaseDetail} from '../components/case-detail';
import {CaseList} from '../components/case-list';
import {Coverage} from '../components/coverage';
import {PageProvider} from '../components/page-context';
import type {PageContextValue} from '../components/page-context';
import {TopBar} from '../components/top-bar';
import {useLineguard} from '../lib/use-lineguard';
import {usePersonId} from '../lib/use-person';

// Next.js needs the page as the default export.
export default function Page() {
  const {state, view, events, selectedId, mock, offline, select, reload} = useLineguard();
  const personId = usePersonId();
  const detailRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    detailRef.current?.scrollTo({top: 0});
  }, [selectedId]);

  if (state === null || context === null) {
    return (
      <main id="inhalt" className="lg-loading">
        <h1>Lineguard</h1>
        <p role="status">
          {offline === null ? 'Lade die Lage …' : 'Keine Verbindung zum Server.'}
        </p>
      </main>
    );
  }

  return (
    <PageProvider value={context}>
      <div className="lg-shell">
        <TopBar state={state} mock={mock} offline={offline} />
        <main id="inhalt" className="lg-main">
          <h1 className="sr-only">Lineguard: Lage der {state.labels.line}</h1>
          <Coverage state={state} />
          <Approvals state={state} selectedId={selectedId} onSelect={select} />
          <div className="lg-board">
            <CaseList
              state={state}
              events={events}
              selectedId={selectedId}
              onSelect={select}
            />
            <div className="lg-detail" ref={detailRef}>
              <CaseDetail
                view={view}
                selectedId={selectedId}
                live={state.mail_mode === 'LIVE'}
              />
            </div>
          </div>
        </main>
      </div>
    </PageProvider>
  );
}
