'use client';

import {formatCount, formatDate, formatSigned} from '../../lib/format';
import type {CaseView} from '../../lib/types';
import {blockReasonWord} from '../../lib/words';

import {usePage} from '../page-context';
import {Clock} from '../ui';

interface Step {
  key: string;
  label: string;
  note: string | null;
  value: number | null;
  signed: boolean;
  tone: 'plain' | 'risk' | 'ok';
  result: boolean;
}

function stepsOf(view: CaseView, timezone: string): Step[] {
  const {detail} = view;
  const used = detail.used_since_snapshot ?? 0;
  const inbound = detail.inbound_secured ?? 0;
  const gap =
    view.case.gap_qty ??
    (detail.usable !== null && detail.need !== null ? detail.usable + inbound - detail.need : null);
  const short = gap !== null && gap < 0;
  const steps: Step[] = [
    {
      key: 'erp',
      label: 'Bestand laut ERP',
      note: detail.stock_as_of === null ? null : `Stand ${formatDate(detail.stock_as_of, timezone)}`,
      value: detail.erp_stock,
      signed: false,
      tone: 'plain',
      result: false,
    },
  ];
  if (used > 0) {
    steps.push({
      key: 'used',
      label: 'Seit dem Stand verbraucht',
      note: null,
      value: -used,
      signed: true,
      tone: 'risk',
      result: false,
    });
  }
  detail.blocks.forEach((block, index) => {
    steps.push({
      key: `block-${index}`,
      label: block.text ?? blockReasonWord(block.reason),
      note: block.text === null ? null : `Abzug: ${blockReasonWord(block.reason)}`,
      value: block.qty === null ? null : -Math.abs(block.qty),
      signed: true,
      tone: 'risk',
      result: false,
    });
  });
  steps.push({
    key: 'usable',
    label: 'Nutzbar',
    note: null,
    value: detail.usable,
    signed: false,
    tone: 'plain',
    result: true,
  });
  if (inbound > 0) {
    steps.push({
      key: 'inbound',
      label: 'Gesicherter Zulauf',
      note: null,
      value: inbound,
      signed: true,
      tone: 'ok',
      result: false,
    });
  }
  steps.push(
    {
      key: 'need',
      label: 'Bedarf',
      note: null,
      value: detail.need,
      signed: false,
      tone: 'plain',
      result: false,
    },
    {
      key: 'gap',
      label: short ? 'Lücke' : 'Reserve',
      note: null,
      value: gap,
      signed: true,
      tone: short ? 'risk' : 'ok',
      result: true,
    },
  );
  return steps;
}

/** The path from the ERP stock down to the gap. */
export function Waterfall({view}: {view: CaseView}) {
  const {timezone} = usePage();
  const {detail} = view;
  const hasNumbers = detail.erp_stock !== null || detail.usable !== null || detail.blocks.length > 0;
  if (!hasNumbers) {
    return null;
  }
  const steps = stepsOf(view, timezone);
  const max = Math.max(1, ...steps.map((step) => Math.abs(step.value ?? 0)));
  return (
    <section className="lg-water lg-on-card" aria-label="Rechnung">
      <h3>Rechnung</h3>
      <div>
        {steps.map((step) => {
          const width = step.value === null ? 0 : (Math.abs(step.value) / max) * 100;
          const text = step.signed ? formatSigned(step.value) : formatCount(step.value);
          return (
            <div
              key={step.key}
              className={
                step.tone === 'plain'
                  ? step.result
                    ? 'lg-step is-result'
                    : 'lg-step'
                  : step.result
                    ? `lg-step is-result is-${step.tone}`
                    : `lg-step is-${step.tone}`
              }
            >
              <i className="lg-rail" aria-hidden="true" />
              <div className="lg-step-name">
                {step.label}
                {step.note !== null && <small>{step.note}</small>}
                <div className="lg-track" aria-hidden="true">
                  <i style={{width: `${width}%`}} />
                </div>
              </div>
              <b>{text}</b>
            </div>
          );
        })}
      </div>
      <p className="lg-balance">
        ERP: {formatCount(detail.erp_stock)} · Lineguard rechnet mit: {formatCount(detail.usable)}
      </p>
      {detail.latest_useful_arrival !== null && (
        <p className="lg-arrival">
          Späteste nützliche Ankunft: <Clock iso={detail.latest_useful_arrival} distance />
        </p>
      )}
    </section>
  );
}
