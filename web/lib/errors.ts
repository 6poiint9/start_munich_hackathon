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
  [401, 'Select a person under "Signed in as" first.'],
  [403, 'This person cannot approve this step.'],
  [404, 'This entry does not exist any more.'],
  [409, 'Someone changed or completed this entry in the meantime.'],
  [422, 'A value is missing or not valid.'],
]);

/** An English sentence for an error of a call. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const known = STATUS_WORDS.get(error.status);
    const detail = error.message.startsWith('HTTP ') ? null : error.message;
    if (known === undefined) {
      return detail ?? `The server reports an error (HTTP ${error.status}).`;
    }
    // The role message of the backend is already a full sentence.
    if (error.status === 403 && detail !== null) {
      return `${detail}.`.replace(/\.\.$/, '.');
    }
    return detail === null ? known : `${known} (${detail})`;
  }
  return 'The server does not answer. Lineguard did not run the action.';
}
