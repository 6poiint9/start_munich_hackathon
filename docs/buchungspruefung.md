# Buchungsprüfung und ERP-Korrektur

Lies diese Datei, wenn du `lineguard/coverage/booking_check.py`, die Korrektur-Karte oder den `ErpWriter` baust.

## 1. Warum

Quelle: Gespräch mit Nils Berger, IT & Systems Lead bei Soony, Sa 21.11., 18:30 (Notizen von Ben, O-Ton sinngemäß; Zusammenfassung in `architecture.md` §0b).

Was Nils gesagt hat, gilt hier als Anforderung:

| Nr. | Aussage von Nils | Anforderung | Wo erfüllt |
|---|---|---|---|
| R1 | Fast alle Fehler macht ein Mensch: Der Fahrer übermittelt falsch, der Lieferant übermittelt falsch, jemand tippt eine 0 zu viel | Nie einer Quelle allein glauben. Jede Buchung gegen unabhängige Belege prüfen | §3, §4 |
| R2 | 80.000 statt 8.000 ist „der Klassiker“, Faktor 10. Kein Einzelfall, passiert häufiger | Faktor 10 ist eine eigene Ursache (`decimal_shift`). Der Rückblick zeigt, wie oft es vorkommt | §2, §4 |
| R3 | Der Fehler fällt erst auf, wenn das Teil gebraucht wird, meist beim Packen oder Versand. Nach ein paar Tagen oder nach Monaten | Prüfen beim Wareneingang, nicht an der Linie | §2 |
| R4 | Am meisten stört: Bei einem Fehler muss Nils selbst prüfen, ob es stimmt. Telefonieren, Mails, jemand schaut im Lager nach | Die Prüfzeit ist der eigentliche Aufwand. Lineguard sammelt die Belege und zeigt sie nebeneinander | §6 |
| R5 | SAP ist „heilig“. Nur Nils darf an die Datenbank. Es hängt an einer Person | Rolle `erp_owner`. Kein Schreiben ohne seine Freigabe oder seine Regel | §6a, §7 |
| R6 | Ticket einstellen lassen, dann je nach Auslastung sofort oder erst 2 Wochen später | Stock Truth rechnet sofort mit der belegten Menge und wartet nicht auf das ERP | §5 |
| R7 | Wenn es super wichtig ist, schaut ein Mensch drüber, sonst automatisch | Zwei Stufen: `human` und `auto`. Die Grenzen stehen im Paket, nicht im Kern | §6a |
| R8 | Die Middleware zum Schreiben ins SAP gibt es noch nicht. Soony würde sie bereitstellen. Bis dahin mocken, was geschrieben würde | `ProposalFileWriter` schreibt genau das, was später an die Middleware geht. `MiddlewareWriter` kommt später | §7 |
| R9 | Nils macht auch die Ursachenanalyse („warum ist das so gelaufen“) | Jeder Befund nennt Ursache und vermuteten Ort des Fehlers | §4 |

Die Buchungsprüfung findet den Fehler zum Zeitpunkt der Buchung. Sie gibt dem `erp_owner` einen fertigen Vorschlag mit Beleg, oder sie korrigiert nach seiner Regel selbst.

Kein neuer Agent. Die Prüfung ist deterministischer Code im Stock-Truth-Handler.

## 2. Auslöser

Stock Truth ruft `check_receipt(gr_fact)` auf, wenn ein Event `facts.updated` einen dieser Fakt-Typen enthält:

- `gr_qty` (neuer oder geänderter Wareneingang)
- `delivery_note_qty`, `delivery_note_weight_kg`, `delivery_note_packages`, `counted_qty`, `gr_exception_qty`, `po_line`, `shipped_qty`, `inspection_result` (neuer Beleg zu einer Bestellposition, die schon einen Wareneingang hat)

Der Reader liest von jedem Lieferschein-Scan Menge, Gewicht und Packstücke als getrennte Fakten. Eine handschriftliche Korrektur ersetzt die gedruckte Zahl. Die gedruckte Zahl bleibt als `value_text` erhalten.

Beim ersten Import läuft die Prüfung einmal über alle vorhandenen Wareneingänge (**Rückblick**). Das Ergebnis erscheint in der Oberfläche als eine Zeile: „N Wareneingänge geprüft, M Befunde“.

## 3. Prüfungen

Jede Prüfung liefert `pass`, `fail` oder `no_data` sowie den Vergleichswert und den Fakt, aus dem er kommt. `no_data` ist kein Fehler.

