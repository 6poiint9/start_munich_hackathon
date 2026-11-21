# Skalierung: Nähte jetzt, Ausbau später

Lies diese Datei, bevor du `lineguard/db.py`, `lineguard/orchestrator.py`, den ersten Import oder `/state` baust, und wenn die Jury fragt, ob Lineguard über Soony hinaus trägt.

Entschieden am Sa 21.11., 20:20: Bis zur Abgabe entstehen nur die **Nähte**. Eine Naht ist eine Stelle im Code, an der ein späterer Ausbau ohne Umbau ansetzt. Der Ausbau selbst steht in §3 und wird nicht vor Sonntag gebaut.

## 1. Ergebnis der Prüfung

Geprüft wurden drei Arten von Wachstum. Nichts davon ist unter Last gemessen. Die Aussagen folgen aus dem Aufbau.

| Wachstum | Trägt heute | Trägt nicht | Naht jetzt | Ausbau später |
|---|---|---|---|---|
| Mehr Kunden | Kern ohne Kundenwerte, Paket je Kunde | Kein Kunden-Schlüssel in den Tabellen. Spalten `per_std` und `per_ce`, Feld `edition`, Wert `launch_blocker` sind Soony | N3, N4 | Stufe 1, Stufe 4 |
| Mehr Daten und Last | Fakten sind klein, die Rechnung ist Code, jede Datei-Version wird einmal gelesen, LLM-Antworten sind gecacht | Der Reader liest Dateien nacheinander. Ein Prozess, eine SQLite-Datei, Dateien auf der lokalen Platte, Polling | N1, N2, N5, N7 | Stufe 2, Stufe 3 |
| Mehr Entscheidungen für Menschen | Rangfolge, `triage`, Routine-Mails ohne Klick | Jede Lücke erzeugt Karten. Bei vielen Teilen sieht der Mensch die wichtige Karte nicht mehr | N6 | Stufe 5 |

Der dringendste Punkt betrifft schon Soony: Der Datenstand enthält 275 PDFs und Scans. Bei 20 bis 40 Sekunden je Datei (`architecture.md` §4) dauert der erste Import nacheinander 1,5 bis 3 Stunden.

## 2. Nähte, die jetzt gebaut werden

Der Aufwand in Klammern ist eine Schätzung.

### N1. Import in zwei Wellen, Reader parallel (1 h)

1. Welle 1 liest alle Tabellen (`*.csv`, `*.xlsx`) mit den deterministischen Parsern. Events `file.added` bekommen Priorität 1. Danach rechnet Stock Truth einmal. Die Oberfläche zeigt erste Lücken, bevor ein LLM gelaufen ist.
2. Welle 2 liest Dokumente, Scans und die Freitexte aus den Tabellen (`docs/import-und-routen.md` §4). Ein Dokument bekommt Priorität 1, wenn seine Route `priority: 1` setzt. Das gilt für Hinweise von Lieferanten und Prüfberichte: Sie ändern die Rechnung am stärksten und tragen oft keine Kennung im Namen. Ein Dokument bekommt Priorität 2, wenn sein Dateiname eine Kennung enthält (Bestellnummer, Lieferschein-Nummer, Sendungsnummer), die in einer offenen Bestellposition oder in einem Wareneingang der letzten 30 Tage vorkommt. Alle anderen Dokumente bekommen Priorität 3. Die Kennungen kommen aus den Fakten von Welle 1.
3. Der Orchestrator verarbeitet bis zu `READER_CONCURRENCY` Reader-Events gleichzeitig (Standard 8). Ein Semaphor `LLM_MAX_PARALLEL` (Standard 8) begrenzt alle LLM-Aufrufe im Prozess. Bei HTTP 429 wartet der Aufruf mit Backoff und Zufallsanteil.
4. Blockierende Aufrufe (tesseract, pdftotext, SMTP, IMAP) laufen in `asyncio.to_thread`.
5. Schreibe nie in die Datenbank, während ein LLM-Aufruf läuft: erst lesen, dann LLM, dann eine kurze Transaktion für Fakten und Event. SQLite erlaubt nur einen Schreiber. Verbindung mit `journal_mode=WAL` und `busy_timeout=5000`.

Der ERP-Bestand aus Welle 1 ist bis zum Ende von Welle 2 nur eine vorläufige Zahl. Die Kopfzeile zeigt deshalb „N von M Belegen gelesen“.

