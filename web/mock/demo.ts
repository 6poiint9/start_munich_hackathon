/**
 * Demo data for mock mode: an invented bicycle factory.
 *
 * `state.json` and `case.json` are the base. This file adds decisions,
 * options, a booking finding with a correction, mails and more cases, so that
 * every card of the page has content. No value comes from a real customer.
 */

import {normalizeCase, normalizeState} from '../lib/normalize';
import type {
  Approval,
  ApprovalDone,
  CaseDetail,
  CaseSummary,
  CaseView,
  Decision,
  Email,
  Evidence,
  LineguardState,
  LogEvent,
  Option,
} from '../lib/types';

import caseJson from './case.json';
import stateJson from './state.json';

export interface DemoData {
  state: LineguardState;
  cases: Map<number, CaseView>;
  events: LogEvent[];
}

const NOW = '2027-03-01T07:00:00Z';

function summary(
  fields: Pick<CaseSummary, 'id' | 'kind' | 'title' | 'state'> &
    Partial<CaseSummary>,
): CaseSummary {
  return {
    rule: null,
    impact: null,
    rank: null,
    component_id: null,
    product_id: null,
    supplier_id: null,
    po_number: null,
    due_at: null,
    act_by: null,
    breaks_at: null,
    owner_role: null,
    gap_qty: null,
    units_at_risk: null,
    residual_qty: null,
    pending: {decisions: 0, corrections: 0, emails: 0},
    updated_at: NOW,
    ...fields,
  };
}

function detail(fields: Partial<CaseDetail>): CaseDetail {
  return {
    erp_stock: null,
    stock_as_of: null,
    used_since_snapshot: null,
    usable: null,
    need: null,
    inbound_secured: null,
    gap_system: null,
    latest_useful_arrival: null,
    blocks: [],
    short_lines: [],
    ...fields,
  };
}

function fact(
  fields: Pick<Evidence, 'fact_id' | 'label'> & Partial<Evidence>,
): Evidence {
  return {
    fact_type: null,
    qty: null,
    value_num: null,
    value_text: null,
    rev: null,
    batch: null,
    ref: null,
    po_number: null,
    eta: null,
    valid_until: null,
    doc_date: null,
    as_of: null,
    source_rank: null,
    confidence: 1,
    extracted_by: 'parser',
    suspicious: false,
    printed_value: null,
    corrected: false,
    file: null,
    locator: null,
    ...fields,
  };
}

function option(
  fields: Pick<Option, 'id' | 'title'> & Partial<Option>,
): Option {
  return {
    kind: null,
    qty_gain: null,
    units_gained: {},
    arrives_at: null,
    cost_eur: null,
    confidence: null,
    valid_until: null,
    feasible: true,
    infeasible_reason: null,
    role_in_plan: 'none',
    status: 'proposed',
    needs_roles: ['buyer'],
    supplier_id: null,
    ...fields,
  };
}

function decision(
  fields: Pick<Decision, 'id' | 'title'> & Partial<Decision>,
): Decision {
  return {
    explanation: null,
    status: 'open',
    options: [],
    recommended_option: null,
    needs_roles: ['buyer'],
    approver_role: 'buyer',
    approver_name: null,
    policy_ref: null,
    deadline: null,
    decided_by: null,
    decided_at: null,
    reject_reason: null,
    ...fields,
  };
}

function mail(fields: Pick<Email, 'id' | 'subject'> & Partial<Email>): Email {
  return {
    direction: 'out',
    from_addr: 'einkauf@radwerk.example',
    to_addr: null,
    body: null,
    language: 'de',
    status: 'draft',
    routine: false,
    commits_money: false,
    reason: null,
    approved_by: null,
    sent_at: null,
    created_at: NOW,
    ...fields,
  };
}

function view(
  caseSummary: CaseSummary,
  fields: Partial<Omit<CaseView, 'case'>>,
): CaseView {
  return {
    case: caseSummary,
    detail: detail({}),
    evidence: [],
    finding: null,
    corrections: [],
    options: [],
    decisions: [],
    emails: [],
    actions: [],
    ...fields,
  };
}

const STOCK_FILE = {id: 3, path: 'bestand.csv', version: 1};
const RECEIPTS_FILE = {id: 4, path: 'wareneingaenge.csv', version: 1};
const NOTE_FILE = {id: 5, path: 'lieferschein-ls-4711.svg', version: 1};
const OFFER_FILE = {id: 6, path: 'angebot-feinrohr.txt', version: 1};

