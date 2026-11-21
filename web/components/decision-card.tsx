'use client';

import {useState} from 'react';
import type {ReactNode} from 'react';

import * as api from '../lib/api';
import {formatClock, formatMoney, formatPercent, formatSigned, parseInstant} from '../lib/format';
import type {CaseView, Decision, Option} from '../lib/types';
import {decisionStatusTone, decisionStatusWord, planRoleWord, roleWord} from '../lib/words';

import {holdsRole, useAction, usePage} from './page-context';
import {ApproverNote, Button, Clock, ErrorNote, RejectForm, Tag, cx} from './ui';

/** From this confidence on an option counts as "sicher". */
const SURE_FROM = 0.85;

function confidenceText(confidence: number | null): string {
  if (confidence === null) {
    return 'unbekannt';
  }
  return `${confidence >= SURE_FROM ? 'sicher' : 'unsicher'} ${formatPercent(confidence)}`;
}

function isLate(option: Option, latestUseful: string | null): boolean {
  const arrival = parseInstant(option.arrives_at);
  const limit = parseInstant(latestUseful);
  return arrival !== null && limit !== null && arrival.getTime() > limit.getTime();
}

function decisionRoles(decision: Decision): string[] {
  if (decision.needs_roles.length > 0) {
    return decision.needs_roles;
  }
  return decision.approver_role === null ? [] : [decision.approver_role];
}

interface FigureProps {
  name: string;
  children: ReactNode;
}

function Figure({name, children}: FigureProps) {
  return (
    <div>
      <dt className="field-name">{name}</dt>
      <dd className="num">{children}</dd>
    </div>
  );
}

interface OptionRowProps {
  option: Option;
  latestUseful: string | null;
  recommended: boolean;
  chosen: boolean;
  /** `null` for a decision that is closed: the row is then only text. */
  group: string | null;
  onChoose: (id: number) => void;
}

function OptionRow({option, latestUseful, recommended, chosen, group, onChoose}: OptionRowProps) {
  const role = planRoleWord(option.role_in_plan) ?? (recommended ? 'Empfehlung' : null);
  const late = isLate(option, latestUseful);
  return (
    <label
      className={cx(
        'flex flex-wrap items-start gap-x-4 gap-y-2 border-l-2 px-3 py-2',
        chosen ? 'border-stamp bg-stamp-wash' : 'border-transparent',
        option.feasible ? group !== null && 'cursor-pointer' : 'text-ink-3',
      )}
    >
      <span className="flex min-w-56 flex-1 items-start gap-2">
        {group !== null && (
          <input
            type="radio"
            name={group}
            className="mt-1 accent-stamp"
            checked={chosen}
            disabled={!option.feasible}
            onChange={() => onChoose(option.id)}
          />
        )}
        <span>
          <span className={cx('font-medium', option.feasible && 'text-ink')}>{option.title}</span>
          <span className="mt-0.5 flex flex-wrap gap-1.5">
            {role !== null && <Tag tone={option.role_in_plan === 'backup' ? 'neutral' : 'work'}>{role}</Tag>}
            {!option.feasible && <Tag tone="stop">nicht machbar</Tag>}
            {option.status === 'approved' && <Tag tone="go">freigegeben</Tag>}
          </span>
          {!option.feasible && option.infeasible_reason !== null && (
            <span className="mt-1 block text-meta">Grund: {option.infeasible_reason}</span>
          )}
        </span>
      </span>
      <dl className="grid w-full grid-cols-4 gap-x-4 sm:w-[25rem]">
        <Figure name="Gewinn">{formatSigned(option.qty_gain)}</Figure>
        <Figure name="Ankunft">
          <Clock iso={option.arrives_at} />
          {late && <span className="block font-sans text-cap font-medium text-stop">zu spät</span>}
        </Figure>
        <Figure name="Kosten">{formatMoney(option.cost_eur)}</Figure>
        <Figure name="Zusage">
          <span className="font-sans">{confidenceText(option.confidence)}</span>
        </Figure>
      </dl>
    </label>
  );
}

interface DecisionCardProps {
  decision: Decision;
  view: CaseView;
}

