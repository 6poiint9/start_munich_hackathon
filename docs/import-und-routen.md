# Import und Routen: von der Kundendatei zum Fakt

Lies diese Datei, wenn du `routes.yaml` oder `source_rank.yaml` eines Pakets schreibst, oder wenn du `lineguard/agents/reader/` baust (`router.py`, `tables.py`, `documents.py`, `vision.py`).

Ein Teil des Wissens stammt aus dem Branch `origin/christian` (Paket `soony_tower`, Sa 21.11., 20:12). §7 ist am Portal-Stand von Sa 21.11., 22:45 geprüft.

## 1. Tabellenarten im Kern

Eine **Route** ordnet einem Pfadmuster einen Parser und eine Tabellenart (`kind`) zu. Der Kern kennt diese Arten. Jede Art hat Pflichtfelder mit neutralen Namen.

| `kind` | Pflichtfelder | Schreibt |
|---|---|---|
| `products` | `product_id` | `products`. Mit `demand_units` zusätzlich Fakt `demand`. Mit `demand_preordered` ein Fakt `demand` der Klasse `preordered`. Der Rest der Nachfrage bekommt die letzte Klasse aus `priority_order` |
| `components` | `component_id` | `components`, `released_rev` |
| `bom` | `product_id`, `component_id`, `qty_per` | `bom_lines` |
| `bom_change` | `product_id`, `component_id`, `effective_from` | Fakt `released_rev`, neue `qty_per` ab dem Datum, Sperre der alten Revision |
| `master_update` | Schlüssel, `field`, `new` | Fakt mit dem neuen Stammdaten-Wert und Datum |
| `demand` | `product_id`, `units`, `due_at` | Fakt `demand` (`docs/dauerbetrieb.md` §3) |
| `stock` | `material_id`, `quantity`, `snapshot_date` | `stock_qty` je Charge oder je Teil, `last_count`. Eine Zeile mit einer `product_id` ist `packed_qty` zum Zeitpunkt des Snapshots |
| `goods_receipts` | `gr_number`, `material_id`, `qty_received` | `gr_qty` |
| `delivery_notes` | `delivery_note`, `quantity` | `delivery_note_qty`, `delivery_note_weight_kg`, `delivery_note_packages` |
| `purchase_orders` | `po_number`, `po_line`, `material_id`, `quantity` | `po_line`, `artwork_rev` |
| `shipments` | `shipment_id`, `eta`, `status` | `inbound_qty` (Menge nach §3) |
| `planned_inbound` | `material_id`, `quantity`, `eta` | `inbound_qty` mit Rang der Quelle |
| `build_status` | `product_id`, `packed` | Tabelle `build_status`, `pack_rate` |
| `build_log` | `date`, `product_id`, `units_packed` | `packed_qty` je Tag für `actual_rate` |
| `shifts` | Tag, Zeitfenster | Fakt `capacity` je Schicht |
| `routes` | `origin`, `destination`, `transit_days` | Fakt `transit` für das letzte Stück vom Hafen zum Standort |
| `suppliers` | `supplier_id` | `contacts`, `release_status` |
| `supplier_parts` | `supplier_id`, `component_id` | `aliases`, Freitext nach §4 |
| `offers` | `component_id`, `quantity`, `valid_until` | Fakt `offer` |
| `validity` | Objekt, `valid_until` | Fakt mit `valid_until` für die Wächter |
| `person_roles` | `person_id`, `role` | Fakt `person_role` |

Fehlt ein Pflichtfeld nach der Zuordnung der Spalten, bekommt die Datei `parse_status = failed` und erscheint in der Leiste „Probleme“. Die anderen Dateien laufen weiter.

## 2. `routes.yaml` und `source_rank.yaml`