| Nr. | Name | Vergleich | `fail`, wenn |
|---|---|---|---|
| 1 | `gr_vs_po` | Summe aller Wareneingänge der Bestellposition gegen die bestellte Menge | Summe > Bestellmenge × (1 + `over_tolerance`) |
| 2 | `gr_vs_delivery_note` | Gebuchte Menge gegen die Menge auf dem Lieferschein (Fakt `delivery_note_qty`, auch handschriftliche Korrektur) | Werte sind verschieden |
| 3 | `gr_vs_weight` | Gewicht auf dem Lieferschein gegen gebuchte Menge × Stückgewicht | Verhältnis liegt außerhalb von `weight_ratio_range` |
| 4 | `gr_vs_packages` | Packstücke auf dem Lieferschein gegen gebuchte Menge ÷ übliche Menge je Packstück | Verhältnis liegt außerhalb von `weight_ratio_range` |
| 5 | `gr_vs_history` | Gebuchte Menge gegen den Median der letzten Wareneingänge desselben Teils vom selben Lieferanten | Menge > 5 × Median oder < Median ÷ 5 |
| 6 | `duplicate` | Gleicher Lieferschein, gleiche Bestellposition, gleiche Menge | Es gibt schon einen Wareneingang mit diesen drei Werten |
| 7 | `unreferenced` | Wareneingang ohne Bestellnummer oder mit unbekanntem Teil | Bestellnummer fehlt oder `material_id` steht nicht in den Stammdaten |
| 8 | `gr_note_exception` | Freitext der Buchung gegen gebuchtes Teil und gebuchte Menge. Der Reader liest den Freitext in Welle 2 und schreibt den Fakt `gr_exception_qty` mit Menge und Grund (`docs/import-und-routen.md` §4) | Der Freitext nennt eine Teilmenge, die ein anderes Teil ist, beschädigt ist oder fehlt |

Stückgewicht und Menge je Packstück stehen nicht in den Stammdaten. Der Kern leitet beide aus früheren Lieferscheinen desselben Teils ab (Median, mindestens 3 Lieferscheine). Sind es weniger, liefern Prüfung 3 und 4 `no_data`.

Teillieferungen sind normal: Zwei Wareneingänge mit zusammen 100 % der Bestellmenge bestehen Prüfung 1. Eine Unterlieferung ist kein Buchungsfehler und besteht Prüfung 1 ebenfalls.

Ein Befund entsteht, wenn Prüfung 1, 2, 6, 7 oder 8 `fail` ist, oder wenn mindestens zwei der Prüfungen 3 bis 5 `fail` sind. Eine einzelne auffällige Prüfung 3, 4 oder 5 senkt nur `confidence` der Menge.

## 4. Ursache und Vorschlag

```
references      = Vergleichsmengen aus allen Prüfungen mit Status fail oder pass
                  (Bestellmenge, Lieferschein-Menge, Menge aus Gewicht, Menge aus Packstücken)
proposed_qty    = Wert, den die meisten unabhängigen Quellen stützen (Toleranz ±2 %);
                  bei Gleichstand gewinnt die Quelle mit dem besseren Rang (architecture.md §2.3)
agreeing        = Anzahl unabhängiger Quellen, die proposed_qty stützen
ratio           = booked_qty / proposed_qty
```

| `cause` | Bedingung |
|---|---|
| `decimal_shift` | `ratio` liegt innerhalb von ±2 % bei 10, 100, 0,1 oder 0,01 |
| `unit_mismatch` | `ratio` oder 1/`ratio` entspricht der üblichen Menge je Packstück (±2 %) |
| `duplicate_booking` | Prüfung 6 ist `fail` |
| `unreferenced_receipt` | Prüfung 7 ist `fail` |
| `content_mismatch` | Prüfung 8 ist `fail`. `proposed_qty` = gebuchte Menge minus Menge aus dem Freitext. Der Freitext ist eine Quelle, deshalb entsteht ohne zweiten Beleg der Status `needs_count` |
| `quantity_mismatch` | alle anderen Fälle |

**Ort des Fehlers** (`origin_hint`, für die Ursachenanalyse von Nils):

| `origin_hint` | Bedingung |
|---|---|
| `handwritten_ignored` | Der Lieferschein hat eine handschriftliche Korrektur. Die Buchung folgt der gedruckten Zahl (`value_text`) |
| `supplier_document` | Die gedruckte Menge auf dem Lieferschein weicht von der Bestellung ab, ohne Handkorrektur, und die Buchung folgt ihr |
| `booking_entry` | Alle Belege stimmen überein, nur die Buchung weicht ab |
| `unknown` | Keiner der Fälle oben |

