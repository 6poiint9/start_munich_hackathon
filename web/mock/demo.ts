/**
 * Demo data for mock mode: an invented bicycle factory.
 *
 * `state.json` and `case.json` are the base. This file adds decisions,
 * options, a booking finding with a correction, mails and more cases, so that
 * every card of the page has content. No value comes from a real customer.
 */

import {normalizeCase, normalizeState} from '../lib/normalize';
import type {
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
    kind: null,
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
    from_addr: 'purchasing@radwerk.example',
    to_addr: null,
    body: null,
    language: 'en',
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
  label: 'Quantity booked in the goods receipt',
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
  label: 'Quantity on the delivery note',
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
  label: 'Ordered quantity',
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
        writer: 'browser_demo',
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
    title: 'Aluminium frame: 50 short, 50 bikes at risk',
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
        fact_id: 14,
        fact_type: 'offer',
        label: 'Offer from Feinrohr: 60 frames by express',
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
        title: 'Accept the offer from Feinrohr: 60 frames by express',
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
        title: 'Speed up purchase order 4500002 at Alurad',
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
        title: 'Move frames from the north plant',
        qty_gain: 20,
        cost_eur: 300,
        confidence: 0.9,
        feasible: false,
        infeasible_reason: 'The north plant has only 20 free frames. That does not close the shortage.',
      }),
    ],
    decisions: [
      decision({
        id: 1,
        title: 'Order 60 frames from Feinrohr by express',
        explanation:
          '50 frames RAHMEN-01 are short. Goods receipt WE-1001 is booked 900 too high, so the ERP shows no shortage. The offer from Feinrohr arrives on Tuesday, one day before the line stops. The faster delivery from Alurad costs less, but Alurad did not confirm it yet. It stays in the plan as a backup.',
        options: [1, 2, 3],
        recommended_option: 1,
        approver_name: 'Anna Beispiel',
        policy_ref: 'freigaberegel.pdf, section 2: purchasing decides up to €5,000',
        deadline: '2027-03-01T11:00:00Z',
      }),
    ],
    emails: [
      mail({
        id: 1,
        to_addr: 'vertrieb@feinrohr.example',
        subject: 'Order of 60 frames RAHMEN-01 by express (offer ANG-2207)',
        body: 'Dear Ms Rohr,\n\nWe accept your offer ANG-2207 and order 60 frames RAHMEN-01 by express.\nPlease confirm the arrival at our goods receipt on Tuesday, 2 March, by 14:00.\n\nKind regards\nPurchasing, Radwerk Demo',
        commits_money: true,
        reason: 'This order commits €4,800. Lineguard sends it only after your approval.',
      }),
      mail({
        id: 2,
        to_addr: 'service@alurad.example',
        subject: 'Purchase order 4500002: can you deliver by Wednesday 08:00?',
        body: 'Dear Mr Felge,\n\nCan you deliver the 50 frames of purchase order 4500002 by Wednesday, 3 March, 08:00?\nPlease tell us the extra cost.\n\nKind regards\nPurchasing, Radwerk Demo',
        status: 'dry_run',
        routine: true,
        reason: 'Routine question without cost.',
        sent_at: '2027-03-01T06:10:00Z',
        created_at: '2027-03-01T06:10:00Z',
      }),
      mail({
        id: 3,
        direction: 'in',
        from_addr: 'service@alurad.example',
        to_addr: 'purchasing@radwerk.example',
        subject: 'RE: Purchase order 4500002: can you deliver by Wednesday 08:00?',
        body: 'Hello,\n\nWednesday 08:00 is possible if the forwarder gets the order today by 15:00. Extra cost: €650. I can give a firm confirmation only this afternoon.\n\nBest regards\nF. Felge',
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
    title: 'Goods receipt WE-1001: 1,000 booked, documents show 100',
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
    title: '7-speed chain: 20 short, a part delivery is on its way',
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
        label: 'Stock in the ERP',
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
        title: 'Part delivery of 30 chains by courier',
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
        title: 'Part delivery of 30 chains by courier',
        explanation: 'Kettenwerk has 30 chains in stock and delivers them by courier.',
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
        subject: 'Part delivery of 30 chains KETTE-07 by courier',
        body: 'Hello,\n\nPlease send 30 chains KETTE-07 by courier. They must arrive by Wednesday 13:00.\n\nKind regards\nPurchasing, Radwerk Demo',
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
        to_addr: 'purchasing@radwerk.example',
        subject: 'RE: Part delivery of 30 chains KETTE-07 by courier',
        body: 'Hello,\n\nThe 30 chains go to the courier tomorrow morning. The tracking number follows.\n\nBest regards\nKettenwerk shipping',
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
    title: 'Comfort saddle: 10 short, no source delivers in time',
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
          text: 'Batch S-118: seam blocked, inspection not finished',
          fact_ids: [],
        },
      ],
    }),
    options: [
      option({
        id: 5,
        kind: 'alt_source',
        title: 'Order saddles from Sitzgut',
        qty_gain: 10,
        arrives_at: '2027-03-09T08:00:00Z',
        cost_eur: 240,
        confidence: 0.6,
        feasible: false,
        infeasible_reason: 'The saddles arrive on 9 March. That is after the line stops.',
      }),
    ],
  });
}

function tireWatch(): CaseView {
  const caseSummary = summary({
    id: 5,
    kind: 'watch',
    rule: 'thin_and_stale',
    title: '28-inch tire: reserve of only 12, last stock count 5 weeks ago',
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
        label: 'Stock in the ERP',
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
    title: 'Goods receipt WE-0990: handlebars booked twice',
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
        writer: 'browser_demo',
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
        description: 'City bike',
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
        description: 'Touring bike',
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
      description: 'Aluminium frame',
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
        error: 'pruefbericht_sattel.pdf: page 2 is not readable. Check it by hand.',
      },
    ],
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