```yaml
# routes.yaml: die erste passende Route gewinnt
routes:
  - match: "erp/stock_snapshot*.csv"
    parser: table                 # table | report | json | document | vision
    kind: stock
    doc_class: erp_stock
  - match: "erp/purchase_orders*.csv"
    parser: table
    kind: purchase_orders
    doc_class: erp_movement
    columns: {LIFNR: supplier_id}             # optional: Spalte der Datei → Feld im Kern
    normalize: {supplier_id: "SUP-{:04d}"}    # optional: Format einer Kennung
    split: {po_numbers: "|"}                  # optional: Spalte mit mehreren Werten
  - match: "context/launch_status*.xlsx"
    parser: report                # mehrere Tabellen in einer Datei
    as_of: title                  # Zeitpunkt steht in der Titelzelle, je Blatt
    tables:
      - {kind: build_status, header: [Product, Packed]}
  - match: "suppliers/*/profile.json"
    parser: json
    kind: suppliers
    doc_class: erp_movement
    as_of: exportedAt
    columns: {supplier.supplierId: supplier_id, supplier.contact.email: contact_email,
              supplier.qualification.validUntil: valid_until}   # Pfad mit Punkten → Feld im Kern
  - match: "receiving/**/*.{jpg,png}"
    parser: vision
    doc_class: delivery_note
    expect: [delivery_note_qty, delivery_note_weight_kg, delivery_note_packages]
  - match: "suppliers/*/notices/*"
    parser: document
    doc_class: notice
    priority: 1                   # Vorrang in Welle 2 (docs/skalierung.md N1)
default: {parser: document, priority: 3}
```

```yaml
# source_rank.yaml: Dokumentklasse → Rang (architecture.md §2.3)
inspection_report: 1
delivery_note: 1
shipping_advice: 1
packing_list: 1
offer: 2
order_confirmation: 2
notice: 2
supplier_mail: 2
erp_movement: 3
erp_stock: 4
manual_list: 5
```

Bei `parser: document` und `parser: vision` nennt das LLM die Dokumentklasse im Feld `doc_class` der Antwort. Der Rang kommt dann aus `source_rank.yaml`. Eine Klasse ohne Eintrag bekommt Rang 5.

`columns` ist der feste Weg für ein bekanntes Format und braucht kein LLM. Das erfundene Paket `demo_bikes` nutzt ihn, damit seine Tests in der CI ohne LLM laufen.

## 3. Regeln für Tabellen

Reihenfolge beim Zuordnen der Spalten: `columns` der Route, dann die Alias-Liste des Kerns, dann ein gespeichertes Mapping aus `schema_maps`, dann `map_schema` mit dem LLM (`architecture.md` §6.1).

1. Kodierung in dieser Reihenfolge versuchen: `utf-8-sig`, `utf-8`, `cp1252`, `latin-1`.
2. Trennzeichen aus den ersten 20 Zeilen erkennen: `,` `;` Tab `|`.
3. Spaltennamen vor dem Vergleich normalisieren: Kleinbuchstaben, nur Buchstaben und Ziffern.
4. Die Alias-Liste des Kerns enthält die Feldnamen des ERP-Herstellers, zum Beispiel `EBELN`, `EBELP`, `LIFNR`, `MATNR`, `WERKS`, `MENGE`, `NETPR`, `BEDAT`, `EINDT`, `WEDAT`, `CHARG`. Diese Namen gelten für jeden Kunden mit diesem ERP und sind kein Kundenwert. Spalten mit dem Präfix `ZZ` sind Eigenbau eines Kunden und stehen in `columns` der Route.
5. Zahlen: `554.000` ist 554000. `1.234,5` und `1,234.5` sind 1234,5. `640,000` ist 640000. `1,5200` ist 1,52. Eine negative Menge ist ein Storno.
6. Datum: je Spalte entscheiden. Ein Wert über 12 an erster Stelle heißt Tag zuerst. Ist es offen, heißt ein Punkt Tag zuerst und ein Schrägstrich Monat zuerst.
7. Kennungen mit festem Format (`normalize`) und Spalten mit mehreren Werten (`split`) kommen aus der Route, nie aus dem Kern.
8. `parser: report` sucht jede Tabelle über ihre Kopfzeile: die erste Zeile, die alle Wörter aus `header` enthält. Der Zeitpunkt `as_of` kommt aus der Titelzelle des Blatts, als Datum mit Uhrzeit, als Datum allein oder als Wochentag mit Uhrzeit relativ zum nächsten Bedarfstermin. Zwei Blätter einer Datei können verschiedene Zeitpunkte haben.
9. Menge einer Sendung: Die Sendungsliste nennt oft keine Menge. Nimm die Menge aus `planned_inbound` mit derselben Referenz (Container, Frachtbrief). Gibt es keine, und die Sendung nennt genau eine Bestellung, nimm die offene Menge dieser Bestellposition. Sonst bleibt die Menge leer, und die Sendung zählt nicht als Zulauf.
10. Ankunft am Standort: `eta` am Hafen oder Flughafen plus `transit_days` der Route vom Zielort der Sendung zum Standort plus `coverage.default_handling_hours`.
11. Zulauf zählt nur mit der noch offenen Menge der Bestellposition: bestellte Menge minus Summe der Wareneingänge. Sonst zählt Ware doppelt, wenn die Sendungsliste älter ist als die Buchung. Bei Soony stehen zwei Sendungen auf `booked`, deren Ware schon im Bestand ist.
12. Je Tabellenart gewinnt die Quelle mit dem neuesten `as_of`, nicht ein bestimmter Dateiname. Das gilt für Bestand und für gepackte Stück. Ein neuerer Stand ersetzt die Fortschreibung „Bestand minus Verbrauch seit dem Snapshot“.
13. Nennt der neueste Bestand keine Chargen, gelten gesperrte Chargen aus dem letzten Bestand mit Chargen weiter, höchstens bis zur Gesamtmenge. Der Fall bekommt den Hinweis „Charge am Lager unbekannt“ und eine Aktion `count_request`.

