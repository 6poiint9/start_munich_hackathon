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

Jeder schreibende Aufruf braucht den Header `X-Lineguard-User: <person_id>`. Ohne Header antwortet die API mit HTTP 401. Mit einer Person ohne passende Rolle antwortet sie mit HTTP 403 und `detail` „Diese Freigabe braucht die Rolle <rolle>“. Die Oberfläche zeigt nur die Knöpfe, die die gewählte Person klicken darf. Dafür vergleicht sie `people[].roles` mit `needs_roles` oder `approver_role`.

| Endpunkt | Body | Wirkung |
|---|---|---|
| `POST /decisions/{id}/approve` | `{"option_id": 7}` oder leer für die Empfehlung | Entscheidung freigeben |
| `POST /decisions/{id}/reject` | `{"reason": "…"}` | Entscheidung ablehnen. Der Grund ist Pflicht |
| `POST /emails/{id}/approve` | `{"subject": "…", "body": "…"}`, beide optional | Entwurf senden, bei `DRY_RUN` nur ins Protokoll |
| `POST /emails/{id}/discard` | — | Entwurf verwerfen |
| `POST /corrections/{id}/approve` | — | Korrektur fürs ERP freigeben, nur Rolle `erp_owner` |
| `POST /corrections/{id}/reject` | `{"reason": "…"}` | Korrektur ablehnen. Der Grund ist Pflicht |
| `POST /corrections/{id}/count` | — | Zählung im Lager anfordern |
| `POST /sync` | — | Quelle jetzt prüfen. Antwort `{"changes": [...]}` |

Jede Antwort auf einen schreibenden Aufruf ist das geänderte Objekt.
