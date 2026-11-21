'use client';

import {formatCount, formatDate, formatSigned} from '../lib/format';
import type {CaseView} from '../lib/types';
import {blockReasonWord} from '../lib/words';

import {usePage} from './page-context';
import {Card, Clock, cx} from './ui';

interface LineProps {
  label: string;
  note?: string | null;
  value: string;
  strong?: boolean;
  tone?: 'stop' | 'go';
  rule?: boolean;
}

function Line({label, note = null, value, strong = false, tone, rule = false}: LineProps) {
  return (
    <div className={cx('flex items-baseline justify-between gap-4 py-1', rule && 'border-t border-rule-ink')}>
      <dt className={cx('min-w-0', strong ? 'font-semibold text-ink' : 'text-ink-2')}>
        {label}
        {note !== null && <span className="block text-meta text-ink-3">{note}</span>}
      </dt>
      <dd
        className={cx(
          'num shrink-0',
          strong && 'font-semibold',
          tone === 'stop' && 'text-stop',
          tone === 'go' && 'text-go',
        )}
      >
        {value}
      </dd>
    </div>
  );
}

/** The path from the ERP stock to the gap, like a column of a ledger. */
export function Calculation({view}: {view: CaseView}) {
  const {timezone} = usePage();
  const {detail} = view;
  const hasNumbers = detail.erp_stock !== null || detail.usable !== null || detail.blocks.length > 0;
  if (!hasNumbers) {
    return null;
  }
  const used = detail.used_since_snapshot ?? 0;
  const inbound = detail.inbound_secured ?? 0;
  const gap =
    view.case.gap_qty ??
    (detail.usable !== null && detail.need !== null ? detail.usable + inbound - detail.need : null);
  const short = gap !== null && gap < 0;

  return (
    <Card title="Rechnung">
      <dl>
        <Line
          label="Bestand laut ERP"
          note={detail.stock_as_of === null ? null : `Stand ${formatDate(detail.stock_as_of, timezone)}`}
          value={formatCount(detail.erp_stock)}
        />
        {used > 0 && <Line label="Seit dem Stand verbraucht" value={formatSigned(-used)} />}
        {detail.blocks.map((block, index) => (
          <Line
            key={index}
            label={block.text ?? blockReasonWord(block.reason)}
            note={block.text === null ? null : `Abzug: ${blockReasonWord(block.reason)}`}
            value={block.qty === null ? '–' : formatSigned(-Math.abs(block.qty))}
            tone="stop"
          />
        ))}
        <Line label="Nutzbar" value={formatCount(detail.usable)} strong rule />
        {inbound > 0 && <Line label="Gesicherter Zulauf" value={formatSigned(inbound)} tone="go" />}
        <Line label="Bedarf" value={formatCount(detail.need)} />
        <Line
          label={short ? 'Lücke' : 'Reserve'}
          value={formatSigned(gap)}
          strong
          rule
          tone={short ? 'stop' : 'go'}
        />
      </dl>
      <p className="mt-2 rounded-ctl bg-well px-2 py-1 text-body">
        ERP: <span className="num">{formatCount(detail.erp_stock)}</span> · Lineguard rechnet mit:{' '}
        <span className="num font-semibold">{formatCount(detail.usable)}</span>
      </p>
      {detail.latest_useful_arrival !== null && (
        <p className="mt-2 text-meta text-ink-2">
          Späteste nützliche Ankunft: <Clock iso={detail.latest_useful_arrival} distance />
        </p>
      )}
    </Card>
  );
}