const receiptBooked = fact({
  fact_id: 11,
  fact_type: 'gr_qty',
  label: 'Gebuchte Menge im Wareneingang',
  qty: 1000,
  ref: 'WE-1001',
  po_number: '4500001',
  doc_date: '2027-02-24',
  source_rank: 3,
  suspicious: true,
  file: RECEIPTS_FILE,
  locator: 'row 2, column menge',
});

const noteQty = fact({
  fact_id: 12,
  fact_type: 'delivery_note_qty',
  label: 'Menge auf dem Lieferschein',
  qty: 100,
  ref: 'LS-4711',
  po_number: '4500001',
  doc_date: '2027-02-24',
  source_rank: 1,
  confidence: 0.95,
  extracted_by: 'vision',
  printed_value: 1000,
  corrected: true,
  file: NOTE_FILE,
  locator: 'page 1, row 1',
});

const orderQty = fact({
  fact_id: 13,
  fact_type: 'po_qty',
  label: 'Bestellte Menge',
  qty: 100,
  po_number: '4500001',
  source_rank: 3,
  file: {id: 7, path: 'bestellungen.csv', version: 1},
  locator: 'row 2',
});

function receiptBundle(): Pick<CaseView, 'finding' | 'corrections'> {
  return {
    finding: {
      gr_number: 'WE-1001',
      booked_qty: 1000,
      proposed_qty: 100,
      delta_qty: -900,
      cause: 'decimal_shift',
      checks: [
        {name: 'gr_vs_po', status: 'fail', value: 100, fact_ids: [13]},
        {name: 'gr_vs_delivery_note', status: 'fail', value: 100, fact_ids: [12]},
        {name: 'gr_vs_weight', status: 'fail', value: 104, fact_ids: []},
        {name: 'gr_vs_history', status: 'fail', value: 120, fact_ids: []},
        {name: 'duplicate', status: 'pass', value: null, fact_ids: []},
        {name: 'unreferenced', status: 'pass', value: null, fact_ids: []},
        {name: 'gr_note_exception', status: 'no_data', value: null, fact_ids: []},
      ],
      agreeing_sources: 3,
      status: 'proposed',
    },
    corrections: [
      {
        id: 1,
        status: 'proposed',
        payload: {
          kind: 'gr_qty',
          gr_number: 'WE-1001',
          po_number: '4500001',
          material_id: 'RAHMEN-01',
          booked_qty: 1000,
          proposed_qty: 100,
          delta_qty: -900,
        },
        approver_role: 'erp_owner',
        approved_by: null,
        approved_at: null,
        reject_reason: null,
        created_at: NOW,
      },
    ],
  };
}

