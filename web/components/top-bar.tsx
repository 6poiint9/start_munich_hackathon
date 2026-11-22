'use client';

import * as api from '../lib/api';
import {formatCount, formatStamp} from '../lib/format';
import {storePersonId} from '../lib/use-person';
import {mailModeWord, roleWord} from '../lib/words';
import type {LineguardState} from '../lib/types';

import {useAction, usePage} from './page-context';
import {ThemeToggle} from './theme-toggle';
import {Button, ErrorNote} from './ui';

interface TopBarProps {
  state: LineguardState;
  mock: boolean;
  offline: string | null;
}

export function TopBar({state, mock, offline}: TopBarProps) {
  const {person, people, timezone} = usePage();
  const check = useAction();
  const {files_read: read, files_total: total, failed, manual} = state.import;
  const unread = [
    failed > 0 ? `${formatCount(failed)} fehlgeschlagen` : null,
    manual > 0 ? `${formatCount(manual)} von Hand zu prüfen` : null,
  ].filter((part) => part !== null);

  return (
    <header className="lg-top">
      <div className="lg-top-row">
        <div>
          <p className="lg-brand">
            Lineguard
            {state.customer !== null && <span className="lg-customer">{state.customer}</span>}
          </p>
          <p className="lg-stand">
            Stand <span className="lg-id">{formatStamp(state.at, timezone)}</span>
            {' · '}
            <span className="lg-id">{formatCount(read)}</span> von{' '}
            <span className="lg-id">{formatCount(total)}</span> Belegen gelesen
            {unread.length > 0 && <span className="lg-hot"> · {unread.join(', ')}</span>}
          </p>
        </div>
        <div className="lg-top-actions">
          <span className="lg-quiet">{mailModeWord(state.mail_mode)}</span>
          {mock && <span className="lg-quiet">Demo-Daten</span>}
          <ThemeToggle />
          <Button variant="primary" disabled={check.busy} onClick={() => void check.run(api.sync)}>
            {check.busy ? 'Prüfe …' : 'Jetzt prüfen'}
          </Button>
          <ErrorNote message={check.error} />
          <label className="lg-person">
            Angemeldet als
            <select
              value={person?.person_id ?? ''}
              onChange={(event) => storePersonId(event.target.value)}
              className="lg-select"
            >
              {person === null && <option value="">Person wählen …</option>}
              {people.map((entry) => (
                <option key={entry.person_id} value={entry.person_id}>
                  {entry.name}
                  {entry.roles.length > 0 && ` · ${entry.roles.map(roleWord).join(', ')}`}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      {offline !== null && (
        <p role="status" className="lg-offline">
          Keine Verbindung zum Server. Die Seite zeigt den letzten Stand und versucht es
          alle 5 Sekunden neu.
        </p>
      )}
    </header>
  );
}