Beim Artbook (`5000413065`) ist es `handwritten_ignored`: Auf WZ-261116-473 ist „80.000“ durchgestrichen und „8 000“ von Hand geschrieben. Gebucht wurden 80.000.

Unabhängig sind zwei Quellen, wenn sie aus verschiedenen Dokumenten kommen. Menge und Gewicht auf demselben Lieferschein zählen als zwei Quellen, weil der Schreiber sie getrennt einträgt.

Entscheidung:

- `agreeing >= min_agreeing_sources` (Standard 2): Befund mit Status `proposed` und eine Korrektur (§6).
- Sonst: Befund mit Status `needs_count`. Stock Truth erstellt eine Aktion `count_request` an die Rolle `site_lead` („Bitte Teil X, Charge Y zählen“). Die Antwort kommt als Fakt `counted_qty` (Rang 1) zurück und löst die Prüfung neu aus.

## 5. Wirkung auf die Deckung

Stock Truth rechnet sofort mit `proposed_qty`, sobald ein Befund den Status `proposed` hat. Die Differenz ist der Posten „nachweislich falsch gebucht“ im Rechenkern (`architecture.md` §2.3). Die Rechnung wartet nicht auf die Korrektur im ERP.

Die Oberfläche zeigt beide Zahlen nebeneinander: „ERP: 80.000 · Lineguard rechnet mit: 8.000 · Korrektur offen seit 2 h“.

Lehnt der `erp_owner` die Korrektur ab, bekommt der Befund den Status `dismissed`, und Stock Truth rechnet wieder mit der ERP-Menge. Der Grund der Ablehnung ist ein Pflichtfeld und wird als Fakt (`extracted_by = human`) gespeichert.

## 6. Korrektur-Karte

Empfänger ist die Rolle `erp_owner` aus dem Paket. Die Karte zeigt:

1. Einen Satz: „Wareneingang 5000413065: 80.000 gebucht, 8.000 belegt. Vermutung: eine Null zu viel.“
2. Die Belege **nebeneinander** in einer Zeile: gebuchte Menge, Bestellposition, Ausschnitt des Lieferschein-Scans mit markierter Stelle, Gewichtsrechnung, Packstücke. Jeder Beleg hat einen Link auf Datei und Stelle. Ziel: Nils entscheidet auf der Karte, ohne Telefon, Mail oder Gang ins Lager (R4).
3. Die vorgeschlagene Buchung: Storno des Belegs und neuer Wareneingang mit `proposed_qty`.
4. Die Wirkung: „Deckung Collector's sinkt von +66.100 auf −5.900. Linie steht So 11:27.“
5. Ursache und Ort des Fehlers (`cause`, `origin_hint`).
6. Drei Knöpfe: **Korrektur freigeben** · **Ablehnen** (mit Grund) · **Zählung anfordern**.

Die Zahlen im Beispiel kommen aus den Fakten des Artbook-Falls. Die Karte baut ihren Text aus dem Befund, nicht aus einer Vorlage je Fall.

## 6a. Stufe: Mensch prüft oder automatisch

Regel von Nils (R7): Wenn es super wichtig ist, schaut ein Mensch drüber, sonst läuft es automatisch. Jeder Befund mit Status `proposed` bekommt deshalb eine Stufe (`tier`): `human` oder `auto`.

Der Kern kennt nur die Regel. Die Grenzen stehen im Paket unter `booking_check.tiers` (`docs/kern-und-kundenpaket.md` §3).

Ein Befund ist `human`, wenn mindestens eine Bedingung zutrifft:

1. `tiers.auto_enabled` ist `false`. Das ist der Standard im Kern.
2. Die Korrektur ändert eine Lücke mit `impact = deadline_blocker`, oder sie ändert die Deckung einer `demand_class` aus `tiers.human_demand_classes`.
3. Der Wert der Differenz (`delta_qty` × Preis aus der Bestellposition) ist größer als `tiers.auto_max_value_eur`. Fehlt der Preis, gilt `human`.
4. `cause` steht nicht in `tiers.auto_causes`.
5. `agreeing_sources` ist kleiner als `tiers.auto_min_agreeing_sources`.

Sonst ist der Befund `auto`:

- Die Korrektur ist durch die Regel freigegeben: `approved_by = policy:erp_write_auto`, dazu die Version des Pakets. Die Regel hat der `erp_owner` gesetzt, sie ist seine Freigabe im Voraus.
- Sie läuft über denselben `ErpWriter` wie jede andere Korrektur (§7).
- Sie steht in der Liste „Automatisch korrigiert“. Dort gibt es einen Knopf **Zurücknehmen**. Er erzeugt eine Gegenkorrektur, wieder über den `ErpWriter`.

Ein Befund mit Status `needs_count` ist nie `auto`. Ohne zweiten Beleg gibt es keinen Vorschlag.

Bei Soony ist der Artbook-Befund `human`: Er ändert die Deckung der Collector's Edition, eine Lücke mit `impact = deadline_blocker` (Bedingung 2). Die Werte für `auto_max_value_eur` und `auto_causes` hat Nils noch nicht genannt (offene Frage an Nils). Bis dahin steht im Soony-Paket `auto_enabled: false`. Die Stufe `auto` zeigt der Test mit dem erfundenen Paket `demo_bikes`.

## 7. Schreibweg ins ERP

SAP ist bei Soony geschützt. Laut Nils (Gespräch 21.11.) gibt es noch keine Middleware zum Schreiben. Soony würde sie bereitstellen. Bis dahin sollen wir mocken, was geschrieben würde, und später anbinden. Endpunkt und Zugang sind noch offen (`architecture.md` §11, Frage 15).

Der Mock ist der `ProposalFileWriter`. Die JSON-Datei, die er schreibt, ist genau der Body, den später der `MiddlewareWriter` sendet (gleiches Schema `Correction`, Feld `schema_version`). Der Wechsel ist dann nur `erp_writer.mode: middleware` im Paket plus `ERP_MW_URL` und `ERP_MW_TOKEN` in `.env`. Kein Code im Kern ändert sich.

Port in `lineguard/connectors/erp_writer.py`:

```python
class ErpWriter(Protocol):
    def apply(self, correction: Correction) -> WriteResult: ...   # idempotent über correction.idempotency_key
    def status(self, external_ref: str) -> WriteStatus: ...
```

| Implementierung | `erp_writer.mode` | Verhalten |
|---|---|---|
| `ProposalFileWriter` (Standard) | `proposal_file` | Schreibt `data/<workspace>/out/corrections/<id>.json` und hängt eine Zeile an `data/<workspace>/out/corrections.csv` an. Erstellt eine Mail an den `erp_owner` mit beiden Dateien. Status `handed_over` |
| `MiddlewareWriter` | `middleware` | `POST {ERP_MW_URL}/corrections` mit Token aus `ERP_MW_TOKEN`, Body = Korrektur als JSON, Header `Idempotency-Key`. Status `posted`. Bei Fehler nach 3 Versuchen: Rückfall auf `ProposalFileWriter` und Hinweis in der Oberfläche |

Jeder Schreibvorgang trägt `approved_by` und `approved_at`. Erlaubt sind nur zwei Werte für `approved_by`: eine Person mit der Rolle `erp_owner`, oder `policy:erp_write_auto` bei einem Befund mit `tier = auto` (§6a). `apply` prüft das als erste Zeile und bricht sonst mit `ApprovalMissing` ab.

Inhalt der Korrektur (`payload`): `schema_version`, `kind` (`gr_qty`), `gr_number`, `po_number`, `po_line`, `material_id`, `site`, `booked_qty`, `proposed_qty`, `delta_qty`, `cause`, `origin_hint`, `tier`, `evidence` (Liste aus Datei, Stelle, Wert), `finding_id`.

**Bestätigung durch Lesen:** Eine Korrektur gilt erst als erledigt (`verified`), wenn ein späterer ERP-Export die neue Menge zeigt. Der Reader liest den Export, `verify_corrections()` vergleicht und setzt den Status. Bis dahin bleibt die Karte sichtbar mit ihrem Alter.

## 8. Daten

Neue Tabellen (Ergänzung zu `architecture.md` §3):

| Tabelle | Spalten |
|---|---|
| `booking_findings` | `id`, `gr_fact_id`, `gr_number`, `component_id`, `supplier_id`, `po_number`, `po_line`, `booked_qty`, `proposed_qty`, `delta_qty`, `cause`, `checks` (JSON: Name → Status, Vergleichswert, `source_fact_id`), `agreeing_sources`, `confidence`, `origin_hint`, `tier` (`human/auto`), `status` (`proposed/needs_count/dismissed/corrected`), `booked_at`, `detected_at` |
| `corrections` | `id`, `finding_id`, `kind`, `payload` (JSON), `approver_role`, `status` (`proposed/approved/rejected/handed_over/posted/verified/failed`), `approved_by`, `approved_at`, `reject_reason`, `writer`, `external_ref`, `idempotency_key` (UNIQUE), `first_viewed_at`, `decided_at`, `reverts_correction_id`, `verified_at` |