function frameGap(): CaseView {
  const base = normalizeCase(caseJson);
  const caseSummary = summary({
    ...(base?.case ?? {id: 1, kind: 'gap'}),
    title: 'Rahmen Alu: 50 fehlen, 50 Räder in Gefahr',
    state: 'plan_proposed',
    rank: 1,
    breaks_at: '2027-03-03T10:27:00Z',
    pending: {decisions: 1, corrections: 1, emails: 1},
  });
  return view(caseSummary, {
    ...receiptBundle(),
    detail: {
      ...(base?.detail ?? detail({})),
      latest_useful_arrival: '2027-03-03T08:00:00Z',
    },
    evidence: [
      noteQty,
      fact({
        fact_id: 15,
        fact_type: 'supplier_condition',
        label: 'Bedingung des Lieferanten',
        value_text: 'Express nur, wenn die Bestellung heute bis 16:00 Uhr liegt.',
        ref: 'ANG-2207',
        source_rank: 2,
        confidence: 0.9,
        extracted_by: 'llm',
      }),
      fact({
        fact_id: 14,
        fact_type: 'offer',
        label: 'Angebot Feinrohr: 60 Rahmen per Express',
        qty: 60,
        value_num: 4800,
        ref: 'ANG-2207',
        valid_until: '2027-03-01T16:00:00Z',
        source_rank: 2,
        confidence: 0.9,
        extracted_by: 'llm',
        file: OFFER_FILE,
        locator: 'line 6',
      }),
      receiptBooked,
      ...(base?.evidence ?? []),
    ],
    options: [
      option({
        id: 1,
        kind: 'accept_offer',
        title: 'Angebot von Feinrohr annehmen: 60 Rahmen per Express',
        qty_gain: 60,
        units_gained: {'BIKE-CITY': 50},
        arrives_at: '2027-03-02T13:00:00Z',
        cost_eur: 4800,
        confidence: 0.9,
        valid_until: '2027-03-01T16:00:00Z',
        role_in_plan: 'primary',
        supplier_id: 'LIEF-FEINROHR',
      }),
      option({
        id: 2,
        kind: 'expedite_inbound',
        title: 'Bestellung 4500002 bei Alurad beschleunigen',
        qty_gain: 50,
        units_gained: {'BIKE-CITY': 50},
        arrives_at: '2027-03-03T07:00:00Z',
        cost_eur: 650,
        confidence: 0.55,
        role_in_plan: 'backup',
        supplier_id: 'LIEF-ALURAD',
      }),
      option({
        id: 3,
        kind: 'reallocate',
        title: 'Rahmen aus Werk Nord umlagern',
        qty_gain: 20,
        cost_eur: 300,
        confidence: 0.9,
        feasible: false,
        infeasible_reason: 'Werk Nord hat nur 20 Rahmen frei. Das schließt die Lücke nicht.',
      }),
    ],
    decisions: [
      decision({
        id: 1,
        title: '60 Rahmen bei Feinrohr per Express bestellen',
        explanation:
          'Es fehlen 50 Rahmen RAHMEN-01. Der Wareneingang WE-1001 ist um 900 zu hoch gebucht, deshalb zeigt das ERP keine Lücke. Das Angebot von Feinrohr kommt am Dienstag an, einen Tag vor dem Stopp der Linie. Die beschleunigte Bestellung bei Alurad ist billiger, aber noch nicht zugesagt. Sie bleibt als Absicherung im Plan.',
        options: [1, 2, 3],
        recommended_option: 1,
        approver_name: 'Anna Beispiel',
        policy_ref: 'freigaberegel.pdf, Abschnitt 2: bis 5.000 € entscheidet der Einkauf',
        deadline: '2027-03-01T11:00:00Z',
      }),
    ],
    emails: [
      mail({
        id: 1,
        to_addr: 'vertrieb@feinrohr.example',
        subject: 'Bestellung 60 Rahmen RAHMEN-01 per Express (Angebot ANG-2207)',
        body: 'Guten Tag Frau Rohr,\n\nwir nehmen Ihr Angebot ANG-2207 an und bestellen 60 Rahmen RAHMEN-01 per Express.\nBitte bestätigen Sie die Ankunft am Dienstag, 02.03., bis 14:00 Uhr an unserem Wareneingang.\n\nFreundliche Grüße\nEinkauf Radwerk Demo',
        commits_money: true,
        reason: 'Die Bestellung bindet 4.800 €. Sie geht erst nach deiner Freigabe raus.',
      }),
      mail({
        id: 2,
        to_addr: 'service@alurad.example',
        subject: 'Bestellung 4500002: Ist eine Lieferung bis Mittwoch 08:00 möglich?',
        body: 'Guten Tag Herr Felge,\n\nkönnen Sie die 50 Rahmen der Bestellung 4500002 bis Mittwoch, 03.03., 08:00 Uhr liefern?\nBitte nennen Sie uns den Aufpreis.\n\nFreundliche Grüße\nEinkauf Radwerk Demo',
        status: 'dry_run',
        routine: true,
        reason: 'Routinefrage ohne Kosten.',
        sent_at: '2027-03-01T06:10:00Z',
        created_at: '2027-03-01T06:10:00Z',
      }),
      mail({
        id: 3,
        direction: 'in',
        from_addr: 'service@alurad.example',
        to_addr: 'einkauf@radwerk.example',
        subject: 'AW: Bestellung 4500002: Ist eine Lieferung bis Mittwoch 08:00 möglich?',
        body: 'Guten Tag,\n\nMittwoch 08:00 Uhr ist möglich, wenn die Spedition heute bis 15:00 Uhr den Auftrag bekommt. Aufpreis: 650 €. Eine feste Zusage kann ich erst am Nachmittag geben.\n\nViele Grüße\nF. Felge',
        status: 'received',
        created_at: '2027-03-01T06:42:00Z',
      }),
    ],
  });
}

