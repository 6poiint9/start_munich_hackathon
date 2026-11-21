# Dauerbetrieb: Lineguard nach der ersten Frist

Lies diese Datei, wenn du `lineguard/coverage/core.py`, `lineguard/coverage/watch.py`, die Tabelle `cases` oder die Liste „Danach“ in der Oberfläche baust.

## 1. Warum

Lio hat am Sa 21.11., 19:48 klargestellt: Gesucht ist ein Produkt, das nach dem Wochenende weiterläuft, und eine wartbare Lösung für lange Nutzung (`architecture.md` §0c).

Die Architektur hing bis dahin an genau einer Frist. Nach So 20:00 hätte Lineguard bei Soony keine Lücke mehr gerechnet, und die Liste „Nach dem Launch“ war ein Hinweis ohne Besitzer.

Entschieden am Sa 21.11., 20:55: Die Frist ist ein **Bedarfstermin** unter mehreren. Lineguard läuft auch ohne offenen Bedarfstermin weiter.

## 2. Was immer läuft und was einen Bedarfstermin braucht

| Fähigkeit | Braucht einen Bedarfstermin | Läuft nach der Frist |
|---|---|---|
| Buchungsprüfung je Wareneingang (`docs/buchungspruefung.md`) | nein | ja, bei jedem neuen Wareneingang |
| Release Gate je Charge | nein | ja |
| Wächter über Bestellungen, Freigaben und Verträge (§5) | nein | ja |
| Nachhaken bei Lieferanten (Action Agent) | nein | ja |
| Deckung und Lückenschluss (`docs/lueckenschluss.md`) | ja | ja, für den nächsten Bedarfstermin |

Gibt es keine Bedarfszeile mit `due_at` in der Zukunft, schreibt Stock Truth keine Lücken. Die Kopfzeile zeigt dann „Kein offener Bedarfstermin“ und die Zähler der offenen Fälle.

## 3. Bedarfszeilen

Eine **Bedarfszeile** sagt: so viele Stück eines Produkts bis zu einem Zeitpunkt.

Tabelle `demand_lines`: `id`, `product_id`, `class`, `units`, `due_at`, `source` (`pack` oder `fact_id`).

Quellen, in dieser Reihenfolge:

1. Fakten vom Typ `demand` aus Kundendateien (Produktionsplan, Kundenaufträge, Abrufe). Der Reader liest sie wie jeden anderen Fakt.
2. `demand` in `pack.yaml`. Eine Zeile ohne eigenes `due_at` bekommt `deadline` aus dem Paket.

Bei Soony gibt es heute drei Zeilen mit demselben `due_at` (So 22.11., 20:00). `products.demand_units` ist die Summe der Zeilen des Produkts.

## 4. Rechnung über mehrere Bedarfstermine

```
lines = demand_lines mit due_at > jetzt, sortiert nach (due_at, Position der class in priority_order)
rest  = usable_stock je Teil
für line in lines:
    need    = Stückliste × noch offene Stück der Zeile
    inbound = Zulauf mit Ankunft ≤ latest_useful_arrival(line), der noch keiner früheren Zeile zugeteilt ist
    gap(line, Teil) = rest + inbound − need
    rest    = max(0, rest + inbound − need)
```

- `still_to_pack` eines Produkts wird in der Reihenfolge von `due_at` auf seine Zeilen verteilt.
- `gaps` bekommt die Spalte `due_at`. `breaks_at`, `act_by` und `latest_useful_arrival` beziehen sich auf die Zeile der Lücke.
- Bei genau einem Bedarfstermin ist das Ergebnis dasselbe wie in `architecture.md` §2.3.

Grenze: Die Rechnung teilt den Bestand streng nach Termin zu. Ein späterer Bedarf mit höherer Priorität verdrängt keinen früheren Bedarf. Mehrere Standorte rechnet sie nicht (`docs/skalierung.md` §3, Stufe 4).