Neue Events: `finding.created`, `correction.proposed`, `correction.approved`, `correction.auto_applied`, `correction.rejected`, `correction.reverted`, `correction.verified`.

`idempotency_key` = `<gr_number>:<kind>:<proposed_qty>`. Ein zweiter Lauf über denselben Wareneingang erzeugt keinen zweiten Befund.

Kennzahlen für den Business Case, aus den Tabellen berechnet:

- `detected_at − booked_at` je Befund (heute laut Nils: Tage bis Monate)
- `decided_at − first_viewed_at` je Karte: Prüfzeit des Menschen (heute laut Nils: Telefon, Mail, Gang ins Lager)
- `verified_at − detected_at` je Korrektur (heute laut Nils: sofort bis zwei Wochen)
- Anteil `auto` an allen Korrekturen: Arbeit, die gar nicht mehr bei Nils landet
- Anzahl der Befunde im Rückblick, je `cause` und `origin_hint`

## 9. Geprüft an den Daten

Stand der Datei `soony/erp/goods_receipts.csv` vom Freitag (392 Zeilen), von Hand nachgerechnet:

- Genau eine Zeile weicht um Faktor 10 ab: `5000413065` (bestellt 8.000, gebucht 80.000, Bemerkung „over delivery accepted“).
- Alle anderen Überlieferungen liegen bei höchstens +4,5 %. Deshalb steht `over_tolerance: 0.05` im Soony-Paket. Der Standard im Kern ist 0,10.
- 3 Zeilen haben keine Bestellnummer und ein unbekanntes Teil (`PRM-GH6-PIN`).
- Kein Lieferschein ist doppelt mit gleicher Position und gleicher Menge gebucht.

Nicht von Hand geprüft: der Vergleich aller 61 Lieferschein-Scans mit den Buchungen. Prüfung 2 kann deshalb weitere Befunde liefern. Jeder davon ist ein echtes Ergebnis und kein Testfehler.

Stand Sa 21.11., 22:45 (`goods_receipts_update.csv`, 4 Buchungen vom 21.11.):

- `5000413070`: 28.000 von 48.000 Spielkarten, Bemerkung „partial delivery“. Eine Teillieferung, kein Befund.
- `5000413071`: 20.000 Sleeves gebucht. Die Bemerkung nennt eine Palette mit 4.000 Stück eines anderen Teils, „booked per delivery note“. Das ist Prüfung 8. Nutzbar sind 16.000, bis eine Zählung es klärt.

Diese Zahlen stehen nur in `tests/test_booking_check.py` als erwartetes Ergebnis für den eingefrorenen Datenstand.

## 10. Fertig, wenn

1. Der Rückblick über den eingefrorenen Datenstand liefert genau einen Befund `decimal_shift` (`5000413065`, `proposed_qty` 8.000), 3 Befunde `unreferenced_receipt` und, sobald Welle 2 die Freitexte gelesen hat, einen Befund `content_mismatch` (`5000413071`, `proposed_qty` 16.000, Status `needs_count`). Keine Teillieferung und keine Unterlieferung erzeugt einen Befund aus Prüfung 1.
2. Der Befund zum Artbook hat `agreeing_sources >= 2`, und Stock Truth rechnet danach mit 19.300 nutzbaren Artbooks.
3. Ein Klick auf „Korrektur freigeben“ erzeugt die JSON-Datei, die CSV-Zeile und den Mail-Entwurf. Ein zweiter Klick erzeugt nichts Neues.
4. `apply` ohne Freigabe wirft `ApprovalMissing`.
5. Ein neuer ERP-Export mit der korrigierten Menge setzt die Korrektur auf `verified`.
6. Der Test mit dem Paket `demo_bikes` findet dort den Faktor-10-Fehler mit denselben Regeln.
7. `tests/test_booking_tiers.py`: Mit `demo_bikes` ist der Faktor-10-Befund am knappen Teil `human` und der kleine Befund am Teil mit viel Deckung `auto`. Der `auto`-Befund erzeugt ohne Klick die JSON-Datei mit `approved_by = policy:erp_write_auto`. **Zurücknehmen** erzeugt eine Gegenkorrektur. Mit `auto_enabled: false` sind alle Befunde `human`.
8. Der Artbook-Befund hat `tier = human` und `origin_hint = handwritten_ignored`.
