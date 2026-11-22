'use client';

import type {ReactNode} from 'react';

import type {CaseView} from '../../lib/types';
import {actionStatusWord, actionTypeWord} from '../../lib/words';

import {EvidenceList} from '../evidence';
import {Mails} from '../mails';
import {Tag} from '../ui';

function Fold({title, count, children}: {title: string; count: number; children: ReactNode}) {
  return (
    <details className="lg-fold lg-on-card">
      <summary>
        <span className="lg-fold-name">{title}</span>
        <span className="lg-fold-end">
          <span className="lg-count">{count}</span>
          <i className="lg-chevron" aria-hidden="true" />
        </span>
      </summary>
      <div className="lg-fold-body">{children}</div>
    </details>
  );
}

/** Mails, actions and evidence, closed until the person opens them. */
export function Folds({view, live}: {view: CaseView; live: boolean}) {
  return (
    <div className="lg-folds">
      {view.emails.length > 0 && (
        <Fold title="Mails" count={view.emails.length}>
          <div className="lg-mail-slot">
            <Mails view={view} live={live} />
          </div>
        </Fold>
      )}
      {view.actions.length > 0 && (
        <Fold title="Aktionen" count={view.actions.length}>
          <ul className="lg-action-list">
            {view.actions.map((action) => (
              <li key={action.id}>
                <span>{actionTypeWord(action.type ?? action.kind)}</span>
                {action.target !== null && <span className="lg-id">{action.target}</span>}
                <Tag>{actionStatusWord(action.status)}</Tag>
              </li>
            ))}
          </ul>
        </Fold>
      )}
      <Fold title="Belege" count={view.evidence.length}>
        <div className="lg-evidence-slot">
          <EvidenceList evidence={view.evidence} />
        </div>
      </Fold>
    </div>
  );
}
