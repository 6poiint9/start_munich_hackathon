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
    <header className="sticky top-0 z-20 border-b border-rule-2 bg-paper">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2">
        <div className="flex items-baseline gap-2">
          <span className="text-lead font-semibold tracking-tight">Lineguard</span>
          {state.customer !== null && (
            <span className="text-body text-ink-3">{state.customer}</span>
          )}
        </div>
        <p className="text-meta text-ink-3">
          Stand <span className="num text-ink">{formatStamp(state.at, timezone)}</span>
        </p>
        <Tag tone={state.mail_mode === 'LIVE' ? 'work' : 'neutral'}>
          {mailModeWord(state.mail_mode)}
        </Tag>
        {mock && <Tag tone="wait">Demo-Daten</Tag>}
        <p className="text-meta text-ink-3">
          <span className="num text-ink">{formatCount(read)}</span> von{' '}
          <span className="num text-ink">{formatCount(total)}</span> Belegen gelesen
          {unread.length > 0 && <span className="text-stop"> · {unread.join(', ')}</span>}
        </p>
        <div className="flex items-center gap-2">
          <Button disabled={check.busy} onClick={() => void check.run(api.sync)}>
            {check.busy ? 'Prüfe …' : 'Jetzt prüfen'}
          </Button>
          <ErrorNote message={check.error} />
        </div>
        <label className="ml-auto flex items-center gap-2 text-meta text-ink-3">
          Angemeldet als
          <select
            value={person?.person_id ?? ''}
            onChange={(event) => storePersonId(event.target.value)}
            className="h-8 max-w-72 rounded-ctl border border-rule-2 bg-sheet px-2 text-body text-ink"
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
      {offline !== null && (
        <p role="status" className="border-t border-stop/30 bg-stop-wash px-4 py-1 text-meta text-stop">
          Keine Verbindung zum Server. Die Seite zeigt den letzten Stand und versucht es
          alle 5 Sekunden neu.
        </p>
      )}
    </header>
  );
}
