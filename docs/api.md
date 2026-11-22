# API für die Oberfläche

Lies diese Datei, wenn du `web/` baust oder einen Endpunkt in `lineguard/main.py` änderst.

Basis: `http://localhost:8000`. Alle Antworten sind JSON. Zeitpunkte sind ISO-Text in UTC (`2026-11-22T06:00:00Z`). Die Oberfläche zeigt sie in der Zeitzone aus `state.timezone`. Echte Beispiele liegen in `web/mock/state.json` und `web/mock/case.json`. Sie stammen aus dem erfundenen Paket `demo_bikes`.

## Lesen

| Endpunkt | Inhalt |
|---|---|
| `GET /state` | Kopfzeile, Listen „Jetzt“ und „Danach“, Zähler, Personen. `?at=<Zeitpunkt>` rechnet die Kopfzeile für einen anderen Moment und speichert nichts |
| `GET /cases/{id}` | Ein Fall mit Belegen, Buchungsbefund, Korrekturen, Optionen, Entscheidungen, Mails, Aktionen |
| `GET /files/{id}/content` | Die Datei eines Belegs (Bild, PDF, CSV) |
| `GET /events?limit=50` | Die letzten Events als Protokoll: `id, type, status, created_at, handled_by, payload` |
| `GET /healthz` | Messwerte |

Felder von `state`:

- `labels`: Wörter des Kunden für `deadline`, `product`, `line`, `units`. Die Oberfläche benutzt diese Wörter und nie feste Wörter wie „Launch“.
- `products[]`: `product_id, description, demand, packed, still_to_pack, rate_per_hour, hours_left, coverage_system, coverage_secured` (0 bis 1), `units` mit `secured, planned, open, unclosable` (die Summe ist `still_to_pack`), `limiting_component`.
- `first_stop`: `component_id, description, breaks_at` oder `null`.
- `next_due`: nächster Bedarfstermin oder `null`. Bei `null` zeigt die Kopfzeile „Kein offener Bedarfstermin“.
- `cases_now[]`, `cases_later[]`: je Fall `id, kind` (`gap`, `booking_finding`, `watch`), `rule, title, impact, state, rank, component_id, product_id, supplier_id, po_number, due_at, act_by, breaks_at, owner_role, gap_qty, units_at_risk, residual_qty, pending` (`decisions, corrections, emails`), `updated_at`.
- `counters`: `now_total, later_total, open_decisions, open_corrections, open_emails`.
- `import`: `files_total, files_read, failed, manual` für die Zeile „N von M Belegen gelesen“.
- `booking_review`: `receipts_checked, findings`.
- `problems[]`: fehlgeschlagene Events mit `event_id, type, error`.
- `people[]`: `person_id, name, roles[]` für „Angemeldet als“.
- `mail_mode`: `DRY_RUN`, `LIVE` oder `REPLAY`.

Zustände eines Falls: `open, plan_proposed, approved, in_execution, confirmed, closed, unclosable, dismissed`.

Felder von `cases/{id}`:

- `case`: wie in der Liste, dazu `detail`. Bei einer Lücke enthält `detail`: `erp_stock, usable, need, inbound_secured, gap_system, blocks[]` (`reason, qty, text, fact_ids`), `short_lines[]`, `inbound[]`, `latest_useful_arrival`.
- `evidence[]`: `fact_id, fact_type, label, qty, value_num, value_text, rev, batch, ref, po_number, eta, valid_until, doc_date, as_of, source_rank` (1 ist der beste Beleg, 5 der schwächste), `confidence, extracted_by, suspicious, file` (`id, path, version`), `locator`.
- `finding`: `gr_number, booked_qty, proposed_qty, delta_qty, cause, checks` (Name → `status, value, fact_ids`), `agreeing_sources, status`. Ohne Befund `null`.
- `corrections[]`: `id, status` (`proposed, approved, rejected, handed_over, posted, verified, failed`), `payload, approver_role, approved_by, approved_at, reject_reason, created_at`.
- `options[]`: `id, kind, title, qty_gain, units_gained, arrives_at, cost_eur, confidence, valid_until, feasible, infeasible_reason, role_in_plan` (`primary, backup, none`), `status, needs_roles[], supplier_id`.
- `decisions[]`: `id, title, explanation, status` (`open, approved, rejected, expired`), `options[]` (IDs), `recommended_option, needs_roles[], approver_role, approver_name, policy_ref, deadline, decided_by, decided_at`.
- `emails[]`: `id, direction` (`out, in`), `from_addr, to_addr, subject, body, language, status` (`draft, approved, sent, dry_run, received, failed, discarded`), `routine, commits_money, reason, approved_by, sent_at, created_at`.

