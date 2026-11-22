'use client';

import {formatCount, formatDistance, formatPercent, formatPoints, parseInstant} from '../lib/format';
import type {CaseSummary, LineguardState, Product} from '../lib/types';

import {usePage} from './page-context';
import {Clock} from './ui';

const UNIT_STATES = [
  {key: 'secured', word: 'gesichert', fill: 'fill-secured'},
  {key: 'planned', word: 'in Arbeit', fill: 'fill-planned'},
  {key: 'open', word: 'wartet auf Entscheidung', fill: 'fill-open'},
  {key: 'unclosable', word: 'nicht schließbar', fill: 'fill-unclosable'},
] as const;

/** Under this distance the two numbers count as equal. */
const SAME_RATIO = 0.0005;

type Signal = 'ok' | 'warn' | 'risk';

const SIGNAL_WORD: Record<Signal, string> = {
  ok: 'Gedeckt',
  warn: 'Achtung',
  risk: 'Risiko',
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
  label: string;
  time: boolean;
}

function stopLead(iso: string | null, now: string | null, hoursLeft: number | null): StopLead {
  const phrase = iso === null ? null : formatDistance(iso, now);
  if (phrase !== null) {
    const overdue = phrase.startsWith('seit ');
    return {
      value: overdue ? phrase : phrase.slice(3),
      label: overdue ? 'Linie steht' : 'bis die Linie steht',
      time: true,
    };
  }
  if (hoursLeft !== null) {
    return {value: `${formatCount(hoursLeft)} h`, label: 'Restzeit', time: true};
  }
  return {value: '–', label: 'bis die Linie steht', time: false};
}

function ProductBlock({product, state}: {product: Product; state: LineguardState}) {
  const {labels, now} = usePage();
  const system = product.coverage_system;
  const secured = product.coverage_secured;
  const distance = system !== null && secured !== null ? system - secured : null;
  const apart = distance !== null && distance > SAME_RATIO;
  const cases = [...state.cases_now, ...state.cases_later];
  const atRisk = unitsAtRisk(product, cases);
  const signal = signalOf(product, atRisk, apart);
  const stop = stopLead(lineStopIso(product, state), now, product.hours_left);
  const total = UNIT_STATES.reduce((sum, entry) => sum + product.units[entry.key], 0);
  const rest =
    product.hours_left !== null && stop.label !== 'Restzeit'
      ? `${formatCount(product.hours_left)} h`
      : null;

  return (
    <article className="lg-kpi" data-state={signal}>
      <header className="lg-kpi-head">
        <div>
          <h3>{product.description ?? product.product_id}</h3>
          <p className="lg-kpi-id">
            {labels.product} <span className="lg-id">{product.product_id}</span>
          </p>
        </div>
        <span className={`lg-chip lg-chip-${signal}`}>{SIGNAL_WORD[signal]}</span>
      </header>

      <div className="lg-figures">
        <div>
          <p className="lg-hero">{formatPercent(secured)}</p>
          <p className="lg-kicker">gesichert</p>
        </div>
        <div>
          {atRisk > 0 ? (
            <>
              <p className="lg-hero lg-hero-risk">{formatCount(atRisk)}</p>
              <p className="lg-kicker">{labels.units} in Gefahr</p>
            </>
          ) : (
            <>
              <p className={stop.time ? 'lg-hero lg-hero-time' : 'lg-hero'}>{stop.value}</p>
              <p className="lg-kicker">{stop.label}</p>
            </>
          )}
        </div>
        <div>
          <p className="lg-sub">{formatCount(product.still_to_pack)}</p>
          <p className="lg-kicker">
            offen bis {labels.deadline}
          </p>
        </div>
        <div>
          {atRisk > 0 ? (
            <>
              <p className="lg-sub">{stop.value}</p>
              <p className="lg-kicker">{stop.label}</p>
            </>
          ) : rest !== null ? (
            <>
              <p className="lg-sub">{rest}</p>
              <p className="lg-kicker">Restzeit</p>
            </>
          ) : (
            <>
              <p className="lg-sub">{product.limiting_component ?? '–'}</p>
              <p className="lg-kicker">Engpass</p>
            </>
          )}
        </div>
      </div>

      <p className="lg-note">
        <span>
          System sagt{' '}
          <span className={apart ? 'lg-struck' : undefined}>{formatPercent(system)}</span>
        </span>
        {apart && distance !== null ? (
          <span className="lg-gap-note">{formatPoints(distance)} Punkte ohne Beleg</span>
        ) : distance === null ? (
          <span>Kein Vergleich möglich</span>
        ) : (
          <span className="lg-ok-note">System und Belege stimmen überein</span>
        )}
      </p>

      {system !== null && secured !== null && (
        <div
          className="lg-track relative h-2 overflow-hidden rounded-tag bg-well"
          role="img"
          aria-label={`System sagt ${formatPercent(system)}, gesichert ${formatPercent(secured)}`}
        >
          <div className="fill-secured absolute inset-y-0 left-0" style={{width: share(secured)}} />
          {apart && (
            <div
              className="fill-gap absolute inset-y-0"
              style={{left: share(secured), width: share(system - secured)}}
            />
          )}
        </div>
      )}

      {total > 0 && (
        <div className="lg-track flex h-2 overflow-hidden rounded-tag" aria-hidden="true">
          {UNIT_STATES.map((entry) => (
            <div
              key={entry.key}
              className={entry.fill}
              style={{width: share(product.units[entry.key] / total)}}
            />
          ))}
        </div>
      )}
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

      <dl className="lg-facts">
        <div>
          <dt className="inline">Takt </dt>
          <dd>
            {product.rate_per_hour === null ? (
              'unbekannt'
            ) : (
              <>
                <span className="num">{formatCount(product.rate_per_hour)}</span> {labels.units} je Stunde
              </>
            )}
          </dd>
        </div>
        {product.hours_left !== null && (
          <div>
            <dt className="inline">Restzeit </dt>
            <dd className="num">{formatCount(product.hours_left)} h</dd>
          </div>
        )}
        {product.limiting_component !== null && (
          <div>
            <dt className="inline">Engpass </dt>
            <dd className="lg-id">{product.limiting_component}</dd>
          </div>
        )}
      </dl>
    </article>
  );
}

export function Coverage({state}: {state: LineguardState}) {
  const {labels} = usePage();
  const stop = state.first_stop;
  return (
    <section aria-labelledby="deckung">
      <div className="lg-kpis-head">
        <h2 id="deckung">Deckung bis {labels.deadline}</h2>
        <p>
          {state.next_due === null ? (
            'Kein offener Bedarfstermin'
          ) : (
            <>
              Nächster Bedarfstermin <Clock iso={state.next_due} distance />
            </>
          )}
        </p>
        <p>
          {stop === null || stop.breaks_at === null ? (
            `Kein Stopp der ${labels.line} in Sicht`
          ) : (
            <>
              Erster Stopp der {labels.line}:{' '}
              <span className="lg-id">{stop.component_id ?? '–'}</span>
              {stop.description !== null && ` ${stop.description}`}
              {' · '}
              <span className="lg-stop-clock">
                <Clock iso={stop.breaks_at} distance />
              </span>
            </>
          )}
        </p>
      </div>
      {state.products.length === 0 ? (
        <p className="lg-kpi">Kein {labels.product} mit offenem Bedarf.</p>
      ) : (
        <div className="lg-kpi-grid">
          {state.products.map((product) => (
            <ProductBlock key={product.product_id} product={product} state={state} />
          ))}
        </div>
      )}
    </section>
  );
}
