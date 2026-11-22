'use client';

import {useEffect, useRef, useState} from 'react';

import * as api from '../lib/api';
import {errorMessage} from '../lib/errors';
import {formatCount, formatDate} from '../lib/format';
import type {Evidence, EvidenceFile} from '../lib/types';
import {locatorWord, readerWord, sourceRankWord} from '../lib/words';

import {usePage} from './page-context';
import {Button, Tag} from './ui';

/** Ranks 1 and 2 are documents. They prove more than a booking. */
const DOCUMENT_RANK = 2;

function factValue(fact: Evidence): string {
  if (fact.qty !== null) {
    return formatCount(fact.qty);
  }
  if (fact.value_num !== null) {
    return formatCount(fact.value_num);
  }
  return fact.value_text ?? '–';
}

function factNotes(fact: Evidence, timezone: string): string[] {
  return [
    fact.rev === null ? null : `Rev. ${fact.rev}`,
    fact.batch === null ? null : `Batch ${fact.batch}`,
    fact.ref === null ? null : `Ref. ${fact.ref}`,
    fact.as_of === null ? null : `As of ${formatDate(fact.as_of, timezone)}`,
    fact.doc_date === null ? null : `Document dated ${formatDate(fact.doc_date, timezone)}`,
    fact.valid_until === null ? null : `valid until ${formatDate(fact.valid_until, timezone)}`,
  ].filter((note) => note !== null);
}

interface FileDialogProps {
  file: EvidenceFile;
  locator: string | null;
  onClose: () => void;
}

export function FileDialog({file, locator, onClose}: FileDialogProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const kind = api.fileKind(file.path);
  const url = api.fileUrl(file);
  const name = file.path ?? `File ${file.id}`;

  useEffect(() => {
    const element = dialog.current;
    if (element !== null && !element.open) {
      element.showModal();
    }
  }, []);

  useEffect(() => {
    if (kind !== 'text') {
      return;
    }
    let current = true;
    api
      .getFileText(file)
      .then((loaded) => {
        if (current) {
          setText(loaded);
        }
      })
      .catch((caught: unknown) => {
        if (current) {
          setError(errorMessage(caught));
        }
      });
    return () => {
      current = false;
    };
  }, [file, kind]);

  return (
    <dialog
      ref={dialog}
      aria-label={`Document ${name}`}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialog.current) {
          dialog.current.close();
        }
      }}
      className="file-panel m-0 ml-auto h-dvh max-h-none w-[min(760px,100vw)] max-w-none border-l border-ink bg-paper p-0 text-ink"
    >
      <div className="flex h-full flex-col">
        <header className="flex items-start justify-between gap-3 border-b border-rule px-4 py-3">
          <div className="min-w-0">
            <p className="field-name">Document</p>
            <h2 className="num text-body font-medium break-all">{name}</h2>
            {locator !== null && <p className="text-meta text-ink-3">Found at: {locatorWord(locator)}</p>}
          </div>
          <Button autoFocus onClick={() => dialog.current?.close()}>
            Close
          </Button>
        </header>
        <div className="min-h-0 flex-1 overflow-auto bg-well p-4">
          {kind === 'image' && (
            // The file comes from the API at run time. next/image cannot size it.
            // eslint-disable-next-line @next/next/no-img-element
            <img src={url} alt={`Document ${name}`} className="mx-auto max-w-full border border-rule-2 bg-white" />
          )}
          {kind === 'pdf' && <iframe src={url} title={`Document ${name}`} className="h-full w-full border border-rule-2 bg-white" />}
          {kind === 'binary' && (
            <p>
              The page cannot show this file format.{' '}
              <a href={url} target="_blank" rel="noreferrer" className="lg-link">
                Download the file
              </a>
            </p>
          )}
          {kind === 'text' &&
            (error !== null ? (
              <p role="alert" className="text-stop">
                The file did not load. {error}
              </p>
            ) : text === null ? (
              <p className="text-ink-3">Loading the file …</p>
            ) : (
              <pre className="num overflow-auto rounded-ctl border border-rule-2 bg-white p-3 text-meta whitespace-pre">
                {text}
              </pre>
            ))}
        </div>
      </div>
    </dialog>
  );
}

interface OpenFile {
  file: EvidenceFile;
  locator: string | null;
}

export function EvidenceList({evidence}: {evidence: Evidence[]}) {
  const {timezone} = usePage();
  const [open, setOpen] = useState<OpenFile | null>(null);

  return (
    <div>
      {evidence.length === 0 ? (
        <p className="text-ink-3">This case has no document.</p>
      ) : (
        <ul className="divide-y divide-rule">
          {evidence.map((fact) => {
            const notes = factNotes(fact, timezone);
            const strong = fact.source_rank !== null && fact.source_rank <= DOCUMENT_RANK;
            return (
              <li key={fact.fact_id} className="grid gap-x-4 gap-y-1 py-3 first:pt-0 sm:grid-cols-[minmax(0,1fr)_auto]">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{fact.label}</span>
                    <Tag tone={strong ? 'go' : 'neutral'}>{sourceRankWord(fact.source_rank)}</Tag>
                    {fact.suspicious && <Tag tone="stop">Does not fit</Tag>}
                  </p>
                  {notes.length > 0 && <p className="text-meta text-ink-3">{notes.join(' · ')}</p>}
                  {fact.file !== null ? (
                    <button
                      type="button"
                      onClick={() => fact.file !== null && setOpen({file: fact.file, locator: fact.locator})}
                      className="lg-link mt-0.5 max-w-full text-meta"
                    >
                      <span className="lg-id break-all">{fact.file.path ?? `File ${fact.file.id}`}</span>
                      {fact.locator !== null && <span> · {locatorWord(fact.locator)}</span>}
                      <span className="sr-only"> open</span>
                    </button>
                  ) : (
                    fact.locator !== null && <p className="text-meta text-ink-3">{locatorWord(fact.locator)}</p>
                  )}
                </div>
                <div className="sm:text-right">
                  <p className={fact.suspicious ? 'num text-lead font-medium text-stop' : 'num text-lead font-medium'}>
                    {factValue(fact)}
                  </p>
                  {fact.extracted_by !== null && (
                    <p className="text-cap text-ink-3">read by: {readerWord(fact.extracted_by).toLowerCase()}</p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {open !== null && (
        <FileDialog key={open.file.id} file={open.file} locator={open.locator} onClose={() => setOpen(null)} />
      )}
    </div>
  );
}