## Schreiben

Jeder schreibende Aufruf braucht den Header `X-Lineguard-User: <person_id>`. Ohne Header antwortet die API mit HTTP 401. Eine unbekannte Person erhält HTTP 403. Für Freigeben, Ablehnen, Verwerfen und Zählen gelten Rollenregeln. Eine passende Rolle genügt; bei unbesetzter Rolle kann die konfigurierte Ersatzrolle gelten. Gemeinsame Freigaben, die Soony teilweise verlangt, sind nicht umgesetzt. Die Personenauswahl ist kein Login.

If an option expires, leaves the plan, or its gap closes, approval returns HTTP 409. No email is sent. If mail delivery fails, the API returns HTTP 502 and records the mail as failed. The decision stays approved. Check the mailbox before sending again because delivery can be uncertain. Lineguard does not retry the failed approval automatically.

An `unclosable_gap` decision is a shortage alert for the highest role in the escalation chain. The alert does not confirm a later date or cost. Approving it records an acknowledgment. It does not arrange a delivery or send an email. The case stays open while the shortage remains.

When known options do not cover a shortage, Lineguard can prepare a quote request to a known alternative supplier. The request counts no goods as available. It is a draft unless the customer pack allows automatic `quote_request` emails. Lineguard discards an unsent draft when the shortage closes or known options cover it.

The `feed_stale` watcher reports a shipment feed when its latest known update exceeds the configured age. A feed with no known update time does not create this alert.

For an ERP correction, `approvals[]` includes `correction_payload` and `erp_writer`. A case detail includes the same payload and the writer for each correction. `proposal_file` saves a local JSON and CSV proposal. It does not update the ERP. The correction stays `handed_over` until a later ERP export confirms the quantity. If middleware fails, the writer is recorded as `proposal_file`.

| Endpunkt | Body | Wirkung |
|---|---|---|
| `POST /decisions/{id}/approve` | `{"option_id": 7}` oder leer für die Empfehlung | Entscheidung freigeben |
| `POST /decisions/{id}/reject` | `{"reason": "…"}` | Entscheidung ablehnen. Der Grund ist Pflicht |
| `POST /emails/{id}/approve` | `{"subject": "…", "body": "…"}`, beide optional | Entwurf senden, bei `DRY_RUN` nur ins Protokoll |
| `POST /emails/{id}/discard` | — | Entwurf verwerfen |
| `POST /corrections/{id}/approve` | — | Korrektur fürs ERP freigeben |
| `POST /corrections/{id}/reject` | `{"reason": "…"}` | Korrektur ablehnen. Der Grund ist Pflicht |
| `POST /corrections/{id}/count` | — | Zählung im Lager anfordern |
| `POST /sync` | — | Quelle jetzt prüfen. Antwort `{"changes": [...]}` |

Jede Antwort auf einen schreibenden Aufruf ist das geänderte Objekt.

## Waiting approvals in `/state`

`GET /state` holds two more lists. The page shows them in the section "Freigaben".

`approvals[]` lists each step that the agent prepared and that waits for a person. The most urgent entry comes first.

| Field | Meaning |
|---|---|
| `id` | Unique text, for example `decision:4` or `correction:1` |
| `type` | `decision` or `correction` |
| `object_id` | The id for `POST /decisions/{id}/approve` or `POST /corrections/{id}/approve` |
| `case_id` | The case with the evidence |
| `kind` | Kind of the recommended option, for example `confirm_terms`, or `erp_correction` |
| `title`, `summary` | Text for the person |
| `needs_roles`, `approver_name` | Required roles and suggested owner for the decision |
| `deadline`, `arrives_at` | Time limits as ISO text |
| `cost_eur`, `cost_unknown` | The cost. `cost_unknown` is true when the document names no cost |
| `commits_money` | True when the approval binds the company |
| `condition`, `conflict` | The term that the supplier demands, and the difference to the order |
| `note`, `after_deadline` | Remark of the plan. `after_deadline` is true when the goods arrive after the due date |
| `email` | The mail draft that goes out with the approval (`id`, `to_addr`, `subject`, `body`, `language`), or `null` |

`approvals_done[]` lists the last five clicks with `title`, `status`, `decided_by`, `decided_at`, `mail_status` and `mail_to`.

The option kind `confirm_terms` comes from the fact type `supplier_condition`. A supplier holds finished goods until the customer confirms a term in writing. The mail for this option always needs an approval. A rule with `applies_to: supplier_terms` in `approval_policy.yaml` names the required role. Without that rule, the rule for `purchase_order` applies with the value of the order line.
