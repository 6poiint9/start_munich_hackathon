'use client';

import {useEffect, useState} from 'react';

import {THEME_KEY, isThemeChoice} from '../lib/theme';
import type {ThemeChoice} from '../lib/theme';

const OPTIONS: {id: ThemeChoice; label: string}[] = [
  {id: 'light', label: 'Hell'},
  {id: 'dark', label: 'Dunkel'},
  {id: 'system', label: 'System'},
];

function readChoice(): ThemeChoice {
  const stored = (() => {
    try {
      return localStorage.getItem(THEME_KEY);
    } catch {
      return null;
    }
  })();
  if (isThemeChoice(stored)) {
    return stored;
  }
  const value = document.documentElement.dataset.theme ?? null;
  return isThemeChoice(value) ? value : 'system';
}

function apply(choice: ThemeChoice): void {
  const dark =
    choice === 'dark' ||
    (choice !== 'light' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = choice;
  document.documentElement.dataset.resolved = dark ? 'dark' : 'light';
  try {
    localStorage.setItem(THEME_KEY, choice);
  } catch {
    // The choice still applies until the next load.
  }
}

/** Hell, Dunkel or System. The choice stays in localStorage. */
export function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>('system');

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const sync = () => {
      const next = readChoice();
      setChoice(next);
      apply(next);
    };
    sync();
    media.addEventListener('change', sync);
    return () => media.removeEventListener('change', sync);
  }, []);

  return (
    <div className="lg-theme" role="group" aria-label="Farbschema">
      {OPTIONS.map((option) => (
        <button
          key={option.id}
          type="button"
          aria-pressed={choice === option.id}
          onClick={() => {
            apply(option.id);
            setChoice(option.id);
          }}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
