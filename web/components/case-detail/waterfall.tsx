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
      label: 'Stock in the ERP',
      note: detail.stock_as_of === null ? null : `as of ${formatDate(detail.stock_as_of, timezone)}`,
      value: detail.erp_stock,
      signed: false,
      tone: 'plain',
      result: false,
    },
  ];
  if (used > 0) {
    steps.push({
      key: 'used',
      label: 'Used since that date',
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
      note: block.text === null ? null : `Deducted: ${blockReasonWord(block.reason).toLowerCase()}`,
      value: block.qty === null ? null : -Math.abs(block.qty),
      signed: true,
      tone: 'risk',
      result: false,
    });
  });
  steps.push({
    key: 'usable',
    label: 'Usable stock',
    note: null,
    value: detail.usable,
    signed: false,
    tone: 'plain',
    result: true,
  });
  if (inbound > 0) {
    steps.push({
      key: 'inbound',
      label: 'Secured deliveries',
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
      label: 'Demand',
      note: null,
      value: detail.need,
      signed: false,
      tone: 'plain',
      result: false,
    },
    {
      key: 'gap',
      label: short ? 'Shortage' : 'Reserve',
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
  const short = steps.at(-1)?.tone === 'risk';
  const max = Math.max(1, ...steps.map((step) => Math.abs(step.value ?? 0)));
  return (
    <section className="cd-block" aria-labelledby="cd-water">
      <h3 id="cd-water" className="lg-label">
        How Lineguard calculates the {short ? 'shortage' : 'reserve'}
      </h3>
      <p className="cd-lead">
        The ERP shows {formatCount(detail.erp_stock)}. Lineguard counts {formatCount(detail.usable)}{' '}
        as usable.
      </p>
      <div className="cd-steps">
        {steps.map((step) => {
          const width = step.value === null ? 0 : (Math.abs(step.value) / max) * 100;
          const text = step.signed ? formatSigned(step.value) : formatCount(step.value);
          return (
            <div
              key={step.key}
              className="cd-step"
              data-tone={step.tone === 'plain' ? undefined : step.tone}
              data-result={step.result}
            >
              <div className="cd-step-name">
                {step.label}
                {step.note !== null && <small>{step.note}</small>}
              </div>
              <div className="cd-track" aria-hidden="true">
                <i style={{width: `${width}%`}} />
              </div>
              <b>{text}</b>
            </div>
          );
        })}
      </div>
      {detail.latest_useful_arrival !== null && (
        <p className="cd-quiet">
          Latest useful arrival: <Clock iso={detail.latest_useful_arrival} distance />
        </p>
      )}
    </section>
  );
}
