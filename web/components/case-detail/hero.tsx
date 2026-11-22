'use client';

import {useState} from 'react';

import * as api from '../../lib/api';
import {formatClock, formatCount, formatSigned} from '../../lib/format';
import type {CaseView, Correction, Evidence, EvidenceFile} from '../../lib/types';
import {
  causeWord,
  checkNameWord,
  checkStatusTone,
  checkStatusWord,
  correctionStatusTone,
  correctionStatusWord,
  findingStatusWord,
} from '../../lib/words';
import {FileDialog} from '../evidence';
import {holdsRole, useAction, usePage} from '../page-context';
import {ApproverNote, Button, ErrorNote, RejectForm, Tag} from '../ui';

import {heroModel} from './read';
import type {HeroModel} from './read';

const APPROVE_ROLES = ['erp_owner'];
const COUNT_ROLES = ['erp_owner', 'site_lead'];

interface OpenFile {
  file: EvidenceFile;
  locator: string | null;
}

function fileName(file: EvidenceFile): string {
  return file.path ?? `Datei ${file.id}`;
}

function Metric({label, value, risk = false}: {label: string; value: string; risk?: boolean}) {
  return (
    <div className={risk ? 'lg-metric lg-on-card is-risk' : 'lg-metric lg-on-card'}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function DocumentPane({
  model,
  onOpen,
}: {
  model: HeroModel;
  onOpen: (file: OpenFile) => void;
}) {
  const note = model.note;
  const file = note?.file ?? null;
  const kind = file === null ? null : api.fileKind(file.path);
  const open = () => {
    if (file !== null) {
      onOpen({file, locator: note?.locator ?? null});
    }
  };
  return (
    <div className="lg-doc lg-on-card">
      <p className="lg-kicker-label">Beleg</p>
      {file !== null && kind === 'image' ? (
        <button type="button" className="lg-scan" onClick={open}>
          {/* The scan comes from the API at run time. next/image cannot size it. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={api.fileUrl(file)} alt={`Beleg ${fileName(file)}`} />
        </button>
      ) : (
        <button type="button" className="lg-scan lg-plate" onClick={open} disabled={file === null}>
          <span className="lg-kicker-label">{kind === 'pdf' ? 'PDF' : 'Dokument'}</span>
          <strong className="lg-id">{note?.ref ?? model.finding.gr_number ?? 'ohne Nummer'}</strong>
        </button>
      )}
      {model.handwritten && <p className="lg-chip">Handschriftliche Korrektur</p>}
      <div className="lg-doc-meta">
        {note?.ref !== null && note?.ref !== undefined && (
          <span>
            Ref. <span className="lg-id">{note.ref}</span>
          </span>
        )}
        {model.finding.gr_number !== null && (
          <span>
            Wareneingang <span className="lg-id">{model.finding.gr_number}</span>
          </span>
        )}
        {file !== null && (
          <button type="button" onClick={open}>
            <span className="lg-id">{fileName(file)}</span>
            <span className="sr-only"> öffnen</span>
          </button>
        )}
      </div>
    </div>
  );
}

function Figures({model}: {model: HeroModel}) {
  const gapRisk = model.gap !== null && model.gap < 0;
  const showShift =
    model.booked !== null && model.noteQty !== null && model.booked !== model.noteQty;
  return (
    <div className="lg-metrics">
      {showShift && (
        <p className="lg-shift">
          <b>{formatCount(model.booked)}</b>
          <span aria-hidden="true"> → </span>
          <b>{formatCount(model.noteQty)}</b>
        </p>
      )}
      <dl className="lg-metrics">
        <Metric label="ERP gebucht" value={formatCount(model.booked)} />
        <Metric label={model.noteLabel} value={formatCount(model.noteQty)} />
        <Metric
          label={model.gapLabel}
          value={formatSigned(model.gap)}
          risk={gapRisk}
        />
      </dl>
      {(model.handwritten || model.finding.cause !== null) && (
        <p className="lg-hint">
          {model.handwritten && (
            <>
              <span>Handschriftliche Korrektur. </span>
              {model.printed !== null && model.noteQty !== null && (
                <>Gedruckt {formatCount(model.printed)}, von Hand {formatCount(model.noteQty)}. </>
              )}
            </>
          )}
          {model.finding.cause !== null && <>Vermutung: {causeWord(model.finding.cause)}.</>}
        </p>
      )}
    </div>
  );
}

function CorrectionRow({correction}: {correction: Correction}) {
  const {person, people, timezone} = usePage();
  const action = useAction();
  const approver =
    people.find((entry) => entry.person_id === correction.approved_by)?.name ??
    correction.approved_by;
  if (correction.status !== 'proposed') {
    return (
      <li className="lg-quiet">
        <Tag tone={correctionStatusTone(correction.status)}>{correctionStatusWord(correction.status)}</Tag>
        {approver !== null && <span> von {approver}</span>}
        {correction.approved_at !== null && (
          <span className="lg-id"> {formatClock(correction.approved_at, timezone, null)}</span>
        )}
        {correction.reject_reason !== null && <span> Grund: {correction.reject_reason}</span>}
      </li>
    );
  }
  const mayApprove = holdsRole(person, APPROVE_ROLES);
  const mayCount = holdsRole(person, COUNT_ROLES);
  return (
    <li>
      <div className="lg-actions">
        <Tag tone="wait">{correctionStatusWord(correction.status)}</Tag>
        {mayApprove && (
          <Button
            variant="primary"
            className="lg-approve-btn"
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

function FindingCard({view}: {view: CaseView}) {
  const finding = view.finding;
  if (finding === null) {
    return null;
  }
  const fails = finding.checks.filter((check) => check.status === 'fail').length;
  return (
    <section className="lg-finding lg-on-card" aria-label="Buchungsbefund und Korrektur">
      <div className="lg-finding-head">
        <p className="lg-kicker-label">Buchungsbefund und Korrektur</p>
        {finding.status !== null && <Tag>{findingStatusWord(finding.status)}</Tag>}
      </div>
      <p>
        Wareneingang <span className="lg-id">{finding.gr_number ?? '–'}</span>:{' '}
        {formatCount(finding.booked_qty)} gebucht, {formatCount(finding.proposed_qty)} belegt.
      </p>
      <p className="lg-quiet">
        Vermutung: {causeWord(finding.cause)}
        {finding.agreeing_sources !== null &&
          ` · ${formatCount(finding.agreeing_sources)} Quellen stimmen überein`}
      </p>
      {view.corrections.length === 0 ? (
        <p className="lg-quiet">Noch keine Korrektur vorgeschlagen.</p>
      ) : (
        <ul className="lg-action-list">
          {view.corrections.map((correction) => (
            <CorrectionRow key={correction.id} correction={correction} />
          ))}
        </ul>
      )}
      {finding.checks.length > 0 && (
        <details className="lg-checks">
          <summary>
            <span>Prüfungen</span>
            <span className="lg-fold-end">
              <span className="lg-count">{fails > 0 ? `${fails} weichen ab` : finding.checks.length}</span>
              <i className="lg-chevron" aria-hidden="true" />
            </span>
          </summary>
          <ul className="lg-check-list">
            {finding.checks.map((check) => {
              const value =
                check.value === null
                  ? null
                  : typeof check.value === 'number'
                    ? formatCount(check.value)
                    : check.value;
              return (
                <li key={check.name}>
                  <span>{checkNameWord(check.name)}</span>
                  <span>
                    {value !== null && <span>{value} </span>}
                    <Tag tone={checkStatusTone(check.status)}>{checkStatusWord(check.status)}</Tag>
                  </span>
                </li>
              );
            })}
          </ul>
        </details>
      )}
    </section>
  );
}

function noteKey(note: Evidence | null): string {
  return note?.ref ?? 'beleg';
}

/** Document on the left, booked quantity against the note and the gap on the right. */
export function DiscrepancyHero({view}: {view: CaseView}) {
  const model = heroModel(view);
  const [open, setOpen] = useState<OpenFile | null>(null);
  if (model === null) {
    return view.finding === null ? null : <FindingCard view={view} />;
  }
  return (
    <>
      <section className="lg-hero" aria-label={`Buchung gegen Beleg ${noteKey(model.note)}`}>
        <DocumentPane model={model} onOpen={setOpen} />
        <Figures model={model} />
      </section>
      <FindingCard view={view} />
      {open !== null && (
        <FileDialog key={open.file.id} file={open.file} locator={open.locator} onClose={() => setOpen(null)} />
      )}
    </>
  );
}