function receiptFinding(): CaseView {
  const caseSummary = summary({
    id: 2,
    kind: 'booking_finding',
    title: 'Wareneingang WE-1001: 1.000 gebucht, 100 belegt',
    state: 'open',
    rank: 2,
    impact: 'deadline_blocker',
    component_id: 'RAHMEN-01',
    product_id: 'BIKE-CITY',
    po_number: '4500001',
    act_by: '2027-03-01T15:00:00Z',
    units_at_risk: 50,
    pending: {decisions: 0, corrections: 1, emails: 0},
  });
  return view(caseSummary, {
    evidence: [noteQty, orderQty, receiptBooked],
    ...receiptBundle(),
  });
}

function chainGap(): CaseView {
  const caseSummary = summary({
    id: 3,
    kind: 'gap',
    title: 'Kette 7-fach: 20 fehlen, Nachlieferung läuft',
    state: 'in_execution',
    rank: 3,
    impact: 'deadline_blocker',
    component_id: 'KETTE-07',
    product_id: 'BIKE-TOUR',
    supplier_id: 'LIEF-KETTENWERK',
    breaks_at: '2027-03-04T09:00:00Z',
    gap_qty: -20,
    units_at_risk: 20,
  });
  return view(caseSummary, {
    detail: detail({
      erp_stock: 160,
      stock_as_of: '2027-02-28',
      used_since_snapshot: 0,
      usable: 160,
      need: 180,
      inbound_secured: 0,
      latest_useful_arrival: '2027-03-04T07:00:00Z',
    }),
    evidence: [
      fact({
        fact_id: 21,
        fact_type: 'stock_qty',
        label: 'Bestand laut ERP',
        qty: 160,
        as_of: '2027-02-28',
        source_rank: 4,
        file: STOCK_FILE,
        locator: 'row 4',
      }),
    ],
    options: [
      option({
        id: 4,
        kind: 'expedite_inbound',
        title: 'Teillieferung 30 Ketten per Kurier',
        qty_gain: 30,
        units_gained: {'BIKE-TOUR': 20},
        arrives_at: '2027-03-03T12:00:00Z',
        cost_eur: 180,
        confidence: 0.9,
        role_in_plan: 'primary',
        status: 'approved',
      }),
    ],
    decisions: [
      decision({
        id: 2,
        title: 'Teillieferung 30 Ketten per Kurier',
        explanation: 'Das Kettenwerk hat 30 Ketten auf Lager und liefert sie per Kurier.',
        status: 'approved',
        options: [4],
        recommended_option: 4,
        approver_name: 'Anna Beispiel',
        decided_by: 'P1',
        decided_at: '2027-02-28T15:20:00Z',
      }),
    ],
    emails: [
      mail({
        id: 4,
        to_addr: 'versand@kettenwerk.example',
        subject: 'Teillieferung 30 Ketten KETTE-07 per Kurier',
        body: 'Guten Tag,\n\nbitte senden Sie 30 Ketten KETTE-07 per Kurier. Ankunft bis Mittwoch 13:00 Uhr.\n\nFreundliche Grüße\nEinkauf Radwerk Demo',
        status: 'sent',
        commits_money: true,
        approved_by: 'P1',
        sent_at: '2027-02-28T15:21:00Z',
        created_at: '2027-02-28T15:20:00Z',
      }),
      mail({
        id: 5,
        direction: 'in',
        from_addr: 'versand@kettenwerk.example',
        to_addr: 'einkauf@radwerk.example',
        subject: 'AW: Teillieferung 30 Ketten KETTE-07 per Kurier',
        body: 'Guten Tag,\n\ndie 30 Ketten gehen morgen früh an den Kurier. Sendungsnummer folgt.\n\nViele Grüße\nKettenwerk Versand',
        status: 'received',
        created_at: '2027-02-28T16:05:00Z',
      }),
    ],
  });
}

function saddleGap(): CaseView {
  const caseSummary = summary({
    id: 4,
    kind: 'gap',
    title: 'Sattel Komfort: 10 fehlen, keine Quelle liefert rechtzeitig',
    state: 'unclosable',
    rank: 4,
    component_id: 'SATTEL-02',
    product_id: 'BIKE-TOUR',
    breaks_at: '2027-03-04T13:30:00Z',
    gap_qty: -10,
    units_at_risk: 10,
    residual_qty: 10,
  });
  return view(caseSummary, {
    detail: detail({
      erp_stock: 190,
      stock_as_of: '2027-02-28',
      usable: 170,
      need: 180,
      latest_useful_arrival: '2027-03-04T11:00:00Z',
      blocks: [
        {
          reason: 'quality_hold',
          qty: 20,
          text: 'Charge S-118: Naht gesperrt, Prüfung offen',
          fact_ids: [],
        },
      ],
    }),
    options: [
      option({
        id: 5,
        kind: 'alt_source',
        title: 'Sattel bei Sitzgut bestellen',
        qty_gain: 10,
        arrives_at: '2027-03-09T08:00:00Z',
        cost_eur: 240,
        confidence: 0.6,
        feasible: false,
        infeasible_reason: 'Ankunft erst am 09.03., also nach dem Stopp der Linie.',
      }),
    ],
  });
}

