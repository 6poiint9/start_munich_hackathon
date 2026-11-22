'use client';

import {useEffect, useMemo, useRef, useState} from 'react';

import {ApprovalView} from '../components/approvals';
import {CaseDetail} from '../components/case-detail';
import {CaseList} from '../components/case-list';
import type {BoardTab} from '../components/case-list';
import {Coverage} from '../components/coverage';
import {PageProvider} from '../components/page-context';
import type {PageContextValue} from '../components/page-context';
import {TopBar} from '../components/top-bar';
import type {CaseView, LineguardState, LogEvent} from '../lib/types';
import {useLineguard} from '../lib/use-lineguard';
import {usePersonId} from '../lib/use-person';

interface BoardProps {
  state: LineguardState;
  events: LogEvent[];
  view: CaseView | null;
  selectedId: number | null;
  onSelect: (id: number) => void;
  live: boolean;
}

function Board({state, events, view, selectedId, onSelect, live}: BoardProps) {
  const detailRef = useRef<HTMLDivElement>(null);
  const [tab, setTab] = useState<BoardTab>('now');
  const [approvalId, setApprovalId] = useState<string | null>(null);
  const approval =
    state.approvals.find((item) => item.id === approvalId) ?? state.approvals[0] ?? null;

  useEffect(() => {
    detailRef.current?.scrollTo({top: 0});
  }, [selectedId, tab, approval?.id]);

  return (
    <div className="lg-board">
      <CaseList
        state={state}
        events={events}
        selectedId={selectedId}
        onSelect={onSelect}
        tab={tab}
        onTab={setTab}
        approvalId={approval?.id ?? null}
        onApproval={(id) => {
          setApprovalId(id);
          setTab('approvals');
        }}
      />
      <div className="lg-detail" ref={detailRef}>
        {tab === 'approvals' ? (
          approval === null ? (
            <p className="lg-case lg-empty">Keine Freigabe offen.</p>
          ) : (
            <ApprovalView
              item={approval}
              onOpenCase={(caseId) => {
                onSelect(caseId);
                setTab('now');
              }}
            />
          )
        ) : (
          <CaseDetail view={view} selectedId={selectedId} live={live} />
        )}
      </div>
    </div>
  );
}

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
          <Board
            state={state}
            events={events}
            view={view}
            selectedId={selectedId}
            onSelect={select}
            live={state.mail_mode === 'LIVE'}
          />
        </main>
      </div>
    </PageProvider>
  );
}
