'use client';

import {formatCount} from '../lib/format';
import type {CaseView} from '../lib/types';
import {caseKindWord, caseStateTone, caseStateWord, impactWord, roleWord, ruleWord} from '../lib/words';

import {DecisionBlock} from './case-detail/decisions';
import {Folds} from './case-detail/folds';
import {DiscrepancyHero} from './case-detail/hero';
import {Waterfall} from './case-detail/waterfall';
import {usePage} from './page-context';
import {Clock, Tag} from './ui';

import './case-detail/panel.css';

function Header({view}: {view: CaseView}) {
  const {labels} = usePage();
  const entry = view.case;
  const impact = impactWord(entry.impact);
  const ids = [
    entry.component_id,
    entry.product_id === null ? null : `${labels.product} ${entry.product_id}`,
    entry.po_number === null ? null : `PO ${entry.po_number}`,
    entry.supplier_id === null ? null : `Supplier ${entry.supplier_id}`,
  ].filter((part) => part !== null);
  return (
    <header className="cd-head">
      <p className="cd-tags">
        <Tag>{caseKindWord(entry.kind)}</Tag>
        <Tag tone={caseStateTone(entry.state)}>{caseStateWord(entry.state)}</Tag>
        {entry.rule !== null && <span className="text-meta text-ink-3">Rule: {ruleWord(entry.rule)}</span>}
      </p>
      <h2 className="cd-title">{entry.title}</h2>
      {ids.length > 0 && <p className="lg-label">{ids.join(' · ')}</p>}
      <dl className="cd-facts">
        {entry.breaks_at !== null && (
          <div>
            <dt className="lg-label">{labels.line} stops</dt>
            <dd>
              <Clock iso={entry.breaks_at} distance />
            </dd>
          </div>
        )}
        {entry.act_by !== null && (
          <div>
            <dt className="lg-label">Act by</dt>
            <dd>
              <Clock iso={entry.act_by} distance />
            </dd>
          </div>
        )}
        {entry.due_at !== null && (
          <div>
            <dt className="lg-label">Demand date</dt>
            <dd>
              <Clock iso={entry.due_at} />
            </dd>
          </div>
        )}
        {entry.units_at_risk !== null && entry.units_at_risk > 0 && (
          <div>
            <dt className="lg-label">{labels.units} at risk</dt>
            <dd data-tone="risk">{formatCount(entry.units_at_risk)}</dd>
          </div>
        )}
        {entry.residual_qty !== null && entry.residual_qty > 0 && (
          <div>
            <dt className="lg-label">Short after the plan</dt>
            <dd data-tone="risk">{formatCount(entry.residual_qty)}</dd>
          </div>
        )}
        {impact !== null && (
          <div>
            <dt className="lg-label">Effect</dt>
            <dd>{impact.charAt(0).toUpperCase() + impact.slice(1)}</dd>
          </div>
        )}
        {entry.owner_role !== null && (
          <div>
            <dt className="lg-label">Owner</dt>
            <dd>{roleWord(entry.owner_role)}</dd>
          </div>
        )}
      </dl>
    </header>
  );
}

function LooseOptions({view}: {view: CaseView}) {
  if (view.decisions.length > 0 || view.options.length === 0) {
    return null;
  }
  return (
    <section className="cd-block" aria-labelledby="cd-loose">
      <h3 id="cd-loose" className="lg-label">
        Options that Lineguard checked
      </h3>
      <ul className="cd-list">
        {view.options.map((option) => (
          <li key={option.id}>
            <p className="cd-option-title">
              <span>{option.title}</span>
              {!option.feasible && <Tag tone="stop">Not possible</Tag>}
            </p>
            {option.infeasible_reason !== null && (
              <p className="cd-quiet">Reason: {option.infeasible_reason}</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

interface CaseDetailProps {
  view: CaseView | null;
  selectedId: number | null;
  live: boolean;
}

export function CaseDetail({view, selectedId, live}: CaseDetailProps) {
  if (selectedId === null) {
    return <p className="cd-empty">No case is open. Nothing stops the line today.</p>;
  }
  if (view === null || view.case.id !== selectedId) {
    return (
      <p role="status" className="cd-empty">
        Loading the case …
      </p>
    );
  }
  const openDecisions = view.decisions.filter((decision) => decision.status === 'open');
  const closedDecisions = view.decisions.filter((decision) => decision.status !== 'open');

  return (
    <article key={view.case.id} aria-label={`Case: ${view.case.title}`} className="cd">
      <Header view={view} />
      <DiscrepancyHero view={view} />
      {openDecisions.map((decision) => (
        <DecisionBlock key={decision.id} decision={decision} view={view} live={live} />
      ))}
      <Waterfall view={view} />
      {closedDecisions.map((decision) => (
        <DecisionBlock key={decision.id} decision={decision} view={view} live={live} />
      ))}
      <LooseOptions view={view} />
      <Folds view={view} live={live} />
    </article>
  );
}
