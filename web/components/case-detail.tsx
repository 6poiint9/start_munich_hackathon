'use client';

import {formatCount} from '../lib/format';
import type {CaseView} from '../lib/types';
import {caseKindWord, caseStateTone, caseStateWord, ruleWord} from '../lib/words';

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
  const ids = [
    entry.component_id,
    entry.product_id === null ? null : `${labels.product} ${entry.product_id}`,
    entry.po_number === null ? null : `Bestellung ${entry.po_number}`,
    entry.supplier_id === null ? null : `Lieferant ${entry.supplier_id}`,
  ].filter((part) => part !== null);
  return (
    <header className="space-y-1">
      <div className="lg-kicker">
        <Tag>{caseKindWord(entry.kind)}</Tag>
        <Tag tone={caseStateTone(entry.state)}>{caseStateWord(entry.state)}</Tag>
        {entry.rule !== null && <span>Regel: {ruleWord(entry.rule)}</span>}
      </div>
      <h2 className="lg-title">{entry.title}</h2>
      <p className="lg-meta">
        {ids.length > 0 && <span className="lg-id">{ids.join(' · ')}</span>}
        {entry.breaks_at !== null && (
          <span>
            {labels.line} steht ab <Clock iso={entry.breaks_at} distance />
          </span>
        )}
        {entry.act_by !== null && (
          <span>
            handeln bis <Clock iso={entry.act_by} distance />
          </span>
        )}
        {entry.units_at_risk !== null && entry.units_at_risk > 0 && (
          <span>
            <span className="text-stop">{formatCount(entry.units_at_risk)}</span> {labels.units} in Gefahr
          </span>
        )}
        {entry.residual_qty !== null && entry.residual_qty > 0 && (
          <span>
            Rest nach Plan: <span className="text-stop">{formatCount(entry.residual_qty)}</span>
          </span>
        )}
      </p>
    </header>
  );
}

function LooseOptions({view}: {view: CaseView}) {
  const listed = new Set(view.decisions.flatMap((decision) => decision.options));
  const loose = view.decisions.length === 0 ? view.options : view.options.filter((option) => !listed.has(option.id));
  if (view.decisions.length > 0 || loose.length === 0) {
    return null;
  }
  return (
    <section className="lg-loose lg-on-card">
      <h3>Geprüfte Optionen</h3>
      <ul>
        {loose.map((option) => (
          <li key={option.id}>
            <p className="lg-option-title">
              <span>{option.title}</span>
              {!option.feasible && <Tag tone="stop">nicht machbar</Tag>}
            </p>
            {option.infeasible_reason !== null && <p className="lg-reason">Grund: {option.infeasible_reason}</p>}
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
    return (
      <p className="lg-panel lg-empty">Kein Fall offen. Heute stoppt nichts die Linie.</p>
    );
  }
  if (view === null || view.case.id !== selectedId) {
    return (
      <p role="status" className="lg-panel lg-empty">
        Lade Fall …
      </p>
    );
  }
  const openDecisions = view.decisions.filter((decision) => decision.status === 'open');
  const closedDecisions = view.decisions.filter((decision) => decision.status !== 'open');

  return (
    <article aria-label={`Fall: ${view.case.title}`} className="lg-panel">
      <Header view={view} />
      <DiscrepancyHero view={view} />
      {openDecisions.map((decision) => (
        <DecisionBlock key={decision.id} decision={decision} view={view} />
      ))}
      <Waterfall view={view} />
      {closedDecisions.map((decision) => (
        <DecisionBlock key={decision.id} decision={decision} view={view} />
      ))}
      <LooseOptions view={view} />
      <Folds view={view} live={live} />
    </article>
  );
}