## 4. Freitext in Tabellen

Spalten wie `note`, `remark` und `notes` enthalten Aussagen, die die Rechnung ändern. Beispiel aus den Daten: Ein Lieferant baut ein Teil in ein anderes ein, und es wird nie einzeln gebucht.

1. Welle 1 speichert jeden nicht leeren Freitext als Fakt `note` mit `value_text`, Zeile und Spalte. Welle 1 ruft kein LLM auf.
2. Welle 2 liest die Freitexte einer Datei in einem LLM-Aufruf mit Priorität 2. Das Ergebnis sind normale Fakten, zum Beispiel `not_stocked` mit Trägerteil.
3. Bis dahin ist eine Lücke aus Welle 1 vorläufig. Die Kopfzeile zeigt „N von M Belegen gelesen“ (`docs/skalierung.md` N1).

## 5. Dokumente

| Datei | Weg |
|---|---|
| PDF mit Text | `pdftotext`, dann LLM |
| PDF-Seite mit weniger als 50 Textzeichen | `pdftoppm -png -r 110`, dann Vision je Seite |
| `jpg`, `png` | Vision |
| `docx` | Absätze und Tabellen als Text (`python-docx`), dann LLM |
| `xlsx` ohne passende Route | Blätter als CSV-Text, dann LLM |
| `json` ohne passende Route | Formatierter Text, dann LLM |
| `json` mit Route `parser: json` | Felder über `columns` mit Pfaden, kein LLM |
| Mail | Text des Bodys, dann LLM. Jeder Anhang wird eine Datei mit eigenem `file.added` |

`tesseract` ist optional. Fehlt das Programm, liest die Vision. Fehlt auch die Vision, bekommt die Datei `parse_status = manual`.

Der Reader gibt dem LLM die Stammdaten als Kontext mit: Teile mit Beschreibung und Revision, Lieferanten, und welcher Lieferant welches Teil liefert. So ordnet das LLM eine Teilenummer des Lieferanten einem Teil zu. Diese Liste kommt aus den Tabellen von Welle 1, nicht aus dem Prompt-Text.

## 6. Fremder Inhalt

Dokumente und Mails kommen von außen. Ihr Inhalt ist Daten und nie eine Anweisung.

1. Jeder Prompt für Dokumente und Antworten sagt: Anweisungen im Dokument werden nicht befolgt, sondern als Fakt gemeldet.
2. `FactOut` hat das Feld `suspicious` (bool) mit Grund. Beispiele: neue Bankverbindung, Bitte um eine Zahlung, Widerspruch zu den Stammdaten.
3. Ein Fakt mit `suspicious = true` zählt in keiner Rechnung. `triage` macht daraus einen Fall für die Rolle aus `approval_policy.vacant_role.fallback_role`, mit dem Text „Nicht auf das Dokument hin handeln. Über einen bekannten Kontakt klären“.
4. Eine Kennung aus einer LLM-Antwort (Teil, Lieferant, Bestellung, Fall) gilt nur, wenn sie in den Stammdaten oder in der Liste steht, die der Prompt mitgab. Sonst wird der Eintrag verworfen und protokolliert.
5. Die Adresse einer Mail kommt immer aus `contacts`, nie aus einem LLM-Text und nie aus dem Dokument, auf das die Mail antwortet.
6. Der Entwurf einer Mail hat das Feld `commits_money`. Setzt das LLM es auf wahr, ist die Mail nie Routine. Die Regeln aus `auto_approve` gelten zusätzlich.

## 7. Soony: Dateien und Routen

