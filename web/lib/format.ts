/**
 * German formats for numbers, money and times.
 *
 * Every function accepts `null` and returns a dash, so a field that the
 * backend did not send never breaks a line of the page.
 */

const LOCALE = 'de-DE';
const DASH = '–';
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;
const HAS_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i;
const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;
/** Inside this distance a weekday names exactly one day. */
const WEEKDAY_IS_CLEAR_MS = 6 * DAY_MS;

const countFormat = new Intl.NumberFormat(LOCALE, {maximumFractionDigits: 1});
const signedFormat = new Intl.NumberFormat(LOCALE, {
  maximumFractionDigits: 1,
  signDisplay: 'exceptZero',
});
const wholeMoneyFormat = new Intl.NumberFormat(LOCALE, {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
});
const centMoneyFormat = new Intl.NumberFormat(LOCALE, {
  style: 'currency',
  currency: 'EUR',
});
const percentFormat = new Intl.NumberFormat(LOCALE, {
  style: 'percent',
  maximumFractionDigits: 1,
});

/** `1234.5` becomes `1.234,5`. */
export function formatCount(value: number | null): string {
  return value === null ? DASH : countFormat.format(value);
}

/** `110` becomes `+110`, `-900` becomes `-900`. */
export function formatSigned(value: number | null): string {
  return value === null ? DASH : signedFormat.format(value);
}

/** `16800` becomes `16.800 €`. Cents show only when the amount has cents. */
export function formatMoney(value: number | null): string {
  if (value === null) {
    return DASH;
  }
  const format = Number.isInteger(value) ? wholeMoneyFormat : centMoneyFormat;
  return format.format(value);
}

/** `0.929` becomes `92,9 %`. */
export function formatPercent(ratio: number | null): string {
  return ratio === null ? DASH : percentFormat.format(ratio);
}

/** The distance between two ratios in percentage points: `15,7`. */
export function formatPoints(ratioDistance: number): string {
  return countFormat.format(Math.abs(ratioDistance) * 100);
}

/** Reads an ISO text. A text without a zone counts as UTC. */
export function parseInstant(iso: string | null): Date | null {
  if (iso === null) {
    return null;
  }
  let text = iso.trim().replace(' ', 'T');
  if (DATE_ONLY.test(text)) {
    text = `${text}T12:00:00Z`;
  } else if (!HAS_ZONE.test(text)) {
    text = `${text}Z`;
  }
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : date;
}

interface ClockParts {
  weekday: string;
  day: string;
  month: string;
  year: string;
  hour: string;
  minute: string;
}

const clockFormats = new Map<string, Intl.DateTimeFormat>();

function clockFormat(timezone: string): Intl.DateTimeFormat {
  const known = clockFormats.get(timezone);
  if (known) {
    return known;
  }
  const options: Intl.DateTimeFormatOptions = {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  };
  let format: Intl.DateTimeFormat;
  try {
    format = new Intl.DateTimeFormat(LOCALE, {...options, timeZone: timezone});
  } catch {
    // The browser does not know the zone of the customer pack.
    format = new Intl.DateTimeFormat(LOCALE, {...options, timeZone: 'UTC'});
  }
  clockFormats.set(timezone, format);
  return format;
}

function clockParts(date: Date, timezone: string): ClockParts {
  const found = new Map<string, string>();
  for (const part of clockFormat(timezone).formatToParts(date)) {
    found.set(part.type, part.value);
  }
  return {
    weekday: (found.get('weekday') ?? '').replace('.', ''),
    day: found.get('day') ?? '',
    month: found.get('month') ?? '',
    year: found.get('year') ?? '',
    hour: found.get('hour') ?? '',
    minute: found.get('minute') ?? '',
  };
}

/**
 * A moment as a clock time with weekday: `So 11:27`.
 *
 * The date is added (`Fr 12.03. 16:00`) when the moment is so far from `now`
 * that the weekday alone is not clear. A text with only a date has no time.
 */
export function formatClock(
  iso: string | null,
  timezone: string,
  now: string | null,
): string {
  const date = parseInstant(iso);
  if (iso === null || date === null) {
    return DASH;
  }
  if (DATE_ONLY.test(iso.trim())) {
    const parts = clockParts(date, 'UTC');
    return `${parts.weekday} ${parts.day}.${parts.month}.`;
  }
  const parts = clockParts(date, timezone);
  const reference = parseInstant(now);
  const weekdayIsClear =
    reference !== null &&
    Math.abs(date.getTime() - reference.getTime()) < WEEKDAY_IS_CLEAR_MS;
  const time = `${parts.hour}:${parts.minute}`;
  return weekdayIsClear
    ? `${parts.weekday} ${time}`
    : `${parts.weekday} ${parts.day}.${parts.month}. ${time}`;
}

/** A moment with weekday, date and time: `Mo 01.03. 08:00`. */
export function formatStamp(iso: string | null, timezone: string): string {
  return formatClock(iso, timezone, null);
}

/** A calendar date: `28.02.2027`. */
export function formatDate(iso: string | null, timezone: string): string {
  const date = parseInstant(iso);
  if (iso === null || date === null) {
    return DASH;
  }
  const zone = DATE_ONLY.test(iso.trim()) ? 'UTC' : timezone;
  const parts = clockParts(date, zone);
  return `${parts.day}.${parts.month}.${parts.year}`;
}

/** True when `iso` lies before `now`. Unknown moments are never past. */
export function isPast(iso: string | null, now: string | null): boolean {
  const date = parseInstant(iso);
  const reference = parseInstant(now);
  if (iso === null || date === null || reference === null) {
    return false;
  }
  if (DATE_ONLY.test(iso.trim())) {
    return reference.getTime() - date.getTime() > DAY_MS / 2;
  }
  return date.getTime() < reference.getTime();
}

/** A length of time in two units at most: `2 T 3 h`, `1 h 50 min`, `12 min`. */
export function formatDuration(milliseconds: number): string {
  const total = Math.abs(milliseconds);
  const days = Math.floor(total / DAY_MS);
  const hours = Math.floor((total % DAY_MS) / HOUR_MS);
  const minutes = Math.floor((total % HOUR_MS) / MINUTE_MS);
  if (days > 0) {
    return hours > 0 ? `${days} T ${hours} h` : `${days} T`;
  }
  if (hours > 0) {
    return minutes > 0 ? `${hours} h ${minutes} min` : `${hours} h`;
  }
  return `${Math.max(minutes, 1)} min`;
}

/** The time from `now` to `iso`: `in 2 T 3 h` or `seit 1 h 50 min`. */
export function formatDistance(
  iso: string | null,
  now: string | null,
): string | null {
  const date = parseInstant(iso);
  const reference = parseInstant(now);
  if (date === null || reference === null) {
    return null;
  }
  const distance = date.getTime() - reference.getTime();
  const length = formatDuration(distance);
  return distance >= 0 ? `in ${length}` : `seit ${length}`;
}

/** The age of something that began at `iso`: `1 h 50 min`. */
export function formatAge(iso: string | null, now: string | null): string | null {
  const date = parseInstant(iso);
  const reference = parseInstant(now);
  if (date === null || reference === null) {
    return null;
  }
  return formatDuration(Math.max(reference.getTime() - date.getTime(), 0));
}

/** German plural: `plural(1, 'Fall', 'Fälle')` gives `1 Fall`. */
export function plural(count: number, one: string, many: string): string {
  return `${formatCount(count)} ${count === 1 ? one : many}`;
}
