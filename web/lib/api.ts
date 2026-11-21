/**
 * All calls to the Lineguard API.
 *
 * In mock mode the same functions read and change the invented data of
 * `mock/demo.ts`. The page does not know which mode is active.
 */

import {ApiError} from './errors';
import * as mock from './mock';
import {
  errorDetail,
  normalizeCase,
  normalizeEvents,
  normalizeState,
  normalizeSync,
} from './normalize';
import type {
  CaseView,
  EmailEdit,
  EvidenceFile,
  LineguardState,
  LogEvent,
  SyncResult,
} from './types';

const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000'
).replace(/\/+$/, '');
const USER_HEADER = 'X-Lineguard-User';
const FILE_TEXT_LIMIT = 200_000;

let mockMode = process.env.NEXT_PUBLIC_MOCK === '1';

export function isMock(): boolean {
  return mockMode;
}

/** Switches to the demo data. The page calls this when the API is down. */
export function enableMock(): void {
  mockMode = true;
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function get(path: string): Promise<unknown> {
  const response = await fetch(`${API_BASE}${path}`, {cache: 'no-store'});
  const body = await readJson(response);
  if (!response.ok) {
    throw new ApiError(response.status, errorDetail(body));
  }
  return body;
}

async function post(
  path: string,
  personId: string | null,
  body?: object,
): Promise<unknown> {
  const headers = new Headers({'Content-Type': 'application/json'});
  if (personId !== null) {
    // A header value must be Latin-1. Other characters are percent-encoded.
    headers.set(
      USER_HEADER,
      /^[\x20-\x7e\xa0-\xff]*$/.test(personId)
        ? personId
        : encodeURIComponent(personId),
    );
  }
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body ?? {}),
  });
  const answer = await readJson(response);
  if (!response.ok) {
    throw new ApiError(response.status, errorDetail(answer));
  }
  return answer;
}

export async function getState(): Promise<LineguardState> {
  return mockMode ? mock.getState() : normalizeState(await get('/state'));
}

export async function getCase(id: number): Promise<CaseView | null> {
  return mockMode ? mock.getCase(id) : normalizeCase(await get(`/cases/${id}`));
}

export async function getEvents(limit = 50): Promise<LogEvent[]> {
  return mockMode
    ? mock.getEvents(limit)
    : normalizeEvents(await get(`/events?limit=${limit}`));
}

export async function sync(personId: string | null): Promise<SyncResult> {
  return mockMode
    ? mock.sync(personId)
    : normalizeSync(await post('/sync', personId));
}

export async function approveDecision(
  id: number,
  optionId: number | null,
  personId: string | null,
): Promise<void> {
  if (mockMode) {
    mock.approveDecision(id, optionId, personId);
    return;
  }
  const body = optionId === null ? {} : {option_id: optionId};
  await post(`/decisions/${id}/approve`, personId, body);
}

export async function rejectDecision(
  id: number,
  reason: string,
  personId: string | null,
): Promise<void> {
  if (mockMode) {
    mock.rejectDecision(id, reason, personId);
    return;
  }
  await post(`/decisions/${id}/reject`, personId, {reason});
}

export async function approveEmail(
  id: number,
  edit: EmailEdit,
  personId: string | null,
): Promise<void> {
  if (mockMode) {
    mock.approveEmail(id, edit, personId);
    return;
  }
  await post(`/emails/${id}/approve`, personId, edit);
}

export async function discardEmail(
  id: number,
  personId: string | null,
): Promise<void> {
  if (mockMode) {
    mock.discardEmail(id, personId);
    return;
  }
  await post(`/emails/${id}/discard`, personId);
}

export async function approveCorrection(
  id: number,
  personId: string | null,
): Promise<void> {
  if (mockMode) {
    mock.approveCorrection(id, personId);
    return;
  }
  await post(`/corrections/${id}/approve`, personId);
}

export async function rejectCorrection(
  id: number,
  reason: string,
  personId: string | null,
): Promise<void> {
  if (mockMode) {
    mock.rejectCorrection(id, reason, personId);
    return;
  }
  await post(`/corrections/${id}/reject`, personId, {reason});
}

export async function requestCount(
  id: number,
  personId: string | null,
): Promise<void> {
  if (mockMode) {
    mock.requestCount(id, personId);
    return;
  }
  await post(`/corrections/${id}/count`, personId);
}

export type FileKind = 'image' | 'pdf' | 'text' | 'binary';

const IMAGE_ENDINGS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp'];
/** Office files and archives are not text. The page offers them as a download. */
const BINARY_ENDINGS = ['xlsx', 'xls', 'docx', 'doc', 'pptx', 'zip', 'msg'];

/** How the page shows a file. The ending of the path decides. */
export function fileKind(path: string | null): FileKind {
  const ending = (path ?? '').toLowerCase().split('.').pop() ?? '';
  if (IMAGE_ENDINGS.includes(ending)) {
    return 'image';
  }
  if (BINARY_ENDINGS.includes(ending)) {
    return 'binary';
  }
  return ending === 'pdf' ? 'pdf' : 'text';
}

export function fileUrl(file: EvidenceFile): string {
  if (mockMode) {
    const name = (file.path ?? '').split('/').pop() ?? '';
    return `/mock-files/${encodeURIComponent(name)}`;
  }
  return `${API_BASE}/files/${file.id}/content`;
}

/** Reads a file as text. A long file is cut. */
export async function getFileText(file: EvidenceFile): Promise<string> {
  const response = await fetch(fileUrl(file), {cache: 'no-store'});
  if (!response.ok) {
    throw new ApiError(response.status, null);
  }
  const text = await response.text();
  return text.length > FILE_TEXT_LIMIT
    ? `${text.slice(0, FILE_TEXT_LIMIT)}\n… (gekürzt)`
    : text;
}