function tireWatch(): CaseView {
  const caseSummary = summary({
    id: 5,
    kind: 'watch',
    rule: 'thin_and_stale',
    title: 'Reifen 28 Zoll: Reserve nur 12, letzte Zählung vor 5 Wochen',
    state: 'open',
    rank: 5,
    component_id: 'REIFEN-28',
    product_id: 'BIKE-CITY',
    act_by: '2027-02-28T15:00:00Z',
  });
  return view(caseSummary, {
    evidence: [
      fact({
        fact_id: 31,
        fact_type: 'stock_qty',
        label: 'Bestand laut ERP',
        qty: 1212,
        as_of: '2027-02-28',
        source_rank: 4,
        file: STOCK_FILE,
        locator: 'row 5',
      }),
    ],
  });
}

function doubleBooking(): CaseView {
  const caseSummary = summary({
    id: 6,
    kind: 'booking_finding',
    title: 'Wareneingang WE-0990: Lenker doppelt gebucht',
    state: 'approved',
    rank: 6,
    component_id: 'LENKER-03',
    product_id: 'BIKE-TOUR',
    po_number: '4499990',
  });
  return view(caseSummary, {
    finding: {
      gr_number: 'WE-0990',
      booked_qty: 400,
      proposed_qty: 200,
      delta_qty: -200,
      cause: 'duplicate_booking',
      checks: [
        {name: 'duplicate', status: 'fail', value: 'WE-0989', fact_ids: []},
        {name: 'gr_vs_po', status: 'fail', value: 200, fact_ids: []},
        {name: 'gr_vs_delivery_note', status: 'no_data', value: null, fact_ids: []},
      ],
      agreeing_sources: 2,
      status: 'proposed',
    },
    corrections: [
      {
        id: 2,
        status: 'handed_over',
        payload: {kind: 'gr_qty', gr_number: 'WE-0990'},
        approver_role: 'erp_owner',
        approved_by: 'P3',
        approved_at: '2027-02-28T10:00:00Z',
        reject_reason: null,
        created_at: '2027-02-28T09:30:00Z',
      },
    ],
  });
}

function logEvent(id: number, type: string, createdAt: string): LogEvent {
  return {
    id,
    type,
    status: 'done',
    created_at: createdAt,
    handled_by: null,
    payload: {},
  };
}

/** Builds a fresh copy of the demo data. */
function demoApprovals(): Approval[] {
  return [
    {
      id: 'decision:1',
      type: 'decision',
      object_id: 1,
      case_id: 1,
      kind: 'accept_offer',
      title: '60 Rahmen bei Feinrohr per Express bestellen',
      summary: '60 Rahmen, Ankunft Dienstag 14:00, einen Tag vor dem Stopp der Linie.',
      needs_roles: ['buyer'],
      approver_name: 'Anna Beispiel',
      deadline: '2027-03-01T11:00:00Z',
      cost_eur: 4800,
      cost_unknown: false,
      commits_money: true,
      supplier_id: 'LIEF-FEINROHR',
      arrives_at: '2027-03-02T13:00:00Z',
      condition: 'Express nur, wenn die Bestellung heute bis 16:00 Uhr liegt.',
      conflict: null,
      note: null,
      after_deadline: false,
      email: {
        id: 1,
        to_addr: 'vertrieb@feinrohr.example',
        subject: 'Bestellung 60 Rahmen RAHMEN-01 per Express (Angebot ANG-2207)',
        body: 'Guten Tag Frau Rohr,\n\nwir nehmen Ihr Angebot ANG-2207 an und bestellen 60 Rahmen RAHMEN-01 per Express.\nBitte bestätigen Sie die Ankunft am Dienstag, 02.03., bis 14:00 Uhr an unserem Wareneingang.\n\nFreundliche Grüße\nEinkauf Radwerk Demo',
        language: 'de',
        commits_money: true,
      },
      created_at: NOW,
    },
    {
      id: 'correction:1',
      type: 'correction',
      object_id: 1,
      case_id: 2,
      kind: 'erp_correction',
      title: 'Wareneingang WE-1001 korrigieren: 1.000 auf 100',
      summary: 'Drei Quellen belegen 100 Stück. Das ERP hat 1.000 gebucht.',
      needs_roles: ['erp_owner'],
      approver_name: 'Clara Test',
      deadline: '2027-03-01T15:00:00Z',
      cost_eur: null,
      cost_unknown: false,
      commits_money: false,
      supplier_id: 'LIEF-FEINROHR',
      arrives_at: null,
      condition: null,
      conflict: 'ERP und Lieferschein weichen um 900 Stück ab.',
      note: 'Die Linie verbraucht den Bestand, bevor die Korrektur im ERP steht.',
      after_deadline: true,
      email: null,
      created_at: '2027-03-01T06:20:00Z',
    },
  ];
}

