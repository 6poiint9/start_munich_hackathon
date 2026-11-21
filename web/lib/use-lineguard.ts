'use client';

import {useCallback, useEffect, useRef, useState} from 'react';

import * as api from './api';
import {errorMessage} from './errors';
import type {CaseView, LineguardState, LogEvent} from './types';

const POLL_MS = 5000;
const EVENT_LIMIT = 50;

export interface Lineguard {
  state: LineguardState | null;
  view: CaseView | null;
  events: LogEvent[];
  selectedId: number | null;
  mock: boolean;
  /** A German sentence while the server does not answer. */
  offline: string | null;
  select: (id: number) => void;
  reload: () => Promise<void>;
}

/** Loads the state, the selected case and the log, and polls them. */
export function useLineguard(): Lineguard {
  const [state, setState] = useState<LineguardState | null>(null);
  const [view, setView] = useState<CaseView | null>(null);
  const [events, setEvents] = useState<LogEvent[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [mock, setMock] = useState(api.isMock());
  const [offline, setOffline] = useState<string | null>(null);
  const selected = useRef<number | null>(null);
  const loaded = useRef(false);

  const loadCase = useCallback(async (id: number) => {
    try {
      const next = await api.getCase(id);
      // The answer of a case that is no longer selected is dropped.
      if (selected.current === id) {
        setView(next);
      }
    } catch {
      // The old case stays on the page. The state poll reports the outage.
    }
  }, []);

  const reload = useCallback(async () => {
    let next: LineguardState;
    try {
      next = await api.getState();
    } catch (error) {
      if (loaded.current || api.isMock()) {
        setOffline(errorMessage(error));
        return;
      }
      api.enableMock();
      setMock(true);
      next = await api.getState();
    }
    loaded.current = true;
    setOffline(null);
    setState(next);
    const ids = [...next.cases_now, ...next.cases_later].map((entry) => entry.id);
    const current = selected.current;
    const id = current !== null && ids.includes(current) ? current : ids[0];
    selected.current = id ?? null;
    setSelectedId(id ?? null);
    if (id === undefined) {
      setView(null);
    }
    await Promise.all([
      id === undefined ? undefined : loadCase(id),
      api
        .getEvents(EVENT_LIMIT)
        .then(setEvents)
        .catch(() => undefined),
    ]);
  }, [loadCase]);

  useEffect(() => {
    const first = window.setTimeout(() => void reload(), 0);
    const timer = window.setInterval(() => void reload(), POLL_MS);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [reload]);

  const select = useCallback(
    (id: number) => {
      selected.current = id;
      setSelectedId(id);
      void loadCase(id);
    },
    [loadCase],
  );

  return {state, view, events, selectedId, mock, offline, select, reload};
}
