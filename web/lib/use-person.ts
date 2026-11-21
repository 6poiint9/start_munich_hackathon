'use client';

import {useSyncExternalStore} from 'react';

const STORAGE_KEY = 'lineguard.person';
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener('storage', listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener('storage', listener);
  };
}

function read(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/** Stores the person of "Angemeldet als" in the browser. */
export function storePersonId(personId: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, personId);
  } catch {
    // A browser without storage keeps the choice until the next load.
  }
  for (const listener of listeners) {
    listener();
  }
}

/** The stored `person_id`, or `null` before a person was chosen. */
export function usePersonId(): string | null {
  return useSyncExternalStore(subscribe, read, () => null);
}
