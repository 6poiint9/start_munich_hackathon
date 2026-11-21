'use client';

import * as api from '../lib/api';
import {formatClock, formatCount} from '../lib/format';
import type {Check, Correction, Finding} from '../lib/types';
import {
  causeWord,
  checkNameWord,
  checkStatusTone,
  checkStatusWord,
  correctionStatusTone,
  correctionStatusWord,
  findingStatusWord,
} from '../lib/words';

import {holdsRole, useAction, usePage} from './page-context';
import {ApproverNote, Button, Card, ErrorNote, RejectForm, Tag} from './ui';

const APPROVE_ROLES = ['erp_owner'];
const COUNT_ROLES = ['erp_owner', 'site_lead'];

function checkValue(check: Check): string | null {
  if (check.value === null) {
    return null;
  }
  return typeof check.value === 'number' ? formatCount(check.value) : check.value;
}

function CorrectionRow({correction}: {correction: Correction}) {
  const {person, people, timezone} = usePage();
  const action = useAction();
  const approver = people.find((entry) => entry.person_id === correction.approved_by)?.name ?? correction.approved_by;

  if (correction.status !== 'proposed') {
    return (
      <li className="flex flex-wrap items-center gap-2 py-2 text-meta text-ink-2">
        <Tag tone={correctionStatusTone(correction.status)}>{correctionStatusWord(correction.status)}</Tag>
        {approver !== null && <span>von {approver}</span>}
        {correction.approved_at !== null && (
          <span className="num">{formatClock(correction.approved_at, timezone, null)}</span>
        )}
        {correction.reject_reason !== null && <span>Grund: {correction.reject_reason}</span>}
      </li>
    );
  }
  const mayApprove = holdsRole(person, APPROVE_ROLES);
  const mayCount = holdsRole(person, COUNT_ROLES);
  return (
    <li className="space-y-2 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <Tag tone="wait">{correctionStatusWord(correction.status)}</Tag>
        {mayApprove && (
          <Button
            variant="primary"
            disabled={action.busy}
            onClick={() => void action.run((personId) => api.approveCorrection(correction.id, personId))}
          >
            Korrektur freigeben
          </Button>
        )}
        {mayCount && (
          <Button
            disabled={action.busy}
            onClick={() => void action.run((personId) => api.requestCount(correction.id, personId))}
          >
            Zählung anfordern
          </Button>
        )}
        {mayApprove && (
          <RejectForm
            label="Ablehnen"
            busy={action.busy}
            onReject={(reason) =>
              void action.run((personId) => api.rejectCorrection(correction.id, reason, personId))
            }
          />
        )}
      </div>
      {!mayApprove && <ApproverNote roles={APPROVE_ROLES} />}
      <ErrorNote message={action.error} />
    </li>
  );
}

interface CorrectionCardProps {
  finding: Finding;
  corrections: Correction[];
}

export function CorrectionCard({finding, corrections}: CorrectionCardProps) {
  return (
    <Card
      title="Buchungsbefund und Korrektur"
      aside={finding.status === null ? null : <Tag>{findingStatusWord(finding.status)}</Tag>}
    >
      <p className="text-lead">
        Wareneingang <span className="num font-medium">{finding.gr_number ?? '–'}</span>:{' '}
        <span className="num font-semibold text-stop">{formatCount(finding.booked_qty)}</span> gebucht,{' '}
        <span className="num font-semibold text-go">{formatCount(finding.proposed_qty)}</span> belegt.
      </p>
      <p className="mt-1 text-ink-2">
        Vermutung: {causeWord(finding.cause)}
        {finding.agreeing_sources !== null &&
          ` · ${formatCount(finding.agreeing_sources)} Quellen stimmen überein`}
      </p>

      {finding.checks.length > 0 && (
        <ul className="mt-3 divide-y divide-rule border-y border-rule">
          {finding.checks.map((check) => {
            const value = checkValue(check);
            return (
              <li key={check.name} className="flex items-baseline justify-between gap-3 py-1">
                <span className="text-ink-2">{checkNameWord(check.name)}</span>
                <span className="flex items-baseline gap-2">
                  {value !== null && <span className="num">{value}</span>}
                  <Tag tone={checkStatusTone(check.status)}>{checkStatusWord(check.status)}</Tag>
                </span>
              </li>
            );
          })}
        </ul>
      )}

      {corrections.length === 0 ? (
        <p className="mt-3 text-meta text-ink-3">Noch keine Korrektur vorgeschlagen.</p>
      ) : (
        <ul className="mt-1 divide-y divide-rule">
          {corrections.map((correction) => (
            <CorrectionRow key={correction.id} correction={correction} />
          ))}
        </ul>
      )}
    </Card>
  );
}
