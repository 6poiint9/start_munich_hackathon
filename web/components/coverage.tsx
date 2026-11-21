'use client';

import {formatCount, formatPercent, formatPoints} from '../lib/format';
import type {LineguardState, Product} from '../lib/types';

import {usePage} from './page-context';
import {Clock, cx} from './ui';

const UNIT_STATES = [
  {key: 'secured', word: 'gesichert', fill: 'fill-secured'},
  {key: 'planned', word: 'in Arbeit', fill: 'fill-planned'},
  {key: 'open', word: 'wartet auf Entscheidung', fill: 'fill-open'},
  {key: 'unclosable', word: 'nicht schließbar', fill: 'fill-unclosable'},
] as const;

/** Under this distance the two numbers count as equal. */
const SAME_RATIO = 0.0005;

function share(ratio: number): string {
  return `${Math.min(Math.max(ratio, 0), 1) * 100}%`;
}

function ProductBlock({product}: {product: Product}) {
  const {labels} = usePage();
  const system = product.coverage_system;
  const secured = product.coverage_secured;
  const distance = system !== null && secured !== null ? system - secured : null;
  const apart = distance !== null && distance > SAME_RATIO;
  const total = UNIT_STATES.reduce((sum, entry) => sum + product.units[entry.key], 0);

  return (
    <article className="rounded-sheet border border-rule bg-sheet px-4 py-3">
      <header className="flex flex-wrap items-baseline justify-between gap-x-3">
        <h3 className="text-lead font-semibold">
          {product.description ?? product.product_id}
        </h3>
        <p className="text-meta text-ink-3">
          {labels.product} <span className="num">{product.product_id}</span>
        </p>
      </header>

      <div className="mt-3 flex flex-wrap items-end gap-x-6 gap-y-2">
        <div>
          <p className="field-name">gesichert</p>
          <p className={cx('num text-hero font-semibold', apart ? 'text-ink' : 'text-go')}>
            {formatPercent(secured)}
          </p>
        </div>
        <div className="pb-0.5">
          <p className="field-name">System sagt</p>
          <p className={cx('num text-figure text-ink-3', apart && 'line-through decoration-stop-fill decoration-2')}>
            {formatPercent(system)}
          </p>
        </div>
        <p
          className={cx(
            'mb-1 rounded-ctl border px-2 py-1 text-body font-medium',
            apart ? 'border-stop/30 bg-stop-wash text-stop' : 'border-go/30 bg-go-wash text-go',
          )}
        >
          {apart && distance !== null
            ? `${formatPoints(distance)} Punkte ohne Beleg`
            : distance === null
              ? 'Kein Vergleich möglich'
              : 'System und Belege stimmen überein'}
        </p>
      </div>

      {system !== null && secured !== null && (
        <div
          className="relative mt-2 h-2 overflow-hidden rounded-tag bg-well"
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

      <div className="mt-4">
        <p className="field-name">
          Noch offen bis {labels.deadline}:{' '}
          <span className="num text-ink">{formatCount(product.still_to_pack)}</span>{' '}
          {labels.units}
        </p>
        {total > 0 && (
          <div className="mt-1 flex h-4 overflow-hidden rounded-tag border border-rule-2" aria-hidden="true">
            {UNIT_STATES.map((entry) => (
              <div
                key={entry.key}
                className={entry.fill}
                style={{width: share(product.units[entry.key] / total)}}
              />
            ))}
          </div>
        )}
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-meta">
          {UNIT_STATES.map((entry) => (
            <li
              key={entry.key}
              className={cx('flex items-center gap-1.5', product.units[entry.key] === 0 && 'text-ink-4')}
            >
              <span className={cx('h-2.5 w-2.5 rounded-tag border border-rule-2', entry.fill)} aria-hidden="true" />
              <span className="num font-medium">{formatCount(product.units[entry.key])}</span>
              {entry.word}
            </li>
          ))}
        </ul>
      </div>

      <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 border-t border-rule pt-2 text-meta text-ink-3">
        <div className="flex gap-1.5">
          <dt>Takt</dt>
          <dd className="text-ink">
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
          <div className="flex gap-1.5">
            <dt>Restzeit</dt>
            <dd className="num text-ink">{formatCount(product.hours_left)} h</dd>
          </div>
        )}
        {product.limiting_component !== null && (
          <div className="flex gap-1.5">
            <dt>Engpass</dt>
            <dd className="num text-ink">{product.limiting_component}</dd>
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
    <section aria-labelledby="deckung" className="space-y-2">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <h2 id="deckung" className="text-title font-semibold">
          Deckung bis {labels.deadline}
        </h2>
        <p className="text-body text-ink-2">
          {state.next_due === null ? (
            'Kein offener Bedarfstermin'
          ) : (
            <>
              Nächster Bedarfstermin <Clock iso={state.next_due} distance />
            </>
          )}
        </p>
        <p className="text-body text-ink-2">
          {stop === null || stop.breaks_at === null ? (
            `Kein Stopp der ${labels.line} in Sicht`
          ) : (
            <>
              Erster Stopp der {labels.line}:{' '}
              <span className="num font-medium text-stop">{stop.component_id ?? '–'}</span>
              {stop.description !== null && ` ${stop.description}`} ·{' '}
              <span className="font-medium">
                <Clock iso={stop.breaks_at} distance />
              </span>
            </>
          )}
        </p>
      </div>
      {state.products.length === 0 ? (
        <p className="rounded-sheet border border-rule bg-sheet px-4 py-3 text-ink-3">
          Kein {labels.product} mit offenem Bedarf.
        </p>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {state.products.map((product) => (
            <ProductBlock key={product.product_id} product={product} />
          ))}
        </div>
      )}
    </section>
  );
}