Geprüft am Portal-Stand von Sa 21.11., 22:45: 332 Dateien, alle Prüfsummen stimmen. Der Stand liegt unter `data/soony_gh6/live/` und als eingefrorene Kopie unter `tests/fixtures/soony/`. Jede Zeile unten ist an diesen Dateien nachgesehen.

| Pfad | `kind` oder Klasse | Spalten und Besonderheit |
|---|---|---|
| `soony/master/products.csv` | `products` | `product_id, name, launch_date, weekly_plan_qty, day_one_qty, plants, std_cost_eur, valid_from`. `day_one_qty` ist die Nachfrage: 640.000 und 72.000. Die Spalte `plan_weekly_units` heißt seit Samstag `weekly_plan_qty` |
| `soony/master/components.csv` | `components` | `component_id, description, category, critical, drawing_rev` |
| `soony/master/components_update_*.csv` | `master_update` | `component_id, field, old, new, changed_by` |
| `soony/master/bom.csv` | `bom` | `parent_id, child_id, qty_per, valid_from, valid_to` |
| `soony/master/bom_delta_*.csv` | `bom_change` | `change_id, parent_id, child_id, action, qty_per_old, qty_per_new, rev_old, rev_new, use_up_old_rev, effective_from, reason`. `use_up_old_rev = N` sperrt die alte Revision. `Y` sperrt sie nicht. Die Datei enthält beide Fälle |
| `soony/master/routes.csv` | `routes` | `route_id, origin, destination, mode, transit_days` |
| `soony/erp/stock_snapshot.csv` | `stock` | `snapshot_date, site, material_id, batch, quantity, last_count`. Stand 20.11., mit Chargen. Zwei Zeilen tragen die `product_id` der Editionen |
| `soony/erp/stock_update_*.xlsx` | `report` | Zwei Blätter mit je eigener Titelzelle. `Components`: Kopf `Site, Material, Description, Qty, UoM, Receipts today, Used today, Last count`, Stand „after receipts 2026-11-21, late shift“, ohne Chargen. `Finished goods`: Kopf `Site, Material, Description, Qty, UoM, Packed today, Last count`, Stand 21.11., 20:50. Mengen als Text mit Punkt (`602.000`). Das ist der neueste Stand für Bestand und gepackte Stück |
| `soony/erp/goods_receipts.csv`, `goods_receipts_update.csv` | `goods_receipts` | `gr_number, gr_date, po_number, po_line, supplier_id, material_id, plant, qty_ordered, qty_received, delivery_note, inspector, remark`. Die Update-Datei hat 4 Buchungen vom 21.11. Der Freitext `remark` trägt Aussagen wie „over delivery accepted“ oder eine falsch beschriftete Palette |
| `soony/erp/purchase_orders_2025H2-2026.csv` | `purchase_orders` | `po_number, po_line, supplier_id, material_id, quantity, unit_price, promised_date, status, buyer, incoterm, note` |
| `soony/erp/purchase_orders_legacy_*.csv` | `purchase_orders` | Trennzeichen `;`, SAP-Namen, `ZZCONF` ist `promised_date`, `ZZSTAT` ist `status`, Lieferant als Zahl, Datum als `MM/DD/YYYY` |
| `soony/erp/open_shipments.csv` | `shipments` | `shipment_id, mode, reference, supplier_id, po_numbers, material_ids, origin, destination, dest_site, eta, status, updated_at, note`. `po_numbers` und `material_ids` mit `|` getrennt, keine Menge. Status: `booked`, `in_transit`, `delayed`, `arrived_port`, `in_delivery`. Die Datei ist seit dem 20.11. unverändert: Zwei Sendungen stehen auf `booked`, obwohl ihr Wareneingang am 21.11. gebucht ist |
| `soony/erp/packout_log.csv` | `build_log` | `date, site, product_id, line, units_packed` |
| `soony/context/launch_plan_GH6.xlsx` | `report` | Stand in der Titelzelle: „status 2026-11-20 18:00“. `Editions`: Kopf `Edition, Product, Day-one demand, of which pre-orders, Packed, Still to pack, Rate per hour`. Die Spalte `of which pre-orders` nennt 415.000 und 72.000. `Inbound`: Kopf `Supplier, Part, Quantity, Mode, Reference, ETD, ETA, Status, Comment`. `Shifts`: Kopf `Day, Shift, Hours, Lines`. `Notes`: Kopf `Note` |
| `soony/context/launch_status.xlsx` | `report` | Titelzelle „Saturday 13:00“. Zwei Kopfzeilen, die zweite ist `Name, Product, Day-one demand, Packed, Still to pack, Rate per hour, Line status`. Mengen als Text mit Punkt |
| `soony/context/memo_launch_priorities.docx` | `document` | Memo des CPO: Rangfolge, Freigaben, Auftrag „zweite Quelle für jedes Teil mit einem Lieferanten“ |
| `soony/context/*.pdf` | `document` | Freigaberegeln PP-07, Organigramm v1 und v2. Text-PDFs. Im Organigramm stehen Name und Rolle in Spalten untereinander. Die Zuordnung Person zu Rolle liest das LLM |
| `soony/news/*.json` | `document` | `items[]` mit `headline, summary, published_at, regions, tags`. Kein Bezug zu einem Teil im Text: `triage` entscheidet über die Wirkung |
| `soony/logistics/*.xlsx` | `manual_list` | Tracker: `Shipment, Carrier, Mode, Container/AWB, Supplier, POs, From, To, ETD, ETA, Status, Comment`. Rang 5 |
| `soony/receiving/DC-HAM/*.jpg|png` | `delivery_note` | 72 Scans. Der Dateiname enthält die Lieferschein-Nummer aus `goods_receipts.delivery_note` |
| `soony/receiving/DC-HAM/inspection_report_*.pdf` | `inspection_report` | Priorität 1 |
| `suppliers/*/profile.csv` | `suppliers` | `supplier_id, name, status, qualification_status, contact_name, contact_email, preferred_language, notes` |
| `suppliers/*/profile.json` | `suppliers` | Neuer Export für 2 von 6 Lieferanten, verschachtelt: `supplier.supplierId`, `supplier.contact.email`, `supplier.contact.language`, `supplier.qualification.status`, `supplier.qualification.validUntil`, `supplier.status`, `exportedAt`. Der Export ist neuer als `profile.csv` und gewinnt. Er nennt als einzige Tabelle das Ende einer bedingten Freigabe |
| `suppliers/*/components.csv` | `supplier_parts` | `component_id, unit_price, lead_time_days, moq, primary, note`. Die `supplier_id` steht im Ordnernamen. `note` nennt das eingebaute Teil |
| `suppliers/*/components_delta.csv` | `master_update` | `component_id, supplier_id, action, lead_time_days_old, lead_time_days_new, note` |
| `suppliers/*/order_confirmations/*.pdf` | `document` | 204 PDFs: Auftragsbestätigung (`OA*`), Versandavis (`Shipping_advice_*`), Packliste (`PL_*`). Der Dateiname endet mit der Bestellnummer |
| `suppliers/*/notices/*` | `notice` | PDF und Preislisten als `xlsx`, Priorität 1 |
| `suppliers/*/contracts/*.pdf` | `document` | Verträge mit Laufzeit |

