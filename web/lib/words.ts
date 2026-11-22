/**
 * German words for the codes of the API.
 *
 * A code that this file does not know is shown as it is, with spaces for
 * underscores. A new code of the backend is therefore never hidden.
 */

/** The meaning that a color and a glyph repeat next to a word. */
export type Tone = 'neutral' | 'go' | 'work' | 'wait' | 'stop';

function readable(code: string): string {
  return code.replaceAll('_', ' ').replaceAll('.', ': ');
}

function lookup(words: ReadonlyMap<string, string>, code: string | null): string {
  if (code === null) {
    return '–';
  }
  return words.get(code) ?? readable(code);
}

const CASE_KINDS = new Map([
  ['gap', 'Lücke'],
  ['booking_finding', 'Buchungsbefund'],
  ['watch', 'Wächter'],
]);

export function caseKindWord(kind: string | null): string {
  return lookup(CASE_KINDS, kind);
}

const CASE_STATES = new Map([
  ['open', 'offen'],
  ['plan_proposed', 'Plan liegt vor'],
  ['approved', 'freigegeben'],
  ['in_execution', 'in Arbeit'],
  ['confirmed', 'bestätigt'],
  ['closed', 'geschlossen'],
  ['unclosable', 'nicht schließbar'],
  ['dismissed', 'verworfen'],
]);

const CASE_STATE_TONES = new Map<string, Tone>([
  ['open', 'wait'],
  ['plan_proposed', 'wait'],
  ['approved', 'work'],
  ['in_execution', 'work'],
  ['confirmed', 'go'],
  ['closed', 'go'],
  ['unclosable', 'stop'],
  ['dismissed', 'neutral'],
]);

export function caseStateWord(state: string | null): string {
  return lookup(CASE_STATES, state);
}

export function caseStateTone(state: string | null): Tone {
  return CASE_STATE_TONES.get(state ?? '') ?? 'neutral';
}

const RULES = new Map([
  ['thin_and_stale', 'Dünne Reserve und alte Zählung'],
]);

export function ruleWord(rule: string | null): string {
  return lookup(RULES, rule);
}

const CAUSES = new Map([
  ['decimal_shift', 'eine Null zu viel oder zu wenig'],
  ['unit_mismatch', 'falsche Einheit'],
  ['duplicate_booking', 'doppelt gebucht'],
  ['unreferenced_receipt', 'Wareneingang ohne Bestellung'],
  ['content_mismatch', 'Inhalt weicht vom gebuchten Teil ab'],
  ['quantity_mismatch', 'Menge weicht ab'],
]);

export function causeWord(cause: string | null): string {
  return lookup(CAUSES, cause);
}

const CHECK_NAMES = new Map([
  ['gr_vs_po', 'Bestellmenge'],
  ['gr_vs_delivery_note', 'Menge auf dem Lieferschein'],
  ['gr_vs_weight', 'Menge aus dem Gewicht'],
  ['gr_vs_packages', 'Menge aus den Packstücken'],
  ['gr_vs_history', 'Frühere Wareneingänge'],
  ['duplicate', 'Doppelte Buchung'],
  ['unreferenced', 'Bezug zu einer Bestellung'],
  ['gr_note_exception', 'Bemerkung der Buchung'],
]);

export function checkNameWord(name: string): string {
  return lookup(CHECK_NAMES, name);
}

const CHECK_STATUSES = new Map([
  ['pass', 'passt'],
  ['fail', 'weicht ab'],
  ['no_data', 'keine Daten'],
]);

const CHECK_STATUS_TONES = new Map<string, Tone>([
  ['pass', 'go'],
  ['fail', 'stop'],
  ['no_data', 'neutral'],
]);

export function checkStatusWord(status: string | null): string {
  return lookup(CHECK_STATUSES, status);
}

export function checkStatusTone(status: string | null): Tone {
  return CHECK_STATUS_TONES.get(status ?? '') ?? 'neutral';
}

const FINDING_STATUSES = new Map([
  ['proposed', 'Korrektur vorgeschlagen'],
  ['needs_count', 'Zählung nötig'],
  ['dismissed', 'verworfen'],
  ['corrected', 'korrigiert'],
]);

export function findingStatusWord(status: string | null): string {
  return lookup(FINDING_STATUSES, status);
}

const CORRECTION_STATUSES = new Map([
  ['proposed', 'wartet auf Freigabe'],
  ['approved', 'freigegeben'],
  ['rejected', 'abgelehnt'],
  ['handed_over', 'an ERP-Verantwortlichen übergeben'],
  ['posted', 'im ERP gebucht'],
  ['verified', 'im ERP bestätigt'],
  ['failed', 'fehlgeschlagen'],
]);

const CORRECTION_STATUS_TONES = new Map<string, Tone>([
  ['proposed', 'wait'],
  ['approved', 'work'],
  ['rejected', 'neutral'],
  ['handed_over', 'work'],
  ['posted', 'work'],
  ['verified', 'go'],
  ['failed', 'stop'],
]);