function demoApprovalsDone(): ApprovalDone[] {
  return [
    {
      id: 'decision:8',
      type: 'decision',
      case_id: 3,
      title: 'Teillieferung 30 Ketten per Kurier',
      status: 'approved',
      decided_by: 'Anna Beispiel',
      decided_at: '2027-02-28T16:10:00Z',
      mail_status: 'sent',
      mail_to: 'dispo@kettenwerk.example',
    },
    {
      id: 'correction:4',
      type: 'correction',
      case_id: 5,
      title: 'Wareneingang WE-0990 stornieren',
      status: 'rejected',
      decided_by: 'Clara Test',
      decided_at: '2027-02-28T11:20:00Z',
      mail_status: null,
      mail_to: null,
    },
  ];
}

export function createDemo(): DemoData {
  const views = [
    frameGap(),
    receiptFinding(),
    chainGap(),
    saddleGap(),
    tireWatch(),
    doubleBooking(),
  ];
  const base = normalizeState(stateJson);
  const state: LineguardState = {
    ...base,
    at: NOW,
    products: [
      {
        product_id: 'BIKE-CITY',
        description: 'Stadtrad City',
        demand: 700,
        packed: 100,
        still_to_pack: 600,
        rate_per_hour: 12,
        hours_left: 50,
        coverage_system: 1,
        coverage_secured: 650 / 700,
        units: {secured: 550, planned: 0, open: 50, unclosable: 0},
        limiting_component: 'RAHMEN-01',
      },
      {
        product_id: 'BIKE-TOUR',
        description: 'Tourenrad Tour',
        demand: 300,
        packed: 120,
        still_to_pack: 180,
        rate_per_hour: 6,
        hours_left: 30,
        coverage_system: 1,
        coverage_secured: 270 / 300,
        units: {secured: 150, planned: 20, open: 0, unclosable: 10},
        limiting_component: 'KETTE-07',
      },
    ],
    first_stop: {
      component_id: 'RAHMEN-01',
      description: 'Rahmen Alu',
      breaks_at: '2027-03-03T10:27:00Z',
    },
    cases_now: views.slice(0, 4).map((entry) => entry.case),
    cases_later: views.slice(4).map((entry) => entry.case),
    counters: {
      now_total: 4,
      later_total: 3,
      open_decisions: 1,
      open_corrections: 2,
      open_emails: 1,
    },
    booking_review: {receipts_checked: 4, findings: 2},
    problems: [
      {
        event_id: 41,
        type: 'file.changed',
        error: 'pruefbericht_sattel.pdf: Seite 2 ist nicht lesbar. Bitte von Hand prüfen.',
      },
    ],
    approvals: demoApprovals(),
    approvals_done: demoApprovalsDone(),
  };
  return {
    state,
    cases: new Map(views.map((entry) => [entry.case.id, entry])),
    events: [
      logEvent(46, 'email.received', '2027-03-01T06:42:00Z'),
      logEvent(45, 'email.sent', '2027-03-01T06:10:00Z'),
      logEvent(44, 'email.drafted', '2027-03-01T06:05:00Z'),
      logEvent(43, 'decision.created', '2027-03-01T06:05:00Z'),
      logEvent(42, 'option.created', '2027-03-01T06:04:00Z'),
      {
        ...logEvent(41, 'file.changed', '2027-03-01T06:02:00Z'),
        status: 'failed',
      },
      logEvent(40, 'sync.requested', '2027-03-01T06:00:00Z'),
    ],
  };
}