Von 217 PDFs haben 214 Text. Für sie reicht `pdftotext` mit dem schnellen Modell. Nur 3 PDFs und die 72 Scans brauchen die Vision.

Der Besitzer eines Teils ohne Treffer in den Freigaberegeln ist der Einkäufer, der es am häufigsten bestellt (`purchase_orders.buyer`, nur volle Namen).

## 8. Vorlagen im Branch

Diese Funktionen sind erprobt. Lies sie mit `git show origin/christian:soony_tower/<datei>` und übernimm die Logik in den Kern. Kundenwerte, die dort im Code stehen, wandern dabei ins Paket.

| Für | Vorlage |
|---|---|
| `tables.py`: Kodierung, Trennzeichen, Zahlen, Datum, Alias-Liste | `tables.py`: `_read_text`, `_sniff_delimiter`, `parse_number`, `parse_dates`, `map_columns`, `ALIASES` |
| `parser: report` | `model.py`: `_find_header`, `_as_of_from_title`, `_read_context_reports` |
| Menge und Ankunft einer Sendung | `forecast.py`: `_inbound`, `_last_leg_days` |
| `SourceConnector` `portal_api` | `portal.py`: `sync`, `_seed_manifest_from_disk` |
| `docx` und `xlsx` als Text | `documents.py`: `content_parts` |
| Antworten zuordnen, Anhänge speichern | `mail.py`: `_match`, `_text_of`, `_save_attachments`, `poll` |

Nicht übernehmen: den Zustand in JSON-Dateien, `risks.py` (Regeln und Texte je Fall im Code), die Einstufung der Dringlichkeit durch das LLM, die Seite `cockpit/index.html`, die Bindung an Gemini.
