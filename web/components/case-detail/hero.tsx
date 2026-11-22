'use client';

import {useState} from 'react';

import * as api from '../../lib/api';
import {formatClock, formatCount, formatSigned} from '../../lib/format';
import type {CaseView, Correction, EvidenceFile} from '../../lib/types';
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
import {ErpPreview, erpEffect} from '../erp-preview';
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
  return file.path ?? `File ${file.id}`;
}

function Figure({label, value, risk = false}: {label: string; value: string; risk?: boolean}) {
  return (
    <div data-tone={risk ? 'risk' : undefined}>
      <dd>{value}</dd>
      <dt>{label}</dt>
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
    <figure className="cd-doc">
      {file !== null && kind === 'image' ? (
        <button type="button" className="cd-scan" onClick={open}>
          {/* The scan comes from the API at run time. next/image cannot size it. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={api.fileUrl(file)} alt={`Document ${fileName(file)}`} />
        </button>
      ) : (
        <button type="button" className="cd-scan cd-plate" onClick={open} disabled={file === null}>
          <span className="lg-label">{kind === 'pdf' ? 'PDF' : 'Document'}</span>
          <strong className="lg-id">{note?.ref ?? model.finding.gr_number ?? 'no number'}</strong>
        </button>
      )}
      <figcaption className="cd-doc-meta">
        {model.handwritten && <span className="lg-hot">Corrected by hand</span>}
        {note?.ref !== null && note?.ref !== undefined && (
          <span>
            Ref. <span className="lg-id">{note.ref}</span>
          </span>
        )}
        {model.finding.gr_number !== null && (
          <span>
            Goods receipt <span className="lg-id">{model.finding.gr_number}</span>
          </span>
        )}
        {file !== null && (
          <button type="button" className="lg-link" onClick={open}>
            Open <span className="lg-id">{fileName(file)}</span>
          </button>
        )}
      </figcaption>
    </figure>
  );
}

function Figures({model}: {model: HeroModel}) {
  const gapRisk = model.gap !== null && model.gap < 0;
  return (
    <div>
      <dl className="cd-figures">
        <Figure label="Booked in the ERP" value={formatCount(model.booked)} />
        <Figure label={model.noteLabel} value={formatCount(model.noteQty)} />
        <Figure label={model.gapLabel} value={formatSigned(model.gap)} risk={gapRisk} />
      </dl>
      {(model.handwritten || model.finding.cause !== null) && (
        <p className="cd-hint">
          {model.handwritten && model.printed !== null && model.noteQty !== null && (
            <>
              The document prints {formatCount(model.printed)}. A person corrected it by hand to{' '}
              {formatCount(model.noteQty)}.{' '}
            </>
          )}
          {model.finding.cause !== null && <>Likely cause: {causeWord(model.finding.cause)}.</>}
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
      <li className="cd-quiet">
        <Tag tone={correctionStatusTone(correction.status)}>{correctionStatusWord(correction.status)}</Tag>
        {approver !== null && <span> by {approver}</span>}
        {correction.approved_at !== null && (
          <span className="num"> {formatClock(correction.approved_at, timezone, null)}</span>
        )}
        {correction.reject_reason !== null && <span>. Reason: {correction.reject_reason}</span>}
        <ErpPreview payload={correction.payload} writer={correction.writer} status={correction.status} />
      </li>
    );
  }
  const mayApprove = person !== null;
  const mayReject = holdsRole(person, APPROVE_ROLES);
  const mayCount = holdsRole(person, COUNT_ROLES);
  return (
    <li>
      <p className="cd-quiet">
        The correction waits for approval. {erpEffect(correction.writer)}
      </p>
      <ErpPreview payload={correction.payload} writer={correction.writer} />
      <div className="cd-actions">
        {mayApprove && (
          <Button
            variant="primary"
            disabled={action.busy}
            onClick={() => void action.run((personId) => api.approveCorrection(correction.id, personId))}
          >
            Approve correction
          </Button>
        )}
        {mayCount && (
          <Button
            disabled={action.busy}
            onClick={() => void action.run((personId) => api.requestCount(correction.id, personId))}
          >
            Request stock count
          </Button>
        )}
        {mayReject && (
          <RejectForm
            label="Reject"
            busy={action.busy}
            onReject={(reason) =>
              void action.run((personId) => api.rejectCorrection(correction.id, reason, personId))
            }
          />
        )}
      </div>
      {!mayApprove && <ApproverNote roles={[]} />}
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
    <section className="cd-block" aria-labelledby="cd-finding">
      <div className="cd-block-head">
        <h3 id="cd-finding" className="lg-label">
          Booking error and correction
        </h3>
        {finding.status !== null && <Tag>{findingStatusWord(finding.status)}</Tag>}
      </div>
      <p className="cd-lead">
        Goods receipt <span className="lg-id">{finding.gr_number ?? '–'}</span>: the ERP booked{' '}
        {formatCount(finding.booked_qty)}. The documents show {formatCount(finding.proposed_qty)}.
      </p>
      <p className="cd-quiet">
        Likely cause: {causeWord(finding.cause)}.
        {finding.agreeing_sources !== null &&
          ` ${formatCount(finding.agreeing_sources)} sources agree on the documented quantity.`}
      </p>
      {view.corrections.length === 0 ? (
        <p className="cd-quiet">Lineguard proposed no correction yet.</p>
      ) : (
        <ul className="cd-list">
          {view.corrections.map((correction) => (
            <CorrectionRow key={correction.id} correction={correction} />
          ))}
        </ul>
      )}
      {finding.checks.length > 0 && (
        <details className="cd-fold">
          <summary>
            <span>
              Checks against other sources
            </span>
            <span className="cd-fold-end">
              <span className="num">
                {fails > 0 ? `${fails} of ${finding.checks.length} differ` : finding.checks.length}
              </span>
              <i className="cd-chevron" aria-hidden="true" />
            </span>
          </summary>
          <ul className="cd-check-list">
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
                  <span className="cd-check-end">
                    {value !== null && <span className="num">{value}</span>}
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

/** Document on the left, booked quantity against the note and the gap on the right. */
export function DiscrepancyHero({view}: {view: CaseView}) {
  const model = heroModel(view);
  const [open, setOpen] = useState<OpenFile | null>(null);
  if (model === null) {
    return view.finding === null ? null : <FindingCard view={view} />;
  }
  return (
    <>
      <section className="cd-block" aria-labelledby="cd-hero">
        <h3 id="cd-hero" className="lg-label">
          What the ERP booked and what the document shows
        </h3>
        <div className="cd-hero">
          <DocumentPane model={model} onOpen={setOpen} />
          <Figures model={model} />
        </div>
      </section>
      <FindingCard view={view} />
      {open !== null && (
        <FileDialog key={open.file.id} file={open.file} locator={open.locator} onClose={() => setOpen(null)} />
      )}
    </>
  );
}