/** The moment a human decides: one recommendation, its price, one click. */
export function DecisionCard({decision, view}: DecisionCardProps) {
  const {person, people, timezone, now} = usePage();
  const action = useAction();
  const [picked, setPicked] = useState<number | null>(null);

  const listed = view.options.filter((option) => decision.options.includes(option.id));
  const options = listed.length > 0 ? listed : view.options;
  const feasible = options.filter((option) => option.feasible);
  const fallback =
    feasible.find((option) => option.id === decision.recommended_option) ??
    feasible.find((option) => option.role_in_plan === 'primary') ??
    feasible[0];
  const chosen = feasible.find((option) => option.id === picked) ?? fallback;
  const open = decision.status === 'open';
  const roles = decisionRoles(decision);
  const allowed = holdsRole(person, roles);
  const decider = people.find((entry) => entry.person_id === decision.decided_by)?.name ?? decision.decided_by;
  const latestUseful = view.detail.latest_useful_arrival;

  return (
    <section
      aria-label={`Entscheidung: ${decision.title}`}
      className={cx(
        'rounded-sheet border bg-sheet',
        open ? 'border-rule-ink shadow-[0_0_0_3px_var(--color-stamp-wash)]' : 'border-rule',
      )}
    >
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 px-4 pt-3">
        <div className="min-w-0">
          <p className="field-name">{open ? 'Deine Entscheidung' : 'Entscheidung'}</p>
          <h3 className="text-title font-semibold">{decision.title}</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-meta text-ink-2">
          <Tag tone={decisionStatusTone(decision.status)}>{decisionStatusWord(decision.status)}</Tag>
          {open && decision.deadline !== null && (
            <span>
              entscheiden bis{' '}
              <span className="font-medium">
                <Clock iso={decision.deadline} distance />
              </span>
            </span>
          )}
        </div>
      </header>
      {decision.explanation !== null && (
        <p className="max-w-[72ch] px-4 pt-1 text-ink-2">{decision.explanation}</p>
      )}

      {options.length === 0 ? (
        <p className="px-4 py-3 text-ink-3">Zu dieser Entscheidung gibt es keine Option.</p>
      ) : (
        <div
          role={open ? 'radiogroup' : undefined}
          aria-label="Optionen"
          className="mt-3 divide-y divide-rule border-y border-rule"
        >
          {options.map((option) => (
            <OptionRow
              key={option.id}
              option={option}
              latestUseful={latestUseful}
              recommended={option.id === decision.recommended_option}
              chosen={open && option.id === chosen?.id}
              group={open ? `entscheidung-${decision.id}` : null}
              onChoose={setPicked}
            />
          ))}
        </div>
      )}

      <footer className="space-y-2 px-4 py-3">
        {open ? (
          <>
            <p className="text-meta text-ink-3">
              Freigabe durch{' '}
              <span className="text-ink-2">{roles.map(roleWord).join(' oder ') || 'jede Rolle'}</span>
              {decision.approver_name !== null && ` · ${decision.approver_name}`}
              {decision.policy_ref !== null && ` · Regel: ${decision.policy_ref}`}
            </p>
            {allowed ? (
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <Button
                  variant="primary"
                  large
                  disabled={action.busy || chosen === undefined}
                  onClick={() =>
                    void action.run((personId) =>
                      api.approveDecision(decision.id, chosen?.id ?? null, personId),
                    )
                  }
                >
                  {action.busy ? 'Wird freigegeben …' : 'Freigeben'}
                </Button>
                {chosen !== undefined && (
                  <p className="min-w-48 flex-1 text-body text-ink-2">
                    <span className="font-medium text-ink">{chosen.title}</span>
                    <span className="block text-meta">
                      <span className="num font-medium text-ink">{formatMoney(chosen.cost_eur)}</span> ·{' '}
                      <span className="num">{formatSigned(chosen.qty_gain)}</span> · Ankunft{' '}
                      <span className="num">{formatClock(chosen.arrives_at, timezone, now)}</span>
                    </span>
                  </p>
                )}
                <RejectForm
                  label="Ablehnen"
                  busy={action.busy}
                  onReject={(reason) =>
                    void action.run((personId) => api.rejectDecision(decision.id, reason, personId))
                  }
                />
              </div>
            ) : (
              <ApproverNote roles={roles} name={decision.approver_name} />
            )}
            <ErrorNote message={action.error} />
          </>
        ) : (
          <p className="text-meta text-ink-2">
            {decisionStatusWord(decision.status)}
            {decider !== null && ` von ${decider}`}
            {decision.decided_at !== null && (
              <>
                {' '}
                am <span className="num">{formatClock(decision.decided_at, timezone, null)}</span>
              </>
            )}
            {decision.reject_reason !== null && ` · Grund: ${decision.reject_reason}`}
          </p>
        )}
      </footer>
    </section>
  );
}
