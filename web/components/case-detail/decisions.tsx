'use client';

import {useState} from 'react';

import * as api from '../../lib/api';
import {formatClock, formatMoney, formatPercent, formatSigned, parseInstant} from '../../lib/format';
import type {CaseView, Decision, Option} from '../../lib/types';
import {decisionStatusTone, decisionStatusWord, planRoleWord, roleWord} from '../../lib/words';

import {holdsRole, useAction, usePage} from '../page-context';
import {ApproverNote, Button, Clock, ErrorNote, RejectForm, Tag} from '../ui';

const SURE_FROM = 0.85;

function certaintyText(confidence: number | null): string {
  if (confidence === null) {
    return 'Unknown';
  }
  return `${confidence >= SURE_FROM ? 'High' : 'Low'}, ${formatPercent(confidence)}`;
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
  const role = recommended ? null : planRoleWord(option.role_in_plan);
  const late = isLate(option, latestUseful);
  return (
    <label
      className="cd-option"
      data-chosen={chosen}
      data-blocked={!option.feasible}
      data-pick={group !== null && option.feasible}
    >
      {group !== null && (
        <input
          type="radio"
          name={group}
          className="cd-radio"
          checked={chosen}
          disabled={!option.feasible}
          onChange={() => onChoose(option.id)}
        />
      )}
      <span className="cd-option-body">
        <span className="cd-option-title">
          <span>{option.title}</span>
          {recommended && <Tag tone="go">Recommended</Tag>}
          {role !== null && <Tag>{role}</Tag>}
          {!option.feasible && <Tag tone="stop">Not possible</Tag>}
          {option.status === 'approved' && <Tag tone="go">Approved</Tag>}
        </span>
        {!option.feasible && option.infeasible_reason !== null && (
          <span className="cd-quiet">Reason: {option.infeasible_reason}</span>
        )}
        <dl className="cd-figs">
          <div>
            <dt className="lg-label">Adds</dt>
            <dd>{formatSigned(option.qty_gain)}</dd>
          </div>
          <div>
            <dt className="lg-label">Arrives</dt>
            <dd>
              <Clock iso={option.arrives_at} />
              {late && <span className="lg-hot"> too late</span>}
            </dd>
          </div>
          <div>
            <dt className="lg-label">Cost</dt>
            <dd>{formatMoney(option.cost_eur)}</dd>
          </div>
          <div>
            <dt className="lg-label">Certainty</dt>
            <dd>{certaintyText(option.confidence)}</dd>
          </div>
        </dl>
      </span>
    </label>
  );
}

interface DecisionBlockProps {
  decision: Decision;
  view: CaseView;
  live: boolean;
}

/** One decision: the options, the recommended one marked, one approve button. */
export function DecisionBlock({decision, view, live}: DecisionBlockProps) {
  const {person, people, timezone, now} = usePage();
  const action = useAction();
  const [picked, setPicked] = useState<number | null>(null);

  const isAlert = decision.kind === 'unclosable_gap';
  const listed = view.options.filter((option) => decision.options.includes(option.id));
  const options = isAlert ? [] : listed.length > 0 ? listed : view.options;
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
  const route = roles.map(roleWord).join(' or ') || 'Any role';
  const hasDraft = view.emails.some((email) => email.status === 'draft');

  return (
    <section
      aria-label={`Decision: ${decision.title}`}
      className="cd-decision"
      data-open={open}
    >
      <header className="cd-block-head">
        <div>
          <p className="lg-label">{open ? 'Decision that waits for a person' : 'Decision'}</p>
          <h3>{decision.title}</h3>
        </div>
        <p className="cd-when">
          <Tag tone={decisionStatusTone(decision.status)}>{decisionStatusWord(decision.status)}</Tag>
          {open && decision.deadline !== null && (
            <span>
              Decide by <Clock iso={decision.deadline} distance />
            </span>
          )}
        </p>
      </header>
      {decision.explanation !== null && <p className="cd-explain">{decision.explanation}</p>}
      <dl className="cd-route">
        <div>
          <dt className="lg-label">Who approves</dt>
          <dd>
            {route}
            {decision.approver_name !== null && ` · ${decision.approver_name}`}
          </dd>
        </div>
        {decision.policy_ref !== null && (
          <div>
            <dt className="lg-label">Approval rule</dt>
            <dd>{decision.policy_ref}</dd>
          </div>
        )}
        {latestUseful !== null && (
          <div>
            <dt className="lg-label">Latest useful arrival</dt>
            <dd>
              <Clock iso={latestUseful} />
            </dd>
          </div>
        )}
      </dl>

      {options.length === 0 ? (
        <p className="cd-explain">{isAlert
          ? 'This alert does not arrange a later delivery. Check the available options for dates and costs.'
          : 'This decision has no option.'}</p>
      ) : (
        <div role={open ? 'radiogroup' : undefined} aria-label="Options" className="cd-options">
          {options.map((option) => (
            <OptionCard
              key={option.id}
              option={option}
              latestUseful={latestUseful}
              recommended={option.id === decision.recommended_option}
              chosen={open && option.id === chosen?.id}
              group={open ? `decision-${decision.id}` : null}
              onChoose={setPicked}
            />
          ))}
        </div>
      )}

      {open ? (
        <footer className="cd-approve">
          {allowed ? (
            <>
              {chosen !== undefined && (
                <p className="cd-chosen">
                  You approve: <strong>{chosen.title}</strong>. Cost {formatMoney(chosen.cost_eur)},
                  adds {formatSigned(chosen.qty_gain)}, arrives{' '}
                  {formatClock(chosen.arrives_at, timezone, now)}.
                  {hasDraft &&
                    (live
                      ? ' Lineguard then sends the mail draft of this case.'
                      : ' Mail mode is "log only": Lineguard writes the mail to the log and sends nothing.')}
                </p>
              )}
              {isAlert && <p className="cd-chosen">
                Acknowledging this alert does not arrange a delivery or send an email.
              </p>}
              <div className="cd-actions">
                <Button
                  variant="primary"
                  large
                  disabled={action.busy || (!isAlert && chosen === undefined)}
                  onClick={() =>
                    void action.run((personId) =>
                      api.approveDecision(decision.id, chosen?.id ?? null, personId),
                    )
                  }
                >
                  {action.busy ? 'Working …' : isAlert ? 'Acknowledge' : 'Approve'}
                </Button>
                {!isAlert && <RejectForm
                  label="Reject"
                  busy={action.busy}
                  onReject={(reason) =>
                    void action.run((personId) => api.rejectDecision(decision.id, reason, personId))
                  }
                />}
              </div>
            </>
          ) : (
            <ApproverNote roles={roles} name={decision.approver_name} />
          )}
          <ErrorNote message={action.error} />
        </footer>
      ) : (
        <p className="cd-quiet">
          {decisionStatusWord(decision.status)}
          {decider !== null && ` by ${decider}`}
          {decision.decided_at !== null && (
            <>
              {' '}
              on <span className="num">{formatClock(decision.decided_at, timezone, null)}</span>
            </>
          )}
          {decision.reject_reason !== null && `. Reason: ${decision.reject_reason}`}
        </p>
      )}
    </section>
  );
}
