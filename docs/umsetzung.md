# Umsetzung: Schritte in Reihenfolge

Beginne hier, wenn du Lineguard baust. Diese Datei nennt die Reihenfolge und das Fertig-Kriterium je Schritt. Was zu bauen ist, steht in der Spezifikation, die der Schritt nennt. `architecture.md` §9 nennt, wer wann arbeitet.

## Regeln für jeden Schritt

1. Lies die genannten Abschnitte, bevor du Code schreibst.
2. Ein Schritt ist fertig, wenn seine Tests grün sind und `pytest -q` insgesamt grün ist.
3. Committe nach jedem Schritt. Committe nur Code, Tests und das erfundene Paket `demo_bikes`. `data/`, `.env`, `packs/soony_gh6/`, `tests/fixtures/soony/` und `tests/golden/soony_gh6/` stehen in `.gitignore`, weil das Repo öffentlich ist und Kundendaten das Team nicht verlassen dürfen.
4. Erwartete Zahlen von Soony stehen nur in Tests mit `@pytest.mark.customer_data`.
5. Baue die Stufen in der Reihenfolge 0, A, B, C. Stufe D beginnt spätestens So 10:30, egal wie weit A bis C sind.
6. Der Branch `origin/christian` (Paket `soony_tower`) wird nicht gemergt. Er ist die Vorlage für die Funktionen aus `docs/import-und-routen.md` §8. Alles andere entsteht neu nach diesen Spezifikationen.
7. Jeder Befehl läuft auch ohne `make`: `python -m lineguard init|run|eval|demo-reset`. Das `Makefile` ruft nur diese Befehle auf. Grund: Ein Teil des Teams arbeitet unter Windows.

## Stand der Umsetzung (So 22.11., früh)

Gebaut und mit Tests belegt (`pytest -q`: 76 Tests, CI grün): A1 bis A4, A5 (API), A6 bis A10, B2, B3. Die Seite unter `web/` (A5, Oberfläche) ist in Arbeit.

Auf dem eingefrorenen Soony-Stand liefert die Kette aus echten Dokumenten: Artbook −5.900 (Buchungsbefund `decimal_shift` mit zwei Quellen), Statue −3.400 (Prüfbericht), Hüllen −32.000, Spielkarten −6.800, Sleeves ohne Lücke nach Abzug von 64.000 Rev. B und 4.000 falsch beschrifteten Stück, Magnete ohne Alarm. „System sagt“ 100 %, gesichert 91,8 % und 95,0 %.

Abweichungen von den Spezifikationen:

| Thema | Gebaut | Spezifikation |
|---|---|---|
| Orchestrator | Worker-Threads je Gruppe, jeder mit eigener Datenbank-Verbindung | asyncio-Loop |
| Neuberechnung | Stock Truth rechnet bei jedem `facts.updated` den ganzen Workspace. Alle diese Events teilen die Partition `coverage` | je betroffenes Teil |
| Generatoren | `accept_offer`, `release_held`, `expedite_inbound`, `rework_sort` in `coverage/options/standard.py`. `reallocate` steckt in der Zuteilung, `count_request` kommt aus der Buchungsprüfung | ein Generator je Datei, dazu `deliver_after_deadline` |
| Vorrang in Welle 2 | Nur über `priority` der Route | zusätzlich über Kennungen im Dateinamen |
| Nachprüfung mit dem großen Modell | nicht gebaut. Das schnelle Modell liest die korrigierte Menge richtig | asynchron bei abweichender Druckmenge |

Nicht gebaut: `python -m lineguard eval` und das Golden Set (W4), JSON-Protokoll (W5), `pack check`, `/state?role=`, Fakten-Diff in der Oberfläche (B1; ersetzte Dateien werden verarbeitet und alte Fakten als ersetzt markiert), Widersprüche als eigene Tabelle, Stufe D bis auf README und `demo-save` / `demo-reset`.

## Stufe 0: Vorbedingungen

