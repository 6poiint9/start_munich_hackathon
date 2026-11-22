'use client';

import {useId, useState} from 'react';

import * as api from '../lib/api';
import {formatClock} from '../lib/format';
import type {CaseView, Email} from '../lib/types';
import {emailStatusTone, emailStatusWord, languageWord} from '../lib/words';

import {holdsRole, useAction, usePage} from './page-context';
import {ApproverNote, Button, ErrorNote, Tag} from './ui';

const FIELD_CLASS = 'mt-1 w-full rounded-ctl border border-rule-2 bg-sheet px-2 py-1 text-body';

function mailRoles(view: CaseView): string[] {
  const roles = view.decisions.flatMap((decision) =>
    decision.needs_roles.length > 0
      ? decision.needs_roles
      : decision.approver_role === null
        ? []
        : [decision.approver_role],
  );
  return [...new Set(roles)];
}

interface DraftProps {
  email: Email;
  roles: string[];
  live: boolean;
}

function Draft({email, roles, live}: DraftProps) {
  const {person} = usePage();
  const action = useAction();
  const [subject, setSubject] = useState(email.subject ?? '');
  const [body, setBody] = useState(email.body ?? '');
  const subjectId = useId();
  const bodyId = useId();
  const allowed = holdsRole(person, roles);

  return (
    <li className="space-y-2 py-3 first:pt-0">
      <div className="flex flex-wrap items-center gap-2 text-meta text-ink-2">
        <Tag tone="wait">{emailStatusWord(email.status)}</Tag>
        {email.commits_money && <Tag tone="stop">Commits the company to pay</Tag>}
        <span>
          To <span className="font-medium text-ink">{email.to_addr ?? 'unknown'}</span>
        </span>
        <span>{languageWord(email.language)}</span>
      </div>
      {email.reason !== null && <p className="text-meta text-ink-3">{email.reason}</p>}
      <div>
        <label htmlFor={subjectId} className="field-name">
          Subject
        </label>
        <input
          id={subjectId}
          value={subject}
          readOnly={!allowed}
          onChange={(event) => setSubject(event.target.value)}
          className={`${FIELD_CLASS} h-8`}
        />
      </div>
      <div>
        <label htmlFor={bodyId} className="field-name">
          Text
        </label>
        <textarea
          id={bodyId}
          value={body}
          readOnly={!allowed}
          rows={Math.min(Math.max(body.split('\n').length + 1, 4), 14)}
          onChange={(event) => setBody(event.target.value)}
          className={`${FIELD_CLASS} leading-5`}
        />
      </div>
      {allowed ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="primary"
            disabled={action.busy}
            onClick={() =>
              void action.run((personId) => api.approveEmail(email.id, {subject, body}, personId))
            }
          >
            {live ? 'Approve and send' : 'Approve'}
          </Button>
          <Button
            disabled={action.busy}
            onClick={() => void action.run((personId) => api.discardEmail(email.id, personId))}
          >
            Discard
          </Button>
          {!live && (
            <span className="text-meta text-ink-3">
              Mail mode is &quot;log only&quot;. Lineguard writes the mail to the log and sends nothing.
            </span>
          )}
        </div>
      ) : (
        <ApproverNote roles={roles} />
      )}
      <ErrorNote message={action.error} />
    </li>
  );
}

function ThreadMail({email}: {email: Email}) {
  const {timezone} = usePage();
  const incoming = email.direction === 'in';
  const moment = email.sent_at ?? email.created_at;
  return (
    <li className={incoming ? 'border-l border-ink py-2 pl-3' : 'border-l border-rule-2 py-2 pl-3'}>
      <div className="flex flex-wrap items-center gap-2 text-meta text-ink-2">
        <span className="font-medium text-ink">
          {incoming ? `From ${email.from_addr ?? 'unknown'}` : `To ${email.to_addr ?? 'unknown'}`}
        </span>
        <Tag tone={emailStatusTone(email.status)}>{emailStatusWord(email.status)}</Tag>
        {email.commits_money && <Tag tone="stop">Commits the company to pay</Tag>}
        {moment !== null && <span className="num">{formatClock(moment, timezone, null)}</span>}
      </div>
      <p className="mt-1 font-medium">{email.subject ?? '(no subject)'}</p>
      {email.body !== null && (
        <p className="mt-1 max-h-48 max-w-[80ch] overflow-auto whitespace-pre-wrap text-ink-2">{email.body}</p>
      )}
      {email.status === 'failed' && (
        <p className="mt-1 text-stop">Mail delivery could not be confirmed. Check the mailbox before sending again.</p>
      )}
    </li>
  );
}

export function Mails({view, live}: {view: CaseView; live: boolean}) {
  if (view.emails.length === 0) {
    return null;
  }
  const roles = mailRoles(view);
  const drafts = view.emails.filter((email) => email.status === 'draft');
  const thread = view.emails.filter((email) => email.status !== 'draft');
  return (
    <div>
      {drafts.length > 0 && (
        <ul className="divide-y divide-rule">
          {drafts.map((email) => (
            <Draft key={email.id} email={email} roles={roles} live={live} />
          ))}
        </ul>
      )}
      {thread.length > 0 && (
        <>
          {drafts.length > 0 && <p className="field-name mt-2 border-t border-rule pt-3">Sent and received</p>}
          <ul className="mt-1 space-y-2">
            {thread.map((email) => (
              <ThreadMail key={email.id} email={email} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
