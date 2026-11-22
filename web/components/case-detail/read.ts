import type {CaseView, Evidence, Finding} from '../../lib/types';

const DELIVERY_NOTE = 'delivery_note_qty';

export interface HeroModel {
  finding: Finding;
  note: Evidence | null;
  booked: number | null;
  noteQty: number | null;
  /** Label of the document quantity. The delivery note keeps its own name. */
  noteLabel: string;
  /** Coverage gap when the case has one. Otherwise the booking difference. */
  gap: number | null;
  gapLabel: 'Shortage' | 'Reserve' | 'Difference';
  /** Printed number that the handwritten quantity replaced. */
  printed: number | null;
  handwritten: boolean;
}

function checkNumber(finding: Finding, name: string): number | null {
  const check = finding.checks.find((item) => item.name === name);
  return typeof check?.value === 'number' ? check.value : null;
}

/** The delivery-note fact that the booking check cites, or the first one. */
export function deliveryFact(view: CaseView): Evidence | null {
  const check = view.finding?.checks.find((item) => item.name === 'gr_vs_delivery_note');
  const linked = new Set(check?.fact_ids ?? []);
  const notes = view.evidence.filter((item) => item.fact_type === DELIVERY_NOTE);
  return notes.find((item) => linked.has(item.fact_id)) ?? notes[0] ?? null;
}

/**
 * A printed quantity that is not the quantity the reader kept.
 * German thousands separators count: `80.000` is 80000.
 */
function printedFromText(text: string | null, qty: number | null): number | null {
  if (text === null) {
    return null;
  }
  const compact = text.trim().replace(/\s+/g, '');
  let value: number | null = null;
  if (/^\d{1,3}(\.\d{3})+$/.test(compact)) {
    value = Number(compact.replaceAll('.', ''));
  } else if (/^\d{1,3}(\.\d{3})*,\d+$/.test(compact)) {
    value = Number(compact.replaceAll('.', '').replace(',', '.'));
  } else if (/^\d+([.,]\d+)?$/.test(compact)) {
    value = Number(compact.replace(',', '.'));
  }
  if (value === null || !Number.isFinite(value) || value === qty) {
    return null;
  }
  return value;
}

function printedOf(note: Evidence | null): number | null {
  if (note === null) {
    return null;
  }
  if (note.printed_value !== null && note.printed_value !== note.qty) {
    return note.printed_value;
  }
  return printedFromText(note.value_text, note.qty);
}

/** The three figures of the hero. `null` when the case has no booking finding. */
export function heroModel(view: CaseView): HeroModel | null {
  const finding = view.finding;
  if (finding === null) {
    return null;
  }
  const note = deliveryFact(view);
  const noteQty =
    note?.qty ?? checkNumber(finding, 'gr_vs_delivery_note') ?? finding.proposed_qty;
  if (finding.booked_qty === null && noteQty === null) {
    return null;
  }
  const printed = printedOf(note);
  const coverage = view.case.gap_qty;
  const gap = coverage ?? finding.delta_qty;
  const gapLabel =
    coverage === null ? 'Difference' : coverage < 0 ? 'Shortage' : 'Reserve';
  return {
    finding,
    note,
    booked: finding.booked_qty,
    noteQty,
    noteLabel: note === null ? 'Quantity in the documents' : 'On the delivery note',
    gap,
    gapLabel,
    printed,
    handwritten: note?.corrected === true || printed !== null,
  };
}
