'use client';

import {
  formatClock,
  formatCount,
  formatDistance,
  formatDuration,
  formatPercent,
  formatPoints,
  isPast,
  parseInstant,
} from '../lib/format';
import type {CaseSummary, LineguardState, Product} from '../lib/types';

import {usePage} from './page-context';
import {Clock} from './ui';

const UNIT_STATES = [
  {key: 'secured', word: 'secured', fill: 'fill-secured'},
  {key: 'planned', word: 'in progress', fill: 'fill-planned'},
  {key: 'open', word: 'waiting for a decision', fill: 'fill-open'},
  {key: 'unclosable', word: 'cannot be closed', fill: 'fill-unclosable'},
] as const;

/** Under this distance the two numbers count as equal. */
const SAME_RATIO = 0.0005;

type Signal = 'ok' | 'warn' | 'risk';

const SIGNAL_WORD: Record<Signal, string> = {
  ok: 'Covered',
  warn: 'Needs attention',
  risk: 'At risk',
};

function share(ratio: number): string {
  return `${Math.min(Math.max(ratio, 0), 1) * 100}%`;
}

function relatedCases(product: Product, cases: CaseSummary[]): CaseSummary[] {
  return cases.filter((entry) => {
    if (entry.product_id !== null && entry.product_id === product.product_id) {
      return true;
    }
    return (
      product.limiting_component !== null &&
      entry.component_id === product.limiting_component
    );
  });
}

function unitsAtRisk(product: Product, cases: CaseSummary[]): number {
  return relatedCases(product, cases).reduce(
    (highest, entry) => Math.max(highest, entry.units_at_risk ?? 0),
    0,
  );
}

function soonest(times: string[]): string | null {
  let best: string | null = null;
  let bestMs = Number.POSITIVE_INFINITY;
  for (const time of times) {
    const date = parseInstant(time);
    if (date === null) {
      continue;
    }
    if (date.getTime() < bestMs) {
      bestMs = date.getTime();
      best = time;
    }
  }
  return best;
}

function lineStopIso(product: Product, state: LineguardState): string | null {
  const times = relatedCases(product, [...state.cases_now, ...state.cases_later])
    .map((entry) => entry.breaks_at)
    .filter((value): value is string => value !== null);
  const first = state.first_stop;
  if (
    first !== null &&
    first.breaks_at !== null &&
    first.component_id !== null &&
    first.component_id === product.limiting_component
  ) {
    times.push(first.breaks_at);
  }
  return soonest(times);
}

function signalOf(product: Product, atRisk: number, apart: boolean): Signal {
  if (atRisk > 0 || product.units.unclosable > 0) {
    return 'risk';
  }
  if (apart || product.units.open > 0) {
    return 'warn';
  }
  return 'ok';
}

interface StopLead {
  value: string;
  note: string | null;
  past: boolean;
}

function stopLead(iso: string | null, now: string | null, timezone: string): StopLead | null {
  const stop = parseInstant(iso);
  const reference = parseInstant(now);
  if (iso === null || stop === null || reference === null) {
    return null;
  }
  const past = isPast(iso, now);
  const length = formatDuration(stop.getTime() - reference.getTime());
  return {
    value: past ? `${length} ago` : `in ${length}`,
    note: formatClock(iso, timezone, now),
    past,
  };
}