Ohne diese Punkte liefert Stufe A falsche Zahlen. Stand Sa 21.11., 22:45 auf dem Rechner, auf dem diese Datei entstand: 0.1 bis 0.5 sind erfüllt (332 Dateien, alle Prüfsummen stimmen). Auf jedem anderen Rechner sind 0.1 bis 0.4 zu wiederholen. Vor Stufe B und vor Stufe D lädt der Watcher den Stand neu, weil das Portal weitere Dateien bekommt.

| Nr. | Punkt | Fertig, wenn |
|---|---|---|
| 0.1 | Das Team-Token aus dem Portal (Settings) steht in `.env` als `PORTAL_TOKEN`. Im Branch heißt derselbe Wert `LIO_TOKEN` | Der erste Befehl unten liefert eine Dateiliste |
| 0.2 | Der aktuelle Datenstand liegt unter `data/soony_gh6/live/`. Die Kopie unter `/tmp/soony/soony-data/` ist der Stand von Freitag (308 Dateien) und reicht nicht | Die Dateiliste hat mindestens 332 Einträge. Unter `soony/context/` liegen `launch_status*.xlsx` und das Memo des CPO, unter `soony/master/` liegt `bom_delta_*.csv` |
| 0.3 | Eine Kopie dieses Stands liegt als eingefrorener Snapshot unter `tests/fixtures/soony/`, mit dem Zeitpunkt in `tests/fixtures/soony/AS_OF` | Der Ordner steht in `.gitignore` und ist gefüllt |
| 0.4 | Werkzeuge: Python ab 3.12, Node, `pdftotext` und `pdftoppm` (poppler). `tesseract` ist optional | `python3 --version`, `node --version`, `pdftoppm -v` laufen |
| 0.5 | `docs/import-und-routen.md` §7 ist am aktuellen Stand geprüft. Kommt eine neue Datei dazu, bekommt sie eine Zeile in §7 und eine Route im Paket | Jede Datei des Stands trifft eine Zeile in §7 |

```bash
set -a; . ./.env; set +a
curl -fsS -H "Authorization: Bearer $PORTAL_TOKEN" "$PORTAL_BASE/api/v1/files" | head -c 400
mkdir -p data/soony_gh6/live
curl -fsS -H "Authorization: Bearer $PORTAL_TOKEN" "$PORTAL_BASE/api/v1/archive.zip" -o data/soony_gh6/archive.zip
unzip -oq data/soony_gh6/archive.zip -d data/soony_gh6/live
```

Antwortet das Portal mit HTTP 401, steht das Anmelde-Schema in `$PORTAL_BASE/api/v1/openapi.json`. Enthält das Archiv einen obersten Ordner `soony-data/`, ist dieser Ordner der Inhalt von `live/`.

## Stufe A: Durchstich mit dem Leitfall

Ziel: Der Artbook-Fall läuft vom Scan bis zur Antwort des Lieferanten. Danach zeigen die anderen Fälle ihre Zahlen ohne eigenen Code.

