'use client';

import {useCallback, useEffect, useMemo, useRef, useState} from 'react';

import {Approvals} from '../components/approvals';
import {CaseFlow} from '../components/case-flow';
import {CaseList} from '../components/case-list';
import {Coverage} from '../components/coverage';
import {DashboardNav} from '../components/dashboard-nav';
import type {DashboardView} from '../components/dashboard-nav';
import {Overview} from '../components/overview';
import {PageProvider} from '../components/page-context';
import type {PageContextValue} from '../components/page-context';
import {Strips} from '../components/strips';
import {TopBar} from '../components/top-bar';
import {useLineguard} from '../lib/use-lineguard';
import {usePersonId} from '../lib/use-person';

// Next.js needs the page as the default export.
export default function Page() {
  const {state, events, selectedId, mock, offline, select, reload} = useLineguard();
  const personId = usePersonId();
  const [current, setCurrent] = useState<DashboardView>('overview');
  const detailRef = useRef<HTMLDivElement>(null);
  const scrollToCase = useRef(false);

  useEffect(() => {
    const update = () => {
      const hash = window.location.hash.slice(1);
      setCurrent(hash === 'cases' || hash === 'approvals' || hash === 'activity' ? hash : 'overview');
    };
    update();
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);

  useEffect(() => {
    if (current === 'cases' && scrollToCase.current && detailRef.current !== null) {
      scrollToCase.current = false;
      if (detailRef.current.getBoundingClientRect().top > window.innerHeight * 0.6) {
        detailRef.current.scrollIntoView({block: 'start'});
      }
    }
  }, [current, selectedId]);

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

  const openCase = useCallback(
    (id: number) => {
      select(id);
      scrollToCase.current = true;
      window.location.hash = 'cases';
    },
    [select],
  );

  if (state === null || context === null) {
    return (
      <main id="content" className="lg-loading">
        <h1>Lineguard</h1>
        <p role="status">
          {offline === null ? 'Loading the current state …' : 'No connection to the server.'}
        </p>
      </main>
    );
  }

  return (
    <PageProvider value={context}>
      <div className="dashboard-shell">
        <DashboardNav state={state} current={current} />
        <div className="dashboard-main">
          <TopBar state={state} mock={mock} offline={offline} current={current.charAt(0).toUpperCase() + current.slice(1)} />
          <main id="content" className="lg-main">
            {current === 'overview' && (
              <>
                <Overview state={state} events={events} onOpenCase={openCase} />
                <Coverage state={state} />
              </>
            )}
            {current === 'approvals' && (
              <div className="dashboard-page">
                <header className="dashboard-heading"><p className="dashboard-overline">Workspace</p><h1>Approvals</h1><p>Review the action and its consequences before you decide.</p></header>
                <Approvals state={state} selectedId={selectedId} onSelect={openCase} />
              </div>
            )}
            {current === 'cases' && (
              <div className="dashboard-page">
                <header className="dashboard-heading"><p className="dashboard-overline">Workspace</p><h1>Cases</h1><p>Understand the risk, its source, and the next step.</p></header>
                <section className="lg-section lg-wrap" aria-labelledby="cases-title">
                  <header className="lg-section-head">
                    <h2 id="cases-title">Open cases</h2>
                  </header>
                  <div className="lg-board">
                    <CaseList state={state} events={events} selectedId={selectedId} onSelect={select} />
                    <div className="lg-detail" ref={detailRef}>
                      <CaseFlow state={state} caseId={selectedId} />
                    </div>
                  </div>
                </section>
              </div>
            )}
            {current === 'activity' && (
              <div className="dashboard-page">
                <header className="dashboard-heading"><p className="dashboard-overline">Workspace</p><h1>Activity</h1><p>Follow the events and problems reported by Lineguard.</p></header>
                <div className="dashboard-panel dashboard-activity lg-log">
                  <Strips problems={state.problems} events={events} />
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
    </PageProvider>
  );
}
