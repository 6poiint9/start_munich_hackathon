'use client';

import {createContext, useCallback, useContext, useState} from 'react';

import {errorMessage} from '../lib/errors';
import type {Labels, Person} from '../lib/types';

export interface PageContextValue {
  timezone: string;
  /** The clock of the state. Every "past" on the page compares with it. */
  now: string | null;
  labels: Labels;
  people: Person[];
  person: Person | null;
  reload: () => Promise<void>;
}

const PageContext = createContext<PageContextValue | null>(null);

export const PageProvider = PageContext.Provider;

export function usePage(): PageContextValue {
  const value = useContext(PageContext);
  if (value === null) {
    throw new Error('usePage needs a PageProvider');
  }
  return value;
}

/** True when the person holds one of the roles. No roles means no limit. */
export function holdsRole(person: Person | null, roles: string[]): boolean {
  if (person === null) {
    return false;
  }
  return roles.length === 0 || roles.some((role) => person.roles.includes(role));
}

export interface ActionState {
  busy: boolean;
  error: string | null;
  run: (call: (personId: string | null) => Promise<unknown>) => Promise<void>;
}

/** Runs a write call, shows its error and reloads the page data. */
export function useAction(): ActionState {
  const {person, reload} = usePage();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const personId = person?.person_id ?? null;

  const run = useCallback<ActionState['run']>(
    async (call) => {
      setBusy(true);
      setError(null);
      try {
        await call(personId);
      } catch (caught) {
        setError(errorMessage(caught));
      }
      await reload();
      setBusy(false);
    },
    [personId, reload],
  );

  return {busy, error, run};
}