| Nr. | Schritt | Spezifikation | Fertig, wenn |
|---|---|---|---|
| A1 | Gerüst: `pyproject.toml` (Python ab 3.12), `python -m lineguard`, `Makefile`, Migration `0001_init` mit allen Tabellen, `claim_next()`, `clock.py`, CI nur für das Backend | `architecture.md` §3, §8, §10 · `docs/skalierung.md` N2 bis N5 · `docs/betrieb-und-wartung.md` W2, W3 | `python -m lineguard init` legt die Datenbank an. `tests/test_claim.py` und `tests/test_migrations.py` sind grün. Mit `LINEGUARD_NOW` gesetzt liefert `clock.now()` diesen Zeitpunkt, und kein anderer Code liest die Systemzeit. Die CI ist grün |
| A2 | Pakete: `pack.py`, `packs/soony_gh6/` mit `routes.yaml` und `source_rank.yaml`, `tests/fixtures/packs/demo_bikes/` mit den Dateien aus `docs/kern-und-kundenpaket.md` §5 | `docs/kern-und-kundenpaket.md` §3, §5 · `docs/import-und-routen.md` §2, §7 | Beide Pakete laden. Ein fehlendes Pflichtfeld stoppt den Start mit klarer Meldung. Jede Datei des Soony-Stands trifft eine Route oder `default` |
| A3 | Import Welle 1: `SourceConnector` (`portal_api`, `local_folder`), Watcher, `tables.py` mit `parser: table` und `parser: report` | `architecture.md` §2.1, §2.2, §6.1 · `docs/import-und-routen.md` §1 bis §4, §8 · `docs/skalierung.md` N1 | `tests/test_import_order.py` und `tests/test_tables.py` (Zahlen, Datum, Trennzeichen, Kopfsuche aus `docs/import-und-routen.md` §3) sind grün. Für Soony gibt es Fakten zu Bestand, Wareneingang, Bestellung, Stückliste, Sendung mit Menge, Status und Schichten |
| A4 | Rechenkern: `coverage/core.py` mit Bedarfszeilen, Release Gate, `not_stocked`, `breaks_at`, Deckung auf den Stufen `system` und `secured`. Jede Lücke schreibt ihren Fall in `cases` (`kind = gap`) | `architecture.md` §2.3 · `docs/dauerbetrieb.md` §3, §4, §6 · `docs/lueckenschluss.md` §2 | `tests/test_demand_lines.py` ist grün. `tests/test_stock_truth.py` ist grün für `need_remaining` und `stock_now` aller Teile und für die Lücke, die nur Tabellen braucht (Hüllen) |
| A5 | API und eine Seite: `/state`, `/cases/{id}`, Kopfzeile, Liste „Jetzt“, Beleg-Ansicht | `architecture.md` §7 · `docs/skalierung.md` N6 · `docs/lueckenschluss.md` §2 · `docs/dauerbetrieb.md` §6 | Die Seite zeigt Kopfzeile („System sagt“ neben „gesichert“) und Fälle aus dem echten `/state`. Ein Klick auf eine Zahl führt zu Fakt, Datei und Stelle. Die CI baut ab jetzt auch das Frontend |
| A6 | Reader für Dokumente, parallel: `llm.py` mit Cache und `llm_calls`, `documents.py` (PDF, Scan-PDF, `docx`, Freitext aus Tabellen), `vision.py`, Regeln für fremden Inhalt, Golden Set mit fünf Dokumenten | `architecture.md` §2.2, §6.5, §7.1 · `docs/import-und-routen.md` §4 bis §6 · `docs/skalierung.md` N1, N7 · `docs/betrieb-und-wartung.md` W4 | `tests/test_reader_parallel.py` und `tests/test_untrusted.py` (ein Dokument mit einer Anweisung ergibt einen Fakt `suspicious` und keine Aktion) sind grün. `python -m lineguard eval soony_gh6` endet mit Code 0. `tests/test_stock_truth.py` ist für alle Zahlen grün |
| A7 | Buchungsprüfung, Korrektur-Karte mit Belegen nebeneinander, Stufe `human`/`auto`, `ProposalFileWriter` als Mock der Middleware. Jeder Befund schreibt seinen Fall in `cases` (`kind = booking_finding`) | `docs/buchungspruefung.md` (§6a Stufen, §7 Mock) | `docs/buchungspruefung.md` §10, Punkte 1 bis 4, 7 und 8. Die Stufe `auto` braucht nur Code im Kern und Testwerte in `demo_bikes`. Das Soony-Paket bleibt auf `auto_enabled: false` |
| A8 | Freigaberegeln und Identität: `policy/engine.py`, `require_role`, „Angemeldet als“ | `architecture.md` §2.5 · `docs/kern-und-kundenpaket.md` §3 · `docs/betrieb-und-wartung.md` W1 | `tests/test_policy.py` und `tests/test_auth.py` sind grün |
| A9 | Lückenschluss: sieben Generatoren, Plan, Entscheidung, Zustände in `cases.state` | `docs/lueckenschluss.md` §4 bis §6 | `docs/lueckenschluss.md` §10, Punkte 1 bis 3 |
| A10 | Action Agent: Entwurf in der Sprache des Lieferanten, Senden nach Freigabe, Antwort zuordnen und lesen, Anhänge als Dateien | `architecture.md` §2.4, §6.3, §7.2 · `docs/import-und-routen.md` §5, §6, §8 | Mit `MAIL_MODE=DRY_RUN` steht die freigegebene Mail im Protokoll. Eine eingespielte Antwort (`.eml`) mit Anhang wird über `In-Reply-To` dem Fall zugeordnet, wird ein Fakt und löst die Neuberechnung aus. Eine Freigabe sendet genau eine Mail |

