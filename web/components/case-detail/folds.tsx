'use client';

import type {ReactNode} from 'react';

import type {CaseView} from '../../lib/types';
import {actionStatusWord, actionTypeWord} from '../../lib/words';

import {EvidenceList} from '../evidence';
import {Mails} from '../mails';
import {Tag} from '../ui';

function Fold({title, count, children}: {title: string; count: number; children: ReactNode}) {
  return (
    <details className="cd-fold">
      <summary>
        <span>{title}</span>
        <span className="cd-fold-end">
          <span className="num">{count}</span>
          <i className="cd-chevron" aria-hidden="true" />
        </span>
      </summary>
      <div className="cd-fold-body">{children}</div>
    </details>
  );
}

/** Mails, actions and evidence, closed until the person opens them. */
export function Folds({view, live}: {view: CaseView; live: boolean}) {
  return (
    <div className="cd-folds">
      {view.emails.length > 0 && (
        <Fold title="Mails" count={view.emails.length}>
          <Mails view={view} live={live} />
        </Fold>
      )}
      {view.actions.length > 0 && (
        <Fold title="Actions" count={view.actions.length}>
          <ul className="cd-list">
            {view.actions.map((action) => (
              <li key={action.id} className="flex flex-wrap items-center gap-2">
                <span>{actionTypeWord(action.type ?? action.kind)}</span>
                {action.target !== null && <span className="lg-id">{action.target}</span>}
                <Tag>{actionStatusWord(action.status)}</Tag>
              </li>
            ))}
          </ul>
        </Fold>
      )}
      <Fold title="Documents and sources" count={view.evidence.length}>
        <EvidenceList evidence={view.evidence} />
      </Fold>
    </div>
  );
}
