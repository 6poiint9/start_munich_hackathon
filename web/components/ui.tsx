'use client';

import {useId, useState} from 'react';
import type {ButtonHTMLAttributes, FormEvent, ReactNode} from 'react';

import {formatClock, formatDistance, isPast} from '../lib/format';
import {roleWord} from '../lib/words';
import type {Tone} from '../lib/words';

import {usePage} from './page-context';

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ');
}

const TONE_CLASSES: Record<Tone, string> = {
  neutral: 'border-rule-2 bg-well text-ink-2',
  go: 'border-go/30 bg-go-wash text-go',
  work: 'border-work/30 bg-work-wash text-stamp-deep',
  wait: 'border-wait/30 bg-wait-wash text-wait',
  stop: 'border-stop/30 bg-stop-wash text-stop',
};

interface TagProps {
  tone?: Tone;
  children: ReactNode;
}

/** A small badge. The word carries the meaning, the color repeats it. */
export function Tag({tone = 'neutral', children}: TagProps) {
  return (
    <span
      className={cx(
        'inline-flex shrink-0 items-center rounded-tag border px-1.5 text-cap font-medium whitespace-nowrap',
        TONE_CLASSES[tone],
      )}
    >
      {children}
    </span>
  );
}

type ButtonVariant = 'primary' | 'secondary' | 'danger';

const BUTTON_CLASSES: Record<ButtonVariant, string> = {
  primary:
    'border-stamp bg-stamp text-white hover:bg-stamp-deep disabled:border-rule-2 disabled:bg-well disabled:text-ink-4',
  secondary:
    'border-rule-2 bg-sheet text-ink hover:bg-well disabled:text-ink-4',
  danger:
    'border-rule-2 bg-sheet text-stop hover:bg-stop-wash disabled:text-ink-4',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  large?: boolean;
}

export function Button({
  variant = 'secondary',
  large = false,
  className,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cx(
        'press inline-flex items-center justify-center rounded-ctl border font-medium whitespace-nowrap',
        large ? 'h-10 px-5 text-lead' : 'h-8 px-3 text-body',
        BUTTON_CLASSES[variant],
        className,
      )}
      {...rest}
    />
  );
}

interface CardProps {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
}

/** A titled section of the case detail. */
export function Card({title, aside, children}: CardProps) {
  return (
    <section className="rounded-sheet border border-rule bg-sheet">
      <header className="flex items-center justify-between gap-3 border-b border-rule px-4 py-2">
        <h3 className="field-name">{title}</h3>
        {aside}
      </header>
      <div className="px-4 py-3">{children}</div>
    </section>
  );
}

/** An error of a write call, next to its button. */
export function ErrorNote({message}: {message: string | null}) {
  if (message === null) {
    return null;
  }
  return (
    <p
      role="alert"
      className="rounded-ctl border border-stop/30 bg-stop-wash px-2 py-1 text-meta text-stop"
    >
      <span className="font-medium">Nicht ausgeführt: </span>
      {message}
    </p>
  );
}

interface ClockProps {
  iso: string | null;
  /** Adds the distance to now: "in 4 h". */
  distance?: boolean;
}

/** A moment in the zone of the state. A past moment is muted and marked. */
export function Clock({iso, distance = false}: ClockProps) {
  const {timezone, now} = usePage();
  if (iso === null) {
    return <span className="text-ink-4">–</span>;
  }
  const past = isPast(iso, now);
  const away = distance && !past ? formatDistance(iso, now) : null;
  return (
    <span className={cx('whitespace-nowrap', past && 'text-ink-4')}>
      <time dateTime={iso} className="num">
        {formatClock(iso, timezone, now)}
      </time>
      {away !== null && <span className="text-ink-3"> ({away})</span>}
      {past && (
        <span className="ml-1 rounded-tag border border-rule-2 px-1 text-cap font-medium">
          überfällig
        </span>
      )}
    </span>
  );
}

interface ApproverNoteProps {
  roles: string[];
  name?: string | null;
}

/** Says who must approve when the selected person cannot. */
export function ApproverNote({roles, name = null}: ApproverNoteProps) {
  const {person, people} = usePage();
  if (person === null) {
    return (
      <p className="text-meta text-ink-3">
        Wähle oben unter „Angemeldet als“ eine Person, um freizugeben.
      </p>
    );
  }
  const holders = people
    .filter((entry) => roles.some((role) => entry.roles.includes(role)))
    .map((entry) => entry.name);
  const names = name !== null ? [name] : holders.slice(0, 3);
  return (
    <p className="text-meta text-ink-3">
      Freigabe nur durch{' '}
      <span className="font-medium text-ink-2">
        {roles.map(roleWord).join(' oder ') || 'eine berechtigte Person'}
      </span>
      {names.length > 0 && ` (${names.join(', ')})`}. {person.name} hat diese
      Rolle nicht.
    </p>
  );
}

interface RejectFormProps {
  label: string;
  busy: boolean;
  onReject: (reason: string) => void;
}

/** "Ablehnen" with a required reason. The form opens in place. */
export function RejectForm({label, busy, onReject}: RejectFormProps) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const inputId = useId();

  if (!open) {
    return (
      <Button variant="danger" disabled={busy} onClick={() => setOpen(true)}>
        {label}
      </Button>
    );
  }
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (reason.trim() !== '') {
      onReject(reason.trim());
      setOpen(false);
      setReason('');
    }
  };
  return (
    <form onSubmit={submit} className="flex w-full flex-wrap items-end gap-2">
      <div className="min-w-48 flex-1">
        <label htmlFor={inputId} className="field-name block">
          Grund der Ablehnung (Pflicht)
        </label>
        <input
          id={inputId}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          required
          autoFocus
          className="mt-1 h-8 w-full rounded-ctl border border-rule-2 bg-well px-2 text-body"
        />
      </div>
      <Button type="submit" variant="danger" disabled={busy || reason.trim() === ''}>
        {label} bestätigen
      </Button>
      <Button onClick={() => setOpen(false)}>Abbrechen</Button>
    </form>
  );
}
