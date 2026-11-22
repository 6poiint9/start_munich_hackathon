'use client';

import * as api from '../lib/api';
import {formatCount, formatStamp} from '../lib/format';
import {storePersonId} from '../lib/use-person';
import {mailModeWord, roleWord} from '../lib/words';
import type {LineguardState} from '../lib/types';

import {useAction, usePage} from './page-context';
import {Button, ErrorNote, Tag} from './ui';

interface TopBarProps {
  state: LineguardState;
  mock: boolean;
  offline: string | null;
  current: string;
}

export function TopBar({state, mock, offline, current}: TopBarProps) {
  const {person, people, timezone} = usePage();
  const check = useAction();
  const {files_read: read, files_total: total, failed, manual} = state.import;
  const unread = [
    failed > 0 ? `${formatCount(failed)} failed` : null,
    manual > 0 ? `${formatCount(manual)} need a manual check` : null,
  ].filter((part) => part !== null);

  return (
    <header className="lg-top">
      <div className="lg-wrap lg-top-row">
        <p className="dashboard-crumb">Workspace <span>/</span> <strong>{current}</strong></p>
        <p className="lg-top-meta">
          As of <span className="num">{formatStamp(state.at, timezone)}</span>
          {' · '}
          <span className="num">
            {formatCount(read)} of {formatCount(total)}
          </span>{' '}
          documents read
          {unread.length > 0 && <span className="lg-hot"> · {unread.join(', ')}</span>}
        </p>
        <div className="lg-top-actions">
          {mock && <Tag>Demo data</Tag>}
          <Tag tone={state.mail_mode === 'LIVE' ? 'go' : 'neutral'}>
            {mailModeWord(state.mail_mode)}
          </Tag>
          <label className="lg-person">
            Acting as
            <select
              value={person?.person_id ?? ''}
              onChange={(event) => storePersonId(event.target.value)}
              className="lg-select"
              data-empty={person === null}
            >
              {person === null && <option value="">Select a person …</option>}
              {people.map((entry) => (
                <option key={entry.person_id} value={entry.person_id}>
                  {entry.name}
                  {entry.roles.length > 0 && ` · ${entry.roles.map(roleWord).join(', ')}`}
                </option>
              ))}
            </select>
          </label>
          <Button disabled={check.busy} onClick={() => void check.run(api.sync)}>
            {check.busy ? 'Checking …' : 'Check sources now'}
          </Button>
          <ErrorNote message={check.error} />
        </div>
      </div>
      {offline !== null && (
        <p role="status" className="lg-wrap lg-offline">
          No connection to the server. The page shows the last known state and tries again
          every 5 seconds.
        </p>
      )}
    </header>
  );
}