function capital(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function ProductBlock({product, state}: {product: Product; state: LineguardState}) {
  const {labels, now, timezone} = usePage();
  const system = product.coverage_system;
  const secured = product.coverage_secured;
  const distance = system !== null && secured !== null ? system - secured : null;
  const apart = distance !== null && distance > SAME_RATIO;
  const cases = [...state.cases_now, ...state.cases_later];
  const atRisk = unitsAtRisk(product, cases);
  const signal = signalOf(product, atRisk, apart);
  const stop = stopLead(lineStopIso(product, state), now, timezone);
  const total = UNIT_STATES.reduce((sum, entry) => sum + product.units[entry.key], 0);

  return (
    <article className="lg-product">
      <header className="lg-product-head">
        <div>
          <h3>{product.description ?? product.product_id}</h3>
          <p className="lg-label lg-product-id">
            {labels.product} {product.product_id}
          </p>
        </div>
        <span className="lg-signal" data-state={signal}>
          {SIGNAL_WORD[signal]}
        </span>
      </header>

      <div className="lg-product-lead">
        <p className="lg-big">{formatPercent(secured)}</p>
        <p className="lg-big-note">
          of the demand until {labels.deadline} is secured by documents.{' '}
          {apart && distance !== null ? (
            <>
              The ERP says <span className="lg-struck">{formatPercent(system)}</span>.{' '}
              <span className="lg-hot">{formatPoints(distance)} points have no document.</span>
            </>
          ) : distance === null ? (
            'The ERP gives no figure to compare.'
          ) : (
            'The ERP says the same.'
          )}
        </p>
      </div>

      {system !== null && secured !== null && (
        <div
          className="lg-bar"
          role="img"
          aria-label={`ERP says ${formatPercent(system)}, secured by documents ${formatPercent(secured)}`}
        >
          <div className="fill-secured" style={{width: share(secured)}} />
          {apart && <div className="fill-gap" style={{width: share(system - secured)}} />}
        </div>
      )}

      <dl className="lg-facts">
        <div>
          <dt className="lg-label">{capital(labels.units)} at risk</dt>
          <dd data-tone={atRisk > 0 ? 'risk' : undefined}>{formatCount(atRisk)}</dd>
        </div>
        <div>
          <dt className="lg-label">{capital(labels.line)} stops</dt>
          {stop === null ? (
            <dd>No stop in sight</dd>
          ) : (
            <dd data-tone={stop.past ? 'risk' : undefined}>
              {stop.value}
              <small>{stop.note}</small>
            </dd>
          )}
        </div>
        <div>
          <dt className="lg-label">Open until {labels.deadline}</dt>
          <dd>
            {formatCount(product.still_to_pack)} <small>{labels.units}</small>
          </dd>
        </div>
        <div>
          <dt className="lg-label">Line rate</dt>
          <dd>
            {product.rate_per_hour === null ? (
              'Unknown'
            ) : (
              <>
                {formatCount(product.rate_per_hour)} <small>{labels.units} per hour</small>
              </>
            )}
          </dd>
        </div>
        <div>
          <dt className="lg-label">Run time left</dt>
          <dd>{product.hours_left === null ? '–' : `${formatCount(product.hours_left)} h`}</dd>
        </div>
        <div>
          <dt className="lg-label">Bottleneck</dt>
          <dd className="lg-id">{product.limiting_component ?? '–'}</dd>
        </div>
      </dl>

      {total > 0 && (
        <>
          <div className="lg-bar" aria-hidden="true">
            {UNIT_STATES.map((entry) => (
              <div
                key={entry.key}
                className={entry.fill}
                style={{width: share(product.units[entry.key] / total)}}
              />
            ))}
          </div>
          <ul className="lg-legend">
            {UNIT_STATES.map((entry) => (
              <li
                key={entry.key}
                className={product.units[entry.key] === 0 ? 'lg-legend-zero' : undefined}
              >
                <span className={`lg-swatch ${entry.fill}`} aria-hidden="true" />
                <span className="num">{formatCount(product.units[entry.key])}</span> {entry.word}
              </li>
            ))}
          </ul>
        </>
      )}
    </article>
  );
}

export function Coverage({state}: {state: LineguardState}) {
  const {labels, now, timezone} = usePage();
  const stop = state.first_stop;
  const stopAt = stop === null ? null : stop.breaks_at;
  const stopped = isPast(stopAt, now);
  return (
    <section className="lg-status lg-wrap" aria-labelledby="coverage">
      <p className="lg-label">Coverage until {labels.deadline}</p>
      <h2 id="coverage" className="lg-headline">
        {stop === null || stopAt === null
          ? `No stop of the ${labels.line} is in sight.`
          : stopped
            ? `The ${labels.line} stopped ${formatClock(stopAt, timezone, now)}.`
            : `The ${labels.line} stops ${formatClock(stopAt, timezone, now)}.`}
      </h2>
      <p className="lg-headline-sub">
        {stop !== null && stopAt !== null && (
          <>
            {stopped ? 'That was ' : 'That is '}
            {formatDistance(stopAt, now)}.{' '}
            {stop.component_id !== null && (
              <>
                <span className="lg-id">{stop.component_id}</span>
                {stop.description !== null && ` ${stop.description}`} runs out first.{' '}
              </>
            )}
          </>
        )}
        {state.next_due === null ? (
          'No demand date is open.'
        ) : (
          <>
            The next demand date is <Clock iso={state.next_due} distance />.
          </>
        )}
      </p>
      {state.products.length === 0 ? (
        <p className="lg-empty-note">No {labels.product} has open demand.</p>
      ) : (
        <div className="lg-products">
          {state.products.map((product) => (
            <ProductBlock key={product.product_id} product={product} state={state} />
          ))}
        </div>
      )}
    </section>
  );
}
