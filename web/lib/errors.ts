/** An answer of the API with an HTTP status that is not a success. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string | null) {
    super(detail ?? `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
  }
}

const STATUS_WORDS = new Map([
  [401, 'Bitte wähle zuerst oben unter „Angemeldet als“ eine Person.'],
  [403, 'Diese Person darf das nicht freigeben.'],
  [404, 'Der Eintrag existiert nicht mehr.'],
  [409, 'Der Eintrag wurde inzwischen geändert oder ist schon erledigt.'],
  [422, 'Eine Angabe fehlt oder ist ungültig.'],
]);

/** A German sentence for an error of a call. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const known = STATUS_WORDS.get(error.status);
    const detail = error.message.startsWith('HTTP ') ? null : error.message;
    if (known === undefined) {
      return detail ?? `Der Server meldet einen Fehler (HTTP ${error.status}).`;
    }
    // The role message of the backend is already a full German sentence.
    if (error.status === 403 && detail !== null) {
      return `${detail}.`.replace(/\.\.$/, '.');
    }
    return detail === null ? known : `${known} (${detail})`;
  }
  return 'Der Server antwortet nicht. Die Aktion wurde nicht ausgeführt.';
}
