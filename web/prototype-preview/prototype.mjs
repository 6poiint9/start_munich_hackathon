// All prototype data and actions are local to this page.
const cases = {
  condition: {
    status: 'Approval needed',
    title: 'Confirm pickup terms',
    description: 'The supplier will not release the housing until pickup terms are confirmed in writing.',
    part: 'Housing',
    order: 'NW-1042',
    quantity: '1,000 units',
    need: 'In 2 days',
    impact: 'The supplier estimates 3 days in transit after release. Arrival before production is not confirmed.',
    known: '1,000 units are ready. The supplier requires written pickup confirmation before release.',
    unknown: 'The transport cost, named forwarder, and arrival date are not confirmed.',
    evidenceTitle: 'Supplier email',
    evidenceText: '“The goods are ready. Please confirm that you will nominate your own forwarder. Transit takes about 3 days after release.”',
    evidenceTime: 'Today, 10:34',
    next: 'Review the terms and email draft. Procurement must approve before a binding confirmation can be sent.',
    alternative: 'If the terms are not acceptable, contact the supplier to discuss another arrangement.',
    action: true,
  },
  stock: {
    status: 'Review needed',
    title: 'Resolve stock mismatch',
    description: 'The recorded stock does not match the delivery note.',
    part: 'Fastener kit',
    order: 'NW-1021',
    quantity: '1,200 units differ',
    need: 'Not available',
    impact: 'The available quantity is uncertain. Production coverage cannot be confirmed until the mismatch is resolved.',
    known: 'The recorded stock is 1,500 units. The delivery note shows 300 units.',
    unknown: 'The physical quantity and the reason for the difference are not confirmed.',
    evidenceTitle: 'Goods receipt and delivery note',
    evidenceText: 'Recorded stock: 1,500 units. Delivery note: 300 units.',
    evidenceTime: 'Today, 09:58',
    next: 'Compare the goods receipt with the delivery note and investigate the difference.',
    alternative: 'A stock correction is not proposed until the quantity is verified.',
    action: false,
  },
  delivery: {
    status: 'Request prepared',
    title: 'Confirm delivery date',
    description: 'A delivery date is not confirmed for the motor order.',
    part: 'Motor',
    order: 'NW-1038',
    quantity: 'Not available',
    need: 'Not available',
    impact: 'Without a confirmed delivery date, arrival before production cannot be confirmed.',
    known: 'A request for the delivery date is prepared. The example does not show a sent email.',
    unknown: 'The order quantity, production need date, and expected arrival are not available.',
    evidenceTitle: 'Draft status request',
    evidenceText: 'Lineguard prepared a request for the supplier to confirm the delivery date.',
    evidenceTime: 'Today, 09:20',
    next: 'Review the prepared request and follow up with the supplier.',
    alternative: 'No alternative delivery option is available in this example.',
    action: false,
  },
};

const labels = {
  overview: 'Overview',
  cases: 'Cases',
  approvals: 'Approvals',
  activity: 'Activity',
};
let approved = false;

function showCase(key) {
  const entry = cases[key] || cases.condition;
  const fields = {
    'case-status': key === 'condition' && approved ?
      'Approval simulated' : entry.status,
    'case-title': entry.title,
    'case-description': entry.description,
    'case-part': entry.part,
    'case-order': entry.order,
    'case-quantity': entry.quantity,
    'case-need': entry.need,
    'case-impact': entry.impact,
    'case-known': entry.known,
    'case-unknown': entry.unknown,
    'evidence-title': entry.evidenceTitle,
    'evidence-text': entry.evidenceText,
    'evidence-time': entry.evidenceTime,
    'case-next': key === 'condition' && approved ?
      'Approval was simulated. No email was sent and no change was saved.' :
      entry.next,
    'case-alternative': entry.alternative,
  };
  for (const [id, value] of Object.entries(fields)) {
    document.getElementById(id).textContent = value;
  }
  for (const item of document.querySelectorAll('[data-case]')) {
    const selected = item.dataset.case === key;
    item.classList.toggle('selected', selected);
    if (selected) {
      item.setAttribute('aria-current', 'page');
    } else {
      item.removeAttribute('aria-current');
    }
  }
  document.querySelector('#case-action').hidden = !entry.action;
}

function renderRoute() {
  const [requestedView, requestedCase] =
    location.hash.slice(1).split('/');
  const name = Object.hasOwn(labels, requestedView) ?
    requestedView : 'overview';
  for (const view of document.querySelectorAll('.view')) {
    view.hidden = view.id !== name;
  }
  for (const item of document.querySelectorAll('[data-view]')) {
    const active = item.dataset.view === name;
    item.classList.toggle('active', active);
    if (active) {
      item.setAttribute('aria-current', 'page');
    } else {
      item.removeAttribute('aria-current');
    }
  }
  document.querySelector('#breadcrumb').textContent = labels[name];
  if (name === 'cases') {
    showCase(Object.hasOwn(cases, requestedCase) ?
      requestedCase : 'condition');
  }
}

document.querySelector('#simulate-approval').addEventListener('click', () => {
  approved = true;
  for (const count of document.querySelectorAll('.approval-count')) {
    count.textContent = '0';
  }
  for (const status of document.querySelectorAll('.condition-status')) {
    status.textContent = 'Approval simulated';
  }
  document.querySelector('#approval-summary').textContent =
    'No approvals in this simulation';
  document.querySelector('#approval-status').textContent =
    'Approval simulated';
  document.querySelector('#decision-status').textContent =
    'Approval simulated';
  document.querySelector('#simulation-result').textContent =
    'Approval simulated. No email was sent and no change was saved.';
  document.querySelector('#decision-title').textContent =
    'Approval was simulated.';
  document.querySelector('#decision-description').textContent =
    'No email was sent. The supplier still holds the goods in this example.';
  document.querySelector('#decision-link').textContent = 'View approval';
  document.querySelector('#simulate-approval').disabled = true;
});

window.addEventListener('hashchange', renderRoute);
renderRoute();