### N2. Events mit Claim, Lease und Partition (45 min)

Neue Spalten in `events`: `workspace_id`, `partition_key`, `coalesce_key`, `locked_by`, `locked_until`.

| Spalte | Regel |
|---|---|
| `partition_key` | Zwei Events mit demselben Schlüssel laufen nie gleichzeitig. Reader: `file:<path>`. Stock Truth und Decision: `component:<component_id>`. Action: `case:<case_id>` |
| `coalesce_key` | Ein UNIQUE-Index über `(workspace_id, coalesce_key)` nur für Zeilen mit `status = 'pending'`. Zehn neue Fakten zu einem Teil ergeben eine Neuberechnung. Der Reader schreibt je betroffenes Teil ein Event `facts.updated` mit `coalesce_key = facts.updated:<component_id>` und fängt den UNIQUE-Fehler ab |
| `dedupe_key` | Bleibt UNIQUE für immer je Workspace (`architecture.md` §6.3) |
| `locked_until` | Lease. Ein Event mit `status = 'processing'` und abgelaufener Lease (`LEASE_SECONDS`, Standard 300) wird wieder `pending` |

Genau eine Funktion `claim_next(worker_id, types)` in `lineguard/db.py` holt Events. Kein anderer Code setzt `status = 'processing'`. Diese Anweisung ist auf SQLite 3.54 getestet. `:types` wird im Code zu einer Liste von Platzhaltern erweitert:

```sql
UPDATE events SET status = 'processing', locked_by = :worker, locked_until = :now + :lease
WHERE id = (
  SELECT id FROM events
  WHERE status = 'pending' AND available_at <= :now AND type IN (:types)
    AND (partition_key IS NULL OR partition_key NOT IN (
         SELECT partition_key FROM events
         WHERE status = 'processing' AND partition_key IS NOT NULL))
  ORDER BY priority, id LIMIT 1)
RETURNING *;
```

Der Orchestrator startet je Handler-Gruppe eine feste Zahl von Tasks: Reader `READER_CONCURRENCY`, Stock Truth 2, Decision 2, Action 1. Die Werte stehen in `.env`, weil sie den Betrieb beschreiben und keinen Kunden.

Die Kopfzeile mit der Deckung ist kein gespeicherter Wert. `/state` berechnet sie beim Lesen aus `components` und `bom_lines`.

### N3. Kunden-Schlüssel `workspace_id` (ohne Mehraufwand, wenn `db.py` gerade entsteht)

Ein **Workspace** ist ein Kunde mit einer Frist und einem Paket. `pack.yaml` bekommt das Pflichtfeld `workspace` (bei Soony `soony_gh6`).

1. Jede Tabelle hat die Spalte `workspace_id TEXT NOT NULL`. Jeder UNIQUE-Schlüssel und jeder Index beginnt mit `workspace_id`.
2. Jede Lese- und Schreibfunktion in `db.py` nimmt `ws` als ersten Parameter. Agenten rufen nur diese Funktionen auf und schreiben kein eigenes SQL.
3. Dateien liegen unter `data/<workspace>/live/`, `data/<workspace>/versions/`, `data/<workspace>/out/`.
4. Der LLM-Cache-Schlüssel enthält `workspace_id`.
5. Heute läuft ein Prozess für genau einen Workspace (`LINEGUARD_PACK`).

### N4. Neutrales Datenmodell (30 min)

| Bisher | Neu |
|---|---|
| `components.per_std`, `components.per_ce` | Tabelle `bom_lines` (`workspace_id`, `product_id`, `component_id`, `qty_per`, `valid_from`) |
| keine Tabelle für Produkte | Tabelle `products` (`workspace_id`, `product_id`, `description`, `demand_units`, `packed`, `still_to_pack`, `rate_per_hour`) |
| `gaps.edition` | `gaps.product_id` |
| `gaps.copies_at_risk` | `gaps.units_at_risk` |
| `gaps.impact`: `launch_blocker`, `after_launch` | `deadline_blocker`, `after_deadline` (`no_impact` bleibt) |
| `launch_status` (je Edition) | `build_status` (`workspace_id`, `as_of`, `product_id`, `packed`, `still_to_pack`, `rate_per_hour`, `source_file_id`) |
| `config` (Launch-Zeit, Schichtplan) | entfällt: Frist aus `pack.yaml`, Schichtplan als Fakten |
| „Kopien gerettet STD/CE“ in einer Option | `units_gained` als Zuordnung `product_id` → Stück |
| `allocate(editions, priority=CE_first)` | `allocate(products, priority_order)` |