export function correctionStatusWord(status: string | null): string {
  return lookup(CORRECTION_STATUSES, status);
}

export function correctionStatusTone(status: string | null): Tone {
  return CORRECTION_STATUS_TONES.get(status ?? '') ?? 'neutral';
}

const DECISION_STATUSES = new Map([
  ['open', 'offen'],
  ['approved', 'freigegeben'],
  ['rejected', 'abgelehnt'],
  ['expired', 'abgelaufen'],
  ['applied', 'verbucht'],
  ['handed_over', 'übergeben'],
]);

const DECISION_STATUS_TONES = new Map<string, Tone>([
  ['open', 'wait'],
  ['approved', 'go'],
  ['rejected', 'neutral'],
  ['expired', 'stop'],
]);

export function decisionStatusWord(status: string | null): string {
  return lookup(DECISION_STATUSES, status);
}

export function decisionStatusTone(status: string | null): Tone {
  return DECISION_STATUS_TONES.get(status ?? '') ?? 'neutral';
}

const OPTION_KINDS = new Map([
  ['release_held', 'Wartende Sendung abholen'],
  ['accept_offer', 'Angebot annehmen'],
  ['expedite_inbound', 'Zulauf beschleunigen'],
  ['rework_sort', 'Gesperrte Charge sortieren'],
  ['reallocate', 'Umverteilen'],
  ['count_request', 'Zählung im Lager'],
  ['alt_source', 'Anderer Lieferant'],
  ['add_capacity', 'Mehr Kapazität'],
  ['deliver_after_deadline', 'Nach der Frist liefern'],
  ['erp_correction', 'ERP-Korrektur'],
]);

export function optionKindWord(kind: string | null): string {
  return lookup(OPTION_KINDS, kind);
}

const PLAN_ROLES = new Map([
  ['primary', 'Empfehlung'],
  ['backup', 'Absicherung'],
]);

/** The part an option plays in the plan. `null` when it plays none. */
export function planRoleWord(role: string | null): string | null {
  return PLAN_ROLES.get(role ?? '') ?? null;
}

const EMAIL_STATUSES = new Map([
  ['draft', 'Entwurf'],
  ['approved', 'freigegeben, wird gesendet'],
  ['sent', 'gesendet'],
  ['dry_run', 'nur im Protokoll'],
  ['received', 'Antwort'],
  ['failed', 'Versand fehlgeschlagen'],
  ['discarded', 'verworfen'],
]);

const EMAIL_STATUS_TONES = new Map<string, Tone>([
  ['draft', 'wait'],
  ['approved', 'work'],
  ['sent', 'go'],
  ['dry_run', 'neutral'],
  ['received', 'neutral'],
  ['failed', 'stop'],
  ['discarded', 'neutral'],
]);

export function emailStatusWord(status: string | null): string {
  return lookup(EMAIL_STATUSES, status);
}

export function emailStatusTone(status: string | null): Tone {
  return EMAIL_STATUS_TONES.get(status ?? '') ?? 'neutral';
}

const MAIL_MODES = new Map([
  ['DRY_RUN', 'Mails nur im Protokoll'],
  ['LIVE', 'Mails werden gesendet'],
  ['REPLAY', 'Mails aus der Aufzeichnung'],
]);

export function mailModeWord(mode: string | null): string {
  return lookup(MAIL_MODES, mode);
}

const ROLES = new Map([
  ['buyer', 'Einkauf'],
  ['category_lead', 'Leitung Warengruppe'],
  ['erp_owner', 'ERP-Verantwortung'],
  ['site_lead', 'Standortleitung'],
  ['procurement_head', 'Leitung Einkauf'],
]);

export function roleWord(role: string | null): string {
  return lookup(ROLES, role);
}

const SOURCE_RANKS = new Map([
  [1, 'Beleg'],
  [2, 'Dokument'],
  [3, 'ERP-Bewegung'],
  [4, 'ERP-Bestand'],
  [5, 'Liste'],
]);

export function sourceRankWord(rank: number | null): string {
  if (rank === null) {
    return 'Quelle unbekannt';
  }
  return SOURCE_RANKS.get(rank) ?? `Rang ${rank}`;
}

const READERS = new Map([
  ['parser', 'Parser'],
  ['llm', 'Sprachmodell'],
  ['ocr', 'Texterkennung'],
  ['vision', 'Bilderkennung'],
  ['human', 'Mensch'],
]);

export function readerWord(reader: string | null): string {
  return lookup(READERS, reader);
}

const BLOCK_REASONS = new Map([
  ['booking_finding', 'Buchungsbefund'],
  ['quality_hold', 'Qualitätssperre'],
  ['inspection_failed', 'Prüfung nicht bestanden'],
  ['wrong_revision', 'Falsche Revision'],
  ['expired', 'Abgelaufen'],
  ['not_released', 'Nicht freigegeben'],
]);

