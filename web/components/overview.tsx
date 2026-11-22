'use client';

import {formatClock, formatCount, formatMoney} from '../lib/format';
import type {LineguardState, LogEvent} from '../lib/types';
import {caseStateWord, eventTypeWord, roleWord} from '../lib/words';

import {usePage} from './page-context';

interface OverviewProps {
  state: LineguardState;
  events: LogEvent[];
  onOpenCase: (id: number) => void;
}

export function Overview({state, events, onOpenCase}: OverviewProps) {
  const {timezone, now} = usePage();
  const approval = state.approvals[0];
  const cases = state.cases_now.slice(0, 3);
  return (
    <div className="dashboard-overview">
      <header className="dashboard-heading">
        <p className="dashboard-overline">Production workspace</p>
        <h1>Production overview.</h1>
        <p>Here is what needs your attention.</p>
      </header>
      <div className="dashboard-grid">
        <section className="dashboard-summary" aria-label="Workspace summary">
          <div><span>Current cases</span><strong>{formatCount(state.counters.now_total)}</strong><small>Need attention now</small></div>
          <div><span>Later cases</span><strong>{formatCount(state.counters.later_total)}</strong><small>For a later date</small></div>
          <div><span>Awaiting approval</span><strong>{formatCount(state.approvals.length)}</strong><small>Decisions and corrections</small></div>
        </section>
        <section className="dashboard-panel dashboard-priorities" aria-labelledby="overview-cases">
          <div className="dashboard-section-head">
            <div><p className="dashboard-overline">Open work</p><h2 id="overview-cases">Cases to follow</h2></div>
            <a href="#cases">All cases ↗</a>
          </div>
          {cases.length === 0 ? <p className="dashboard-empty">No current cases.</p> : (
            <ul>
              {cases.map((entry) => (
                <li key={entry.id}>
                  <button className="dashboard-task" type="button" onClick={() => onOpenCase(entry.id)}>
                    <span className="dashboard-task-icon" aria-hidden="true">!</span>
                    <span className="dashboard-task-copy"><strong>{entry.title}</strong><small>{entry.component_id ?? 'Case'}</small></span>
                    <span className="dashboard-task-status">{caseStateWord(entry.state)}</span>
                    <span aria-hidden="true">↗</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="dashboard-decision" aria-labelledby="overview-decision">
          <div className="dashboard-decision-top"><span>● {approval ? 'Decision required' : 'Approvals'}</span><span>{formatCount(state.approvals.length)} waiting</span></div>
          {approval ? (
            <>
              <h2 id="overview-decision">{approval.title}</h2>
              <p>{approval.condition ?? approval.note ?? approval.summary ?? 'Review the proposed action before you decide.'}</p>
              <dl className="dashboard-decision-facts">
                <div><dt>Who approves</dt><dd>{approval.approver_name ?? (approval.needs_roles.map(roleWord).join(' or ') || 'Any person')}</dd></div>
                <div><dt>Decide by</dt><dd>{approval.deadline ? formatClock(approval.deadline, timezone, now) : 'Not set'}</dd></div>
                <div><dt>Cost</dt><dd>{approval.cost_unknown ? 'Unknown' : formatMoney(approval.cost_eur)}</dd></div>
              </dl>
              {approval.after_deadline && <p>The goods arrive after the deadline.</p>}
              <a className="dashboard-decision-link" href="#approvals">
                {approval.kind === 'unclosable_gap' ? 'Review shortage' : 'Review approval'} ↗
              </a>
            </>
          ) : (
            <>
              <h2 id="overview-decision">No approvals waiting.</h2>
              <p>New decisions and corrections will appear here.</p>
              <a className="dashboard-decision-link" href="#approvals">View approvals ↗</a>
            </>
          )}
        </section>
        <section className="dashboard-panel dashboard-recent" aria-labelledby="overview-activity">
          <div className="dashboard-section-head">
            <div><p className="dashboard-overline">Recent activity</p><h2 id="overview-activity">Latest updates</h2></div>
            <a href="#activity">View activity ↗</a>
          </div>
          {events.length === 0 ? <p className="dashboard-empty">No events yet.</p> : (
            <ul>{events.slice(0, 3).map((event) => (
              <li className="dashboard-event" key={event.id}>
                <span aria-hidden="true" />
                <div><strong>{eventTypeWord(event.type)}</strong><small>{formatClock(event.created_at, timezone, now)}</small></div>
              </li>
            ))}</ul>
          )}
        </section>
      </div>
    </div>
  );
}