Zusätzlich bekommen `facts` und `gaps` die Spalte `site_id`. Bei Soony steht dort immer `DC-HAM`.

Die Wörter „Edition“, „Launch“ und „Kopien“ erscheinen nur in der Oberfläche, aus `pack.labels`.

### N5. Speicher hinter Schnittstellen (20 min)

1. `db.py` öffnet die Datenbank über `DATABASE_URL` (Standard `sqlite:///data/<workspace>/lineguard.sqlite`). SQL außerhalb von `claim_next` benutzt nur SQLModel oder Standard-SQL.
2. Dateien gehen über den Port `BlobStore` in `lineguard/connectors/blob.py` mit `put(key, bytes)`, `get(key)`, `exists(key)`. Die einzige Implementierung heute ist `LocalBlobStore`. `files.local_path` heißt `files.blob_key`.

### N6. Begrenzte Last für Menschen (30 min)

1. Eine Karte je **Fall**. Ein Fall ist ein Teil mit Lücke oder ein Wareneingang mit Befund. Neue Fakten ändern die vorhandene Karte und erzeugen keine zweite.
2. `/state` liefert die Kopfzeile, die ersten `STATE_TOP_N` Fälle nach Rang (Standard 50) und Zähler für den Rest („37 weitere Fälle, alle mit Plan“). Details lädt die Oberfläche je Fall über `/cases/{id}`.
3. Was ohne Klick läuft, steht als Daten im Paket, nicht im Code:

```yaml
auto_approve:
  action_kinds: [status_request, follow_up, count_request]   # nur Fragen
  max_cost_eur: 0
```

4. Jede Karte zeigt ihre Rolle. `/state?role=<rolle>` liefert nur die Karten dieser Rolle.

### N7. Messen statt schätzen (20 min)

| Messwert | Quelle | Wofür |
|---|---|---|
| `queue_lag_seconds` | Alter des ältesten Events mit `status = 'pending'` | Auslöser für Stufe 2 |
| `file_to_gap_seconds` | Zeit von `file.added` bis zum folgenden `gap.changed` oder bis zur Neuberechnung ohne Änderung | Zusage „Datei → Ampel unter 2 Minuten“ |
| `llm_calls` (Tabelle: `workspace_id`, `file_id`, `purpose`, `model`, `tokens_in`, `tokens_out`, `ms`, `cache_hit`) | `lineguard/llm.py` schreibt eine Zeile je Aufruf | Kosten je Datei und je Kunde für den Business Case |
| `open_cards_per_role` | Zählung in `decisions` und `corrections` | Auslöser für Stufe 5 |

`/healthz` liefert die vier Werte als JSON.

## 3. Ausbaupfad

Jede Stufe hat einen Auslöser, den N7 misst oder den ein Kunde nennt. Keine Stufe wird auf Verdacht gebaut.

| Stufe | Auslöser | Änderung | Was gleich bleibt |
|---|---|---|---|
| 0 (Abgabe) | — | Ein Prozess, eine SQLite-Datei, lokaler Ordner, ein Workspace | — |
| 1: 2 bis etwa 10 Kunden | Zweiter Kunde | Ein Container je Workspace mit eigenem Paket, eigener Datenbank, eigenem Postfach und eigenen Schlüsseln | Der gesamte Code. Kundendaten sind hart getrennt, das verlangen Einkaufsabteilungen ohnehin |
| 2: mehr Last je Kunde | `queue_lag_seconds` liegt dauerhaft über dem Ziel, oder ein zweiter Prozess muss schreiben, oder der Kunde verlangt Ausfallsicherheit | `DATABASE_URL` auf Postgres, `claim_next` mit `FOR UPDATE SKIP LOCKED`, mehrere Worker-Prozesse, `S3BlobStore` | Agenten, Regeln, Datenmodell, Events |
| 3: Push statt Polling | Das Auflisten der Quelle dauert länger als `poll_seconds`, oder der Kunde braucht Reaktion in Sekunden | Neue `SourceConnector`: Änderungsmeldungen aus dem ERP über die Middleware des Kunden, Webhook des Mail-Anbieters. Oberfläche über Server-Sent Events statt Polling | Watcher-Vertrag (`file.added`, `file.changed`), alles dahinter |
| 4: Vorrang über Termine und mehrere Standorte | Ein späterer Bedarf mit höherer Priorität muss einen früheren verdrängen, oder ein Kunde packt an zwei Orten | Verteilung nach Priorität über Termine in `allocate`, `site_id` in der Rechnung, Umlagerung als Option | Fakten, Buchungsprüfung, Schreibweg |
| 5: viele Entscheidungen | `open_cards_per_role` liegt über dem Wert, den der Kunde nennt | Eine Mail je Lieferant und Zyklus statt einer Mail je Fall. Sammelfreigabe für Befunde mit gleicher Ursache. Höhere Grenzen in `auto_approve`, belegt durch die Quote abgelehnter Karten | Freigaberegeln als Daten, Rollen, Audit |
| 6: Mandanten in einem Prozess | Betriebskosten von Stufe 1 werden zu hoch | Ein Prozess lädt mehrere Pakete. Zeilenschutz in Postgres über `workspace_id` | N3 hat die Spalte und die Funktionen schon |

