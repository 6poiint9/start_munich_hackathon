'use client';

import {formatCount} from '../lib/format';
import type {CaseView} from '../lib/types';
import {actionStatusWord, actionTypeWord, caseKindWord, caseStateTone, caseStateWord, ruleWord} from '../lib/words';

import {Calculation} from './calculation';
import {CorrectionCard} from './correction-card';
import {DecisionCard} from './decision-card';
import {EvidenceList} from './evidence';
import {Mails} from './mails';
import {usePage} from './page-context';
import {Card, Clock, Tag} from './ui';

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
      <div className="flex flex-wrap items-center gap-2">
        <Tag>{caseKindWord(entry.kind)}</Tag>
        <Tag tone={caseStateTone(entry.state)}>{caseStateWord(entry.state)}</Tag>
        {entry.rule !== null && <span className="text-meta text-ink-3">Regel: {ruleWord(entry.rule)}</span>}
      </div>
      <h2 className="text-title font-semibold">{entry.title}</h2>
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-meta text-ink-2">
        {ids.length > 0 && <span className="num">{ids.join(' · ')}</span>}
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
            <span className="num font-medium text-stop">{formatCount(entry.units_at_risk)}</span> {labels.units} in
            Gefahr
          </span>
        )}
        {entry.residual_qty !== null && entry.residual_qty > 0 && (
          <span>
            Rest nach Plan: <span className="num font-medium text-stop">{formatCount(entry.residual_qty)}</span>
          </span>
        )}
      </p>
    </header>
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
      <p className="rounded-sheet border border-rule bg-sheet px-4 py-6 text-ink-3">
        Kein Fall offen. Heute stoppt nichts die Linie.
      </p>
    );
  }
  if (view === null || view.case.id !== selectedId) {
    return (
      <p role="status" className="rounded-sheet border border-rule bg-sheet px-4 py-6 text-ink-3">
        Lade Fall …
      </p>
    );
  }
  const openDecisions = view.decisions.filter((decision) => decision.status === 'open');
  const closedDecisions = view.decisions.filter((decision) => decision.status !== 'open');
  const listedOptions = new Set(view.decisions.flatMap((decision) => decision.options));
  const looseOptions = view.decisions.length === 0 ? view.options : view.options.filter((option) => !listedOptions.has(option.id));

  return (
    <article aria-label={`Fall: ${view.case.title}`} className="space-y-3">
      <Header view={view} />
      {openDecisions.map((decision) => (
        <DecisionCard key={decision.id} decision={decision} view={view} />
      ))}
      {view.finding !== null && <CorrectionCard finding={view.finding} corrections={view.corrections} />}
      <Calculation view={view} />
      {closedDecisions.map((decision) => (
        <DecisionCard key={decision.id} decision={decision} view={view} />
      ))}
      {view.decisions.length === 0 && looseOptions.length > 0 && (
        <Card title="Geprüfte Optionen">
          <ul className="space-y-2">
            {looseOptions.map((option) => (
              <li key={option.id}>
                <p className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{option.title}</span>
                  {!option.feasible && <Tag tone="stop">nicht machbar</Tag>}
                </p>
                {option.infeasible_reason !== null && (
                  <p className="text-meta text-ink-3">Grund: {option.infeasible_reason}</p>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Mails view={view} live={live} />
      {view.actions.length > 0 && (
        <Card title="Aktionen">
          <ul className="space-y-1">
            {view.actions.map((action) => (
              <li key={action.id} className="flex flex-wrap items-center gap-2">
                <span>{actionTypeWord(action.type ?? action.kind)}</span>
                {action.target !== null && <span className="num text-ink-2">{action.target}</span>}
                <Tag>{actionStatusWord(action.status)}</Tag>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <EvidenceList evidence={view.evidence} />
    </article>
  );
}