export function blockReasonWord(reason: string | null): string {
  return lookup(BLOCK_REASONS, reason);
}

const DEMAND_CLASSES = new Map([
  ['preorder', 'Vorbestellung'],
  ['open_sale', 'Freier Verkauf'],
]);

export function demandClassWord(demandClass: string | null): string {
  return lookup(DEMAND_CLASSES, demandClass);
}

const ACTION_TYPES = new Map([
  ['count_request', 'Zählung im Lager'],
  ['email', 'Mail'],
  ['pickup_request', 'Abholung'],
  ['purchase_order', 'Bestellung'],
  ['erp_correction', 'ERP-Korrektur'],
]);

export function actionTypeWord(type: string | null): string {
  return lookup(ACTION_TYPES, type);
}

const ACTION_STATUSES = new Map([
  ['awaiting_approval', 'wartet auf Freigabe'],
  ['proposed', 'vorgeschlagen'],
  ['approved', 'freigegeben'],
  ['sent', 'gesendet'],
  ['done', 'erledigt'],
  ['failed', 'fehlgeschlagen'],
]);

export function actionStatusWord(status: string | null): string {
  return lookup(ACTION_STATUSES, status);
}

const EVENT_TYPES = new Map([
  ['file.added', 'Datei neu'],
  ['file.changed', 'Datei geändert'],
  ['file.removed', 'Datei entfernt'],
  ['facts.updated', 'Fakten gelesen'],
  ['finding.created', 'Buchungsbefund gefunden'],
  ['correction.proposed', 'Korrektur vorgeschlagen'],
  ['correction.approved', 'Korrektur freigegeben'],
  ['correction.rejected', 'Korrektur abgelehnt'],
  ['correction.verified', 'Korrektur im ERP bestätigt'],
  ['count.requested', 'Zählung angefordert'],
  ['gap.changed', 'Lücke neu berechnet'],
  ['gap.unclosable', 'Lücke nicht schließbar'],
  ['gap.closed', 'Lücke geschlossen'],
  ['option.created', 'Option gefunden'],
  ['option.changed', 'Option geändert'],
  ['decision.created', 'Entscheidung vorbereitet'],
  ['decision.approved', 'Entscheidung freigegeben'],
  ['decision.rejected', 'Entscheidung abgelehnt'],
  ['decision.escalated', 'Entscheidung eskaliert'],
  ['email.drafted', 'Mail entworfen'],
  ['email.sent', 'Mail gesendet'],
  ['email.discarded', 'Mail verworfen'],
  ['email.received', 'Mail empfangen'],
  ['sync.requested', 'Prüfung der Quelle'],
  ['tick', 'Takt'],
]);

export function eventTypeWord(type: string | null): string {
  return lookup(EVENT_TYPES, type);
}

const EVENT_STATUSES = new Map([
  ['pending', 'wartet'],
  ['processing', 'läuft'],
  ['done', 'erledigt'],
  ['failed', 'fehlgeschlagen'],
]);

const EVENT_STATUS_TONES = new Map<string, Tone>([
  ['pending', 'wait'],
  ['processing', 'work'],
  ['done', 'neutral'],
  ['failed', 'stop'],
]);

export function eventStatusWord(status: string | null): string {
  return lookup(EVENT_STATUSES, status);
}

export function eventStatusTone(status: string | null): Tone {
  return EVENT_STATUS_TONES.get(status ?? '') ?? 'neutral';
}

let languageNames: Intl.DisplayNames | null = null;

/** `en` becomes `Englisch`. */
export function languageWord(code: string | null): string {
  if (code === null) {
    return 'Sprache unbekannt';
  }
  try {
    languageNames ??= new Intl.DisplayNames('de', {type: 'language'});
    return languageNames.of(code) ?? code;
  } catch {
    return code;
  }
}

/** How sure an option is, in words. The limits follow docs/lueckenschluss.md. */
export function confidenceWord(confidence: number | null): string {
  if (confidence === null) {
    return 'unbekannt';
  }
  if (confidence >= 0.85) {
    return 'mit Beleg';
  }
  if (confidence >= 0.5) {
    return 'Aussage ohne Beleg';
  }
  return 'noch keine Antwort';
}

/** `row 3, column qty` becomes `Zeile 3, Spalte qty`. */
export function locatorWord(locator: string | null): string | null {
  if (locator === null) {
    return null;
  }
  return locator
    .replace(/\bsheet\b/gi, 'Blatt')
    .replace(/\brow\b/gi, 'Zeile')
    .replace(/\bcolumn\b/gi, 'Spalte')
    .replace(/\bpage\b/gi, 'Seite')
    .replace(/\bcell\b/gi, 'Zelle')
    .replace(/\bline\b/gi, 'Zeile');
}
