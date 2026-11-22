'use client';

import {useState} from 'react';

import * as api from '../../lib/api';
import {formatClock, formatMoney, formatPercent, formatSigned, parseInstant} from '../../lib/format';
import type {CaseView, Decision, Option} from '../../lib/types';
import {decisionStatusTone, decisionStatusWord, planRoleWord, roleWord} from '../../lib/words';

import {holdsRole, useAction, usePage} from '../page-context';
import {ApproverNote, Button, Clock, ErrorNote, RejectForm, Tag, cx} from '../ui';

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

interface OptionCardProps {
  option: Option;
  latestUseful: string | null;
  recommended: boolean;
  chosen: boolean;
  group: string | null;
  onChoose: (id: number) => void;
}

function OptionCard({option, latestUseful, recommended, chosen, group, onChoose}: OptionCardProps) {
  const role = planRoleWord(option.role_in_plan) ?? (recommended ? 'Empfehlung' : null);
  const late = isLate(option, latestUseful);
  const open = group !== null;
  return (
    <label
      className={cx(
        'lg-option',
        option.feasible && 'is-feasible',
        !option.feasible && 'is-blocked',
        recommended && 'is-recommended',
        chosen && 'is-chosen',
      )}
    >
      {open && (
        <input
          type="radio"
          name={group}
          className="lg-radio"
          checked={chosen}
          disabled={!option.feasible}
          onChange={() => onChoose(option.id)}
        />
      )}
      <span className="lg-option-title">
        {recommended && <span className="lg-rec">Empfehlung</span>}
        <span>{option.title}</span>
        {role !== null && role !== 'Empfehlung' && <Tag tone={option.role_in_plan === 'backup' ? 'neutral' : 'work'}>{role}</Tag>}
        {!option.feasible && <Tag tone="stop">nicht machbar</Tag>}
        {option.status === 'approved' && <Tag tone="go">freigegeben</Tag>}
      </span>
      {!option.feasible && option.infeasible_reason !== null && (
        <p className="lg-reason">Grund: {option.infeasible_reason}</p>
      )}
      <dl className="lg-figs">
        <div>
          <dt>Gewinn</dt>
          <dd>{formatSigned(option.qty_gain)}</dd>
        </div>
        <div>
          <dt>Ankunft</dt>
          <dd>
            <Clock iso={option.arrives_at} />
            {late && <span className="lg-late">zu spät</span>}
          </dd>
        </div>
        <div>
          <dt>Kosten</dt>
          <dd>{formatMoney(option.cost_eur)}</dd>
        </div>
        <div>
          <dt>Zusage</dt>
          <dd>{confidenceText(option.confidence)}</dd>
        </div>
      </dl>
    </label>
  );
}

interface DecisionBlockProps {
  decision: Decision;
  view: CaseView;
}

/** One decision: option cards, the recommended one marked, one approve button. */
export function DecisionBlock({decision, view}: DecisionBlockProps) {
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
  const route = roles.map(roleWord).join(' oder ') || 'jede Rolle';

  return (
    <section
      aria-label={`Entscheidung: ${decision.title}`}
      className={open ? 'lg-decision lg-on-card is-open' : 'lg-decision lg-on-card'}
    >
      <header className="lg-decision-head">
        <div>
          <p className="lg-kicker-label">{open ? 'Deine Entscheidung' : 'Entscheidung'}</p>
          <h3>{decision.title}</h3>
        </div>
        <p className="lg-when">
          <Tag tone={decisionStatusTone(decision.status)}>{decisionStatusWord(decision.status)}</Tag>
          {open && decision.deadline !== null && (
            <>
              {' '}
              entscheiden bis <Clock iso={decision.deadline} distance />
            </>
          )}
        </p>
      </header>
      {decision.explanation !== null && <p className="lg-explain">{decision.explanation}</p>}
      <p className="lg-route">
        Freigabe durch {route}
        {decision.approver_name !== null && ` · ${decision.approver_name}`}
        {decision.policy_ref !== null && <span className="lg-quiet"> · Regel: {decision.policy_ref}</span>}
      </p>

      {options.length === 0 ? (
        <p className="lg-explain">Zu dieser Entscheidung gibt es keine Option.</p>
      ) : (
        <div role={open ? 'radiogroup' : undefined} aria-label="Optionen" className="lg-options">
          {options.map((option) => (
            <OptionCard
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

      {open ? (
        <footer className="lg-approve">
          {allowed ? (
            <div className="lg-approve-row">
              <Button
                variant="primary"
                large
                className="lg-approve-btn"
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
                <p className="lg-chosen-line">
                  <strong>{chosen.title}</strong>
                  <span>
                    {' '}
                    · {formatMoney(chosen.cost_eur)} · {formatSigned(chosen.qty_gain)} · Ankunft{' '}
                    {formatClock(chosen.arrives_at, timezone, now)}
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
        </footer>
      ) : (
        <p className="lg-closed-line">
          {decisionStatusWord(decision.status)}
          {decider !== null && ` von ${decider}`}
          {decision.decided_at !== null && (
            <>
              {' '}
              am <span className="lg-id">{formatClock(decision.decided_at, timezone, null)}</span>
            </>
          )}
          {decision.reject_reason !== null && ` · Grund: ${decision.reject_reason}`}
        </p>
      )}
    </section>
  );
}