## 5. Wächter

Ein **Wächter** ist eine Regel, die ohne Lücke einen Fall erzeugt. Jeder Wächter ist eine Funktion in `lineguard/coverage/watch.py`, liest nur Fakten und läuft bei `facts.updated` und einmal je Stunde bei `tick`.

| `rule` | Liest | Fall entsteht, wenn | Erste Aktion | `act_by` |
|---|---|---|---|---|
| `revision_mismatch_open_po` | Offene Bestellposition, Fakt `artwork_rev` der Bestellung, `released_rev` des Teils | Die Revision der Bestellung ist nicht die freigegebene | Entscheidung „Bestellung ändern oder stoppen“ an die Rolle aus `policy.route`, Mail-Entwurf an den Lieferanten | Frühester Versand- oder Liefertermin der Position minus `watch.default_notice_days` |
| `validity_expiring` | Jeder Fakt mit `valid_until` (Vertrag, Lieferanten-Freigabe, Angebot) | `valid_until` liegt in der Vergangenheit oder innerhalb von `horizon_days`, und es gibt offene Bestellungen, Bestand oder eine Option, die davon abhängt | Entscheidung „verlängern, ersetzen oder auslaufen lassen“ | `valid_until` minus Kündigungs- oder Meldefrist aus dem Dokument, sonst minus `watch.default_notice_days` |
| `promise_passed` | Offene Bestellposition mit zugesagtem Termin, Wareneingänge, Versandavis | Der zugesagte Termin ist vorbei, und es gibt weder Wareneingang noch Versandavis | Statusnachfrage als Routine-Mail. Nach `mail.follow_up_hours` ohne Antwort: Eskalation | sofort |
| `po_unconfirmed` | Offene Bestellposition, Auftragsbestätigungen | `watch.confirm_days` nach dem Bestelldatum fehlt die Auftragsbestätigung | Statusnachfrage als Routine-Mail | sofort |
| `shipment_silent` | Sendungen mit `updated_at`, die als Zulauf in einer Deckung zählen | Die Sendung hat länger als `watch.silent_after_hours` (je Transportart) kein Update, während andere Sendungen derselben Quelle eines hatten | Statusnachfrage als Routine-Mail an den Lieferanten: aktuelle Position und Sendungsnummer | sofort |
| `feed_stale` | Das neueste `updated_at` einer Quelle | Die ganze Quelle ist älter als `watch.feed_stale_hours` | Ein Fall für die Rolle `erp_owner`: „Läuft der Export noch?“. Die einzelnen Sendungen erzeugen dann keinen Fall `shipment_silent` | sofort |

| `single_source` | Teile mit genau einem Lieferanten in `supplier_parts`, Fakt `policy_rule` mit einem Auftrag dazu | Ein Teil der Stückliste hat nur einen Lieferanten, und eine Regel des Kunden verlangt eine zweite Quelle | Ein Fall je Teil in der Liste „Danach“ für den Besitzer des Teils | Termin aus der Regel |

Bis zur Abgabe entstehen `revision_mismatch_open_po` und `validity_expiring`. `promise_passed`, `shipment_silent`, `feed_stale` und `single_source` folgen, wenn Zeit bleibt. `po_unconfirmed` kommt danach. Die Idee zu `shipment_silent` und `feed_stale` stammt aus dem Branch `origin/christian`: Stille wird gegen das neueste Update derselben Quelle gemessen, damit ein alter Export ein Fall ist und nicht 25.

Ein Fakt mit Wirkung nach dem nächsten Bedarfstermin bekommt weiter `impact = after_deadline` (`architecture.md` §2.3). Neu ist: Er wird ein Fall mit Besitzer und Datum und bleibt kein Hinweis.

## 6. Fälle

Die Oberfläche zeigt **Fälle**. Ein Fall ist genau eine Zeile in der Tabelle `cases`:

| Spalte | Inhalt |
|---|---|
| `id`, `kind` | `gap`, `booking_finding`, `watch` |
| `rule` | Name des Wächters, sonst leer |
| `component_id`, `supplier_id`, `po_number` | Bezug |
| `title` | Ein Satz, aus den Fakten gebaut |
| `impact` | `deadline_blocker`, `after_deadline`, `no_impact` |
| `due_at`, `act_by` | Termin des Bedarfs oder der Sache, spätester Zeitpunkt zum Handeln |
| `owner_role` | aus `policy.route` |
| `state` | `open`, `plan_proposed`, `approved`, `in_execution`, `confirmed`, `closed`, `unclosable`, `dismissed` |
| `evidence_fact_ids` | JSON |
| `dedupe_key` | UNIQUE: `<kind>:<rule>:<Objekt>`, zum Beispiel `watch:validity_expiring:<fact_id>` |

`gaps`, `booking_findings`, `decisions`, `actions` und `emails` tragen `case_id`. `gaps.case_state` aus `docs/lueckenschluss.md` §6 ist `cases.state`.

Zwei Listen in der Oberfläche:

1. **Jetzt:** Fälle mit `impact = deadline_blocker`, nach Rang. Für sie läuft die Schleife aus `docs/lueckenschluss.md`.
2. **Danach:** Fälle mit `impact = after_deadline`, nach `act_by`. Jede Zeile zeigt Titel, Besitzer und Datum.

Ein Fall wechselt von „Danach“ zu „Jetzt“, wenn `act_by` innerhalb von `coverage.horizon_days` liegt oder wenn sein Bedarfstermin der nächste wird. Ab dann gelten Entscheidung, Freigabe und Eskalation wie bei jedem anderen Fall.

Neue Werte im Paket:

```yaml
coverage: {horizon_days: 30}
watch: {default_notice_days: 14, confirm_days: 5}
```

## 7. Nach einem Bedarfstermin (Plan, nicht vor der Abgabe)

1. **Abschluss:** Wenn `due_at` vorbei ist, schreibt Lineguard einen Bericht aus den Tabellen: erreichte Deckung, fehlende Stück, Befunde, Entscheidungen mit Dauer, Kosten der Optionen.
2. **Gedächtnis:** Aus zugesagtem und echtem Termin je Lieferant entsteht eine Quote. Sie ersetzt die festen Werte für `confidence` in `docs/lueckenschluss.md` §4.
3. **Tagesblatt:** Eine Seite je Tag und Rolle per Mail: neue Fälle, fällige Entscheidungen, was Lineguard von selbst erledigt hat.

## 8. Fertig, wenn

1. `tests/test_demand_lines.py`: Das Paket `demo_bikes` hat zwei Bedarfstermine. Der frühere Termin wird zuerst gedeckt, und die Lücke steht beim späteren.
2. Die Zahlen aus `tests/test_stock_truth.py` für Soony bleiben gleich.
3. `tests/test_watch.py` mit `demo_bikes`: Eine offene Bestellung mit nicht freigegebener Revision und ein Vertrag mit `valid_until` in 10 Tagen erzeugen je einen Fall mit `owner_role` und `act_by`. Ein zweiter Lauf erzeugt keinen zweiten Fall.
4. Auf dem Soony-Datenstand erzeugen die Wächter Fälle für die drei Punkte aus `architecture.md` §0a, Absatz „Nach dem Launch“, soweit die Fakten dazu gelesen sind: offene Bestellungen mit Sleeves Rev. B, der auslaufende Rahmenvertrag, die abgelaufene Lieferanten-Freigabe.
5. Mit einer Systemzeit nach dem letzten `due_at` startet der Kern, zeigt „Kein offener Bedarfstermin“, prüft einen neuen Wareneingang und zeigt die Liste „Danach“.
6. `watch.py` enthält keinen Kundenwert (`tests/test_no_customer_values.py`).
