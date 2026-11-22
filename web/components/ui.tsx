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

const TONE_DOTS: Record<Tone, string | null> = {
  neutral: null,
  go: 'bg-go-fill',
  work: 'bg-work-fill',
  wait: 'bg-wait-fill',
  stop: 'bg-stop-fill',
};

const TONE_PILLS: Record<Tone, string> = {
  neutral: 'bg-ink/5 text-ink-2',
  go: 'bg-go-wash text-go',
  work: 'bg-work-wash text-work',
  wait: 'bg-wait-wash text-wait',
  stop: 'bg-stop-wash text-stop',
};

interface TagProps {
  tone?: Tone;
  children: ReactNode;
}

/** A small outlined badge. The word carries the meaning, the dot repeats it. */
export function Tag({tone = 'neutral', children}: TagProps) {
  const dot = TONE_DOTS[tone];
  return (
    <span
      className={cx(
        'inline-flex h-[24px] shrink-0 items-center gap-1.5 rounded-full px-2.5 text-meta font-medium whitespace-nowrap',
        TONE_PILLS[tone],
      )}
    >
      {dot !== null && <span aria-hidden="true" className={cx('size-1.5 rounded-full', dot)} />}
      {children}
    </span>
  );
}

type ButtonVariant = 'primary' | 'secondary' | 'danger';

const BUTTON_CLASSES: Record<ButtonVariant, string> = {
  primary:
    'border-ink bg-ink text-paper hover:bg-stamp-deep disabled:border-transparent disabled:bg-well disabled:text-ink-4',
  secondary:
    'border-rule-2 bg-transparent text-ink hover:border-ink disabled:border-rule disabled:text-ink-4',
  danger:
    'border-rule-2 bg-transparent text-stop hover:border-stop disabled:border-rule disabled:text-ink-4',
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
        large ? 'h-12 rounded-[12px] px-6 text-lead' : 'h-9 px-4 text-body',
        BUTTON_CLASSES[variant],
        className,
      )}
      {...rest}
    />
  );
}

/** An error of a write call, next to its button. */
export function ErrorNote({message}: {message: string | null}) {
  if (message === null) {
    return null;
  }
  return (
    <p role="alert" className="border-l border-stop pl-3 text-meta text-stop">
      <span className="font-medium">Not done. </span>
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
    <span className="whitespace-nowrap">
      <time dateTime={iso} className={cx('num', past && 'text-ink-3')}>
        {formatClock(iso, timezone, now)}
      </time>
      {away !== null && <span className="font-normal text-ink-3"> ({away})</span>}
      {past && <span className="font-normal text-stop"> overdue</span>}
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
        Select a person under &quot;Acting as&quot; to approve or reject.
      </p>
    );
  }
  const holders = people
    .filter((entry) => roles.some((role) => entry.roles.includes(role)))
    .map((entry) => entry.name);
  const names = name !== null ? [name] : holders.slice(0, 3);
  return (
    <p className="text-meta text-ink-3">
      Only {roles.map(roleWord).join(' or ') || 'a person with the right role'}
      {names.length > 0 && ` (${names.join(', ')})`} can approve this. {person.name} does not
      have this role.
    </p>
  );
}

interface RejectFormProps {
  label: string;
  busy: boolean;
  onReject: (reason: string) => void;
}

/** "Reject" with a required reason. The form opens in place. */
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
          Reason (required)
        </label>
        <input
          id={inputId}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          required
          autoFocus
          className="mt-1 h-9 w-full rounded-ctl border border-rule-2 bg-sheet px-2 text-body"
        />
      </div>
      <Button type="submit" variant="danger" disabled={busy || reason.trim() === ''}>
        Confirm
      </Button>
      <Button onClick={() => setOpen(false)}>Cancel</Button>
    </form>
  );
}
