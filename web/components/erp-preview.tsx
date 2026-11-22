import {formatCount} from '../lib/format';

function text(value: unknown): string {
  if (typeof value === 'string' && value.trim()) {
    return value;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return formatCount(value);
  }
  return 'Not available';
}

export function erpEffect(writer: string | null): string {
  if (writer === 'proposal_file') {
    return 'Lineguard saves a local proposal. It does not update the ERP.';
  }
  if (writer === 'browser_demo') {
    return 'The browser records a demo approval. It does not save a file or update the ERP.';
  }
  if (writer === 'middleware') {
    return 'Lineguard sends the correction to the configured middleware. If it fails, Lineguard saves a local proposal. A later ERP export must confirm the correction.';
  }
  return 'Review the configured ERP write method before approval.';
}

function correctionEffect(writer: string | null, status: string): string | null {
  if (status === 'proposed') {
    return erpEffect(writer);
  }
  if (status === 'rejected') {
    return 'This correction was rejected. Lineguard did not send or save it.';
  }
  if (writer === 'browser_demo') {
    return 'This is a demo approval. No file was saved and the ERP was not updated.';
  }
  if (writer === 'proposal_file') {
    return status === 'verified'
      ? 'Lineguard saved a local proposal. A later ERP export confirmed the quantity.'
      : 'Lineguard saved a local proposal. The ERP has not confirmed the quantity.';
  }
  if (writer === 'middleware') {
    return status === 'verified'
      ? 'Lineguard sent the correction to middleware. A later ERP export confirmed the quantity.'
      : 'Lineguard sent the correction to middleware. The ERP has not confirmed the quantity.';
  }
  return null;
}

export function ErpPreview({payload, writer, status = 'proposed'}: {
  payload: Record<string, unknown>;
  writer: string | null;
  status?: string;
}) {
  const effect = correctionEffect(writer, status);
  return (
    <details className="cd-fold">
      <summary>Review ERP correction proposal</summary>
      <div className="cd-fold-body">
        {effect !== null && <p>{effect}</p>}
        <dl className="lg-pairs">
          <div><dt className="lg-label">Goods receipt</dt><dd>{text(payload.gr_number)}</dd></div>
          <div><dt className="lg-label">Purchase order</dt><dd>{text(payload.po_number)}</dd></div>
          <div><dt className="lg-label">Order line</dt><dd>{text(payload.po_line)}</dd></div>
          <div><dt className="lg-label">Part</dt><dd>{text(payload.material_id)}</dd></div>
          <div><dt className="lg-label">Site</dt><dd>{text(payload.site)}</dd></div>
          <div><dt className="lg-label">Booked quantity</dt><dd>{text(payload.booked_qty)}</dd></div>
          <div><dt className="lg-label">Proposed quantity</dt><dd>{text(payload.proposed_qty)}</dd></div>
        </dl>
        <details className="cd-fold">
          <summary>View proposal data</summary>
          <pre style={{whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'}}>
            {JSON.stringify(payload, null, 2)}
          </pre>
        </details>
      </div>
    </details>
  );
}