Mehrere Bedarfstermine mit gemeinsamem Bestand rechnet Lineguard schon heute, streng in der Reihenfolge der Termine (`docs/dauerbetrieb.md` §4). Ohne Stufe 4 gilt: Vorrang über Termine hinweg und mehrere Standorte rechnet Lineguard nicht.

Was mit der Größe nicht teurer wird:

- Die Rechnung (Deckung, Buchungsprüfung, Optionen) ist Code ohne LLM. Sie läuft je betroffenes Teil, nicht über alle Teile.
- Ein LLM liest jede Datei-Version einmal. Ein `tick` der Schleife kostet keine Tokens, weil `explain` nur bei geänderter Eingabe läuft (Cache über den Hash der Eingabe).
- Ein neues Tabellenformat kostet einen LLM-Aufruf. Danach gilt das gespeicherte Mapping (`schema_maps`).

## 4. Antworten für die Jury

1. „Läuft das bei einem zweiten Kunden?“ Ja: neues Paket, gleicher Kern. Der Test `test_second_pack.py` zeigt es mit einem erfundenen Kunden, und `test_workspace_isolation.py` zeigt, dass zwei Kunden in einer Datenbank sich nicht berühren.
2. „Und bei hundertmal mehr Dateien?“ Der Reader läuft parallel und ist der einzige teure Schritt. Die Queue hat schon Claim und Lease, deshalb kommen weitere Worker ohne Umbau dazu. Der Wechsel auf Postgres ist eine Zeile Konfiguration und eine Funktion.
3. „Was kostet das je Kunde?“ Die Zahl kommt aus der Tabelle `llm_calls` für Soonys echten Datenstand, nicht aus einer Schätzung.
4. „Was skaliert nicht?“ Vorrang über mehrere Termine und mehrere Standorte (Stufe 4) und die Aufmerksamkeit des Menschen (Stufe 5). Beides hat einen Auslöser und einen Plan.

## 5. Fertig, wenn

1. `tests/test_claim.py`: Drei Worker rufen `claim_next` auf vier Events mit zwei gleichen `partition_key`. Zwei Worker bekommen je ein Event mit verschiedenem Schlüssel, der dritte bekommt keines. Ein Event mit abgelaufener Lease wird wieder geholt.
2. `tests/test_reader_parallel.py`: 40 Dateien, ein LLM-Ersatz mit 1 Sekunde Wartezeit, `READER_CONCURRENCY=8`. Der Lauf endet in unter 10 Sekunden, und jede Datei hat genau einen Satz Fakten.
3. `tests/test_import_order.py`: Nach Welle 1 gibt es Lücken, und kein LLM-Aufruf steht in `llm_calls`.
4. `tests/test_workspace_isolation.py`: Soony-Snapshot und `demo_bikes` in einer Datenbank liefern dieselben Lücken wie getrennt geladen.
5. `tests/test_no_customer_values.py` findet in `lineguard/` auch keinen der Namen `per_std`, `per_ce`, `edition`, `launch`.
6. Zehn neue Fakten zu einem Teil erzeugen genau ein offenes Event `facts.updated`.
7. `/healthz` liefert die vier Messwerte aus N7.

Bei Zeitnot entfallen in dieser Reihenfolge: N7 bis auf `llm_calls`, `/state?role=`, Test 4. N1 bis N4 bleiben.