## Stufe B: Beweis, dass es ein Produkt ist

Ziel: die Punkte aus der Klarstellung von Lio (`architecture.md` §0c).

| Nr. | Schritt | Spezifikation | Fertig, wenn |
|---|---|---|---|
| B1 | Neuer Drop: ersetzte Datei, Fakten-Diff, `scripts/simulate_drop.py` | `architecture.md` §6.4 | Eine ersetzte Datei ändert Fakten, Lücke und Kopfzeile ohne Neustart. Die Seite zeigt den Unterschied |
| B2 | Wächter und Liste „Danach“ | `docs/dauerbetrieb.md` §5, §6 | `docs/dauerbetrieb.md` §8, Punkte 3 bis 5 |
| B3 | Zweiter Kunde: Tests mit `demo_bikes` | `docs/kern-und-kundenpaket.md` §6 · `docs/skalierung.md` §5 | `tests/test_second_pack.py`, `tests/test_workspace_isolation.py` und `tests/test_no_customer_values.py` sind grün |
| B4 | Absicherung, Eskalation, Zustand `unclosable` mit sofortiger Eskalation, Zusage für jede Kopie | `docs/lueckenschluss.md` §1, §5, §8 | `docs/lueckenschluss.md` §10, Punkte 4, 5 und 8 bis 11 |

## Stufe C: Wenn Zeit bleibt

In dieser Reihenfolge: Buchungsprüfungen 3 bis 5 · Wächter `promise_passed`, `shipment_silent` und `feed_stale` (`docs/dauerbetrieb.md` §5) · JSON-Protokoll (W5) · `pack check` · Generatoren `alt_source` und `add_capacity` · `MiddlewareWriter` (erst, wenn Soony die Middleware bereitstellt; bis dahin reicht der Mock aus A7) · `/state?role=` · Deployment (Vorlage: `Dockerfile` und `render.yaml` im Branch `origin/christian`. Die Daten liegen nicht im Image, und die Seite braucht ein Passwort).

## Stufe D: Abgabe (Beginn spätestens So 10:30)

| Nr. | Schritt | Spezifikation | Fertig, wenn |
|---|---|---|---|
| D1 | Demo-Backup: Snapshots, aufgezeichnete Antworten, Modus `REPLAY` | `architecture.md` §10 | `make demo-reset` stellt den Startzustand her, und die Demo läuft ohne Netz |
| D2 | README, kurz: ein Satz zum Produkt (allgemein, Soony als erster Kunde), Start in drei Befehlen, Aufbau in fünf Sätzen, Verweis auf `.env.example` und `architecture.md` | `docs/jury-und-pitch.md` §0 | Ein neuer Rechner startet Lineguard mit `demo_bikes` nur nach der README |
| D3 | Deck mit 4 Folien plus 2 bis 3 Folien Anhang, Video mit höchstens 3 Minuten | `docs/jury-und-pitch.md` §6 | Hochgeladen bis So 11:45. Abgabe vollständig nach `docs/jury-und-pitch.md` §1 |
