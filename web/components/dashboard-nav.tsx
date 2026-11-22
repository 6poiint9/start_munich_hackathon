'use client';

import type {LineguardState} from '../lib/types';

export type DashboardView = 'overview' | 'cases' | 'approvals' | 'activity';

const items: {id: DashboardView; label: string; icon: string}[] = [
  {id: 'overview', label: 'Overview', icon: '◫'},
  {id: 'cases', label: 'Cases', icon: '◈'},
  {id: 'approvals', label: 'Approvals', icon: '◇'},
  {id: 'activity', label: 'Activity', icon: '↗'},
];

export function DashboardNav({state, current}: {state: LineguardState; current: DashboardView}) {
  const counts: Partial<Record<DashboardView, number>> = {
    cases: state.counters.now_total + state.counters.later_total,
    approvals: state.approvals.length,
  };
  return (
    <aside className="dashboard-sidebar">
      <a className="dashboard-brand" href="#overview" aria-label="Lineguard overview">
        <span className="dashboard-mark" aria-hidden="true"><i /><i /><i /></span>
        <strong>lineguard</strong>
      </a>
      <div className="dashboard-workspace">
        <span className="dashboard-workspace-icon" aria-hidden="true">
          {(state.customer ?? 'L').slice(0, 1).toUpperCase()}
        </span>
        <span><strong>{state.customer ?? 'Lineguard'}</strong><small>Workspace</small></span>
      </div>
      <p className="dashboard-nav-label">Workspace</p>
      <nav aria-label="Main navigation">
        {items.map((item) => (
          <a
            href={`#${item.id}`}
            key={item.id}
            className="dashboard-nav-item"
            aria-current={current === item.id ? 'page' : undefined}
            aria-label={item.label}
            title={item.label}
          >
            <span className="dashboard-nav-icon" aria-hidden="true">{item.icon}</span>
            <span className="dashboard-nav-text">{item.label}</span>
            {counts[item.id] !== undefined && (
              <span className="dashboard-nav-count" aria-label={`${counts[item.id]} ${item.label.toLowerCase()}`}>
                {counts[item.id]}
              </span>
            )}
          </a>
        ))}
      </nav>
      <div className="dashboard-sidebar-foot">
        <span aria-hidden="true" />
        <p>Lineguard<small>Production workspace</small></p>
      </div>
    </aside>
  );
}
