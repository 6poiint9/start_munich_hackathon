# Betrieb und Wartung

Lies diese Datei, wenn du Freigabe-Endpunkte, `lineguard/migrations/`, die CI, Prompts, das LLM-Modell oder einen neuen Erweiterungspunkt (Prüfung, Generator, Wächter, Anschluss) anfasst, oder wenn du ein Paket für einen neuen Kunden anlegst.

Grund: Lio verlangt eine wartbare Lösung für lange Nutzung (`architecture.md` §0c). Diese Datei nennt, was dafür bis zur Abgabe entsteht (W1 bis W5) und was danach kommt (§8).

## W1. Identität: Wer gibt frei? (40 min)

Das Backend prüft die gewählte Person und die erforderlichen Rollen. Eine passende Rolle genügt. Gemeinsame Freigaben, die Soony teilweise verlangt, sind nicht umgesetzt.

1. Jeder schreibende Endpunkt (`/decisions/{id}/approve`, `/decisions/{id}/reject`, `/emails/{id}/approve`, `/corrections/{id}/approve`, `/corrections/{id}/reject`, Korrektur eines Fakts) verlangt den Header `X-Lineguard-User` mit einer `person_id`.
2. `require_role(person_id, needs_roles, at)` in `lineguard/policy/engine.py` prüft die Rolle für Freigeben, Ablehnen, Verwerfen und Zählen. Bei einer fehlenden Rolle antwortet der Endpunkt mit HTTP 403. Bei einer unbesetzten Rolle kann die konfigurierte Ersatzrolle gelten.
3. Ausnahme: Eine ERP-Korrektur mit `tier = auto` hat keine Person, sondern `approved_by = policy:erp_write_auto` (`docs/buchungspruefung.md` §6a). Nur eine Person mit der Rolle `erp_owner` darf die Regel `booking_check.tiers` ändern. Die Änderung ist ein Commit im Paket und steht im Protokoll.
4. Personen und Rollen sind Fakten vom Typ `person_role` aus dem neuesten Organigramm. Rollen ohne Dokument (zum Beispiel `erp_owner`) stehen in `pack.roles`.
5. `approved_by`, `decided_by` und `extracted_by = human` speichern die `person_id`.
6. Die Oberfläche hat oben rechts „Angemeldet als“. Die Auswahl listet die Personen mit Rolle. Die Oberfläche prüft die direkten Rollen der gewählten Person.

Der Umschalter ist die Lösung für die Abgabe und kein Login. Für einen öffentlichen Betrieb braucht die Anwendung einen Zugriffsschutz.

## W2. Schema-Migrationen (20 min)

1. Jede Änderung am Schema ist eine nummerierte Datei in `lineguard/migrations/` (`0001_init.py`, `0002_…`) mit einer Funktion `up(conn)`.
2. Die Tabelle `schema_version` hält die höchste angewandte Nummer. `make init` und der Start des Kerns wenden fehlende Dateien in Reihenfolge an.
3. Eine angewandte Migration wird nie geändert. Eine Korrektur ist eine neue Datei.
4. `make demo-reset` löscht die Datenbank des Workspace und wendet alle Migrationen neu an, danach lädt es den Snapshot.

Beim Wechsel auf Postgres (`docs/skalierung.md` §3, Stufe 2) ersetzt Alembic den eigenen Läufer. Die Regeln 1 bis 3 bleiben.

## W3. CI bei jedem Push (20 min)

`.github/workflows/ci.yml` läuft bei Push und Pull Request:

1. Backend: `ruff check lineguard tests` und `pytest -q`.
2. Frontend: `npm ci`, `npm run lint`, `npm run build` in `web/`. Dieser Job läuft nur, wenn `web/package.json` existiert (`hashFiles`), also ab Schritt A5.

`python -m lineguard eval` läuft nicht in der CI, weil der Lauf den LLM-Key braucht.

Die Kundendaten liegen nicht im Repo. Tests, die den Soony-Snapshot brauchen, tragen `@pytest.mark.customer_data` und werden übersprungen, wenn `tests/fixtures/soony/` fehlt. Tests mit dem erfundenen Paket `demo_bikes` laufen immer. Die CI prüft damit den Kern, und der Laptop prüft Soony.

## W4. Lese-Qualität messen: Golden Set (30 min)

Der Reader ist der einzige Teil, dessen Ergebnis sich mit Modell und Prompt ändert. Ein **Golden Set** ist eine Liste von Dokumenten mit den Fakten, die der Reader daraus lesen muss.

1. Ablage: `tests/golden/<pack>/<name>.json` mit `file` (Pfad im Workspace), `sha256` und `expected` (Liste aus `fact_type`, `component_id`, `qty` oder `value_text`, `eta`).
2. `make eval PACK=<pack>` liest jedes Dokument ohne Cache und vergleicht. Ausgabe je Fakt-Typ: erwartet, gefunden, falsch, fehlend.
3. Der Lauf scheitert, wenn ein erwarteter Fakt fehlt oder eine Menge oder ein Datum abweicht.
4. Führe `make eval` aus, bevor du eine Datei in `lineguard/prompts/` oder einen Wert `LLM_MODEL_*` änderst, und danach. Notiere beide Ergebnisse in der Commit-Nachricht.
5. Für Soony reichen zur Abgabe fünf Dokumente, je eines pro Art: handschriftlich korrigierter Lieferschein, Prüfbericht, Versandavis (KO/EN), Auftragsbestätigung mit Revision, Angebot. Das Soony-Set bleibt außerhalb des Repos. Das Set für `demo_bikes` liegt im Repo.

Der Cache-Schlüssel enthält den Hash des Prompts und den Modellnamen (`architecture.md` §6.5). Ein geänderter Prompt liest deshalb jede Datei neu.

## W5. Protokoll (15 min)

1. Jeder Handler schreibt eine JSON-Zeile je Event: `ts`, `workspace_id`, `event_id`, `type`, `handler`, `ms`, `outcome`, `error`.
2. `events` wird nie gelöscht. Die Tabelle ist das Audit-Protokoll: wer, wann, auf welchen Beleg hin.
3. `/healthz` liefert die Messwerte aus `docs/skalierung.md` N7 und die Zahl der Events mit `status = 'failed'`.

## 6. Erweiterungspunkte

Jede Erweiterung ist eine Datei plus ein Test mit `demo_bikes`. Kein Erweiterungspunkt verlangt eine Änderung am Orchestrator oder am Datenmodell.

| Du willst | Lege an | Registriere in | Test |
|---|---|---|---|
| eine neue Buchungsprüfung | Funktion in `lineguard/coverage/booking_check.py` | Liste `CHECKS` | `tests/test_booking_check.py` |
| einen neuen Weg, eine Lücke zu schließen | `lineguard/coverage/options/<kind>.py` | Liste `GENERATORS` | `tests/test_closing.py` |
| einen neuen Wächter | Funktion in `lineguard/coverage/watch.py` | Liste `WATCHERS` | `tests/test_watch.py` |
| eine neue Datenquelle | Klasse mit `list` und `download` in `lineguard/connectors/source.py` | `pack.sources[].connector` | Test mit lokalem Ordner |
| ein neues Dateiformat | Parser unter `lineguard/agents/reader/` | `routes.yaml` des Pakets | Eintrag im Golden Set |
| eine neue Tabellenart | Eintrag in der Liste der `kind` in `lineguard/agents/reader/tables.py` (`docs/import-und-routen.md` §1) | `routes.yaml` des Pakets | `tests/test_tables.py` |
| einen neuen Fakt-Typ | Wert im Enum `FactType` in `lineguard/models.py` | Prompt `reader_extract.md` | Eintrag im Golden Set |
| einen anderen ERP-Schreibweg | Klasse mit `apply` und `status` in `lineguard/connectors/erp_writer.py` | `pack.erp_writer.mode` | `tests/test_booking_check.py` |
| eine neue Freigaberegel | Zeile in `approval_policy.yaml` des Pakets | — | `tests/test_policy.py` |

## 7. Neuer Kunde: Paket anlegen

Ziel: Ein zweiter Kunde mit ähnlichen Daten (laut Nils gibt es solche Kunden) läuft ohne Änderung am Kern. Der Kunde liefert:

- Exporte aus dem ERP: Bestellungen, Wareneingänge, Bestand, Stückliste, Teile, Lieferanten. Lesen reicht.
- Die Belege: Lieferscheine (auch Scans), Auftragsbestätigungen, Versandavise, Prüfberichte.
- Frist und Nachfrage, falls sie in keiner Datei stehen.
- Freigaberegeln und Organigramm.
- Eine Person für die Rolle `erp_owner` und den Schreibweg ins ERP. Ohne Schreibweg gilt `proposal_file`.

Schritte:

1. Kopiere `tests/fixtures/packs/demo_bikes/` nach `packs/<kunde>/` und trage `workspace`, `deadline`, `sources` und `demand` ein.
2. Führe `python -m lineguard.pack check packs/<kunde>` aus. Der Befehl lädt die Dateiliste der Quelle und meldet: Dateien ohne Route, Tabellen mit unbekannten Spalten, fehlende Stammdaten (Stückliste, Teile, Lieferanten), Rollen ohne Person.
3. Ergänze `routes.yaml` und `aliases.csv`, bis der Befehl keine Datei ohne Route mehr meldet.
4. Übertrage die Freigaberegeln des Kunden nach `approval_policy.yaml`.
5. Lege fünf Dokumente mit erwarteten Fakten in `tests/golden/<kunde>/` ab und führe `make eval PACK=<kunde>` aus.
6. Starte den Kern mit `LINEGUARD_PACK=packs/<kunde>` und `MAIL_MODE=DRY_RUN`. Der Rückblick der Buchungsprüfung ist das erste Ergebnis für den Kunden.
7. Starte mit `booking_check.tiers.auto_enabled: false`. Jede Korrektur geht zum `erp_owner`. Erst wenn er die Vorschläge eine Zeit lang geprüft hat, legt er `auto_causes` und `auto_max_value_eur` fest und schaltet `auto` ein.
8. `erp_writer.mode` bleibt `proposal_file`, bis der Kunde einen Schreibweg bereitstellt. Dann folgt ein eigener `ErpWriter` (§6, Zeile „anderer ERP-Schreibweg“).

Nicht nötig für einen neuen Kunden: Änderungen an Code, Prompts oder Datenmodell im Kern. Braucht ein Kunde doch eine, ist das ein Erweiterungspunkt aus §6 mit Test für alle Pakete.

Bis zur Abgabe entsteht von `pack check` nur die Meldung „Dateien ohne Route“. Die anderen Meldungen folgen danach.

## 8. Nach der Abgabe

| Thema | Heute | Für den Betrieb |
|---|---|---|
| Anmeldung | Umschalter „Angemeldet als“ | OIDC beim Kunden, `require_role` bleibt |
| ERP-Schreibweg | `ProposalFileWriter` als Mock: JSON und CSV, Mail an den `erp_owner` | `MiddlewareWriter`, sobald Soony die Middleware bereitstellt. Gleicher Body wie die JSON-Datei |
| Geheimnisse | `.env` auf dem Laptop, `.env.example` im Repo | Geheimnis-Speicher je Workspace |
| Kundendaten beim LLM-Anbieter | Dokumente gehen an die API aus `LLM_PROVIDER` | Anbieter und Region je Workspace wählbar über `lineguard/llm.py`, Vertrag zur Auftragsverarbeitung mit dem Kunden |
| Sicherung | Kopie der SQLite-Datei (`make demo-reset` nutzt sie) | Tägliche Sicherung der Datenbank und des `BlobStore` je Workspace |
| Abhängigkeiten | `pyproject.toml` mit festen Versionen, `package-lock.json` | Automatische Updates mit CI als Schranke |
| Alarm | Leiste „Probleme“ in der Oberfläche | Meldung an den Betreiber bei `failed`-Events und bei `queue_lag_seconds` über dem Ziel |

## 9. Fertig, wenn

1. `tests/test_auth.py`: Eine Freigabe ohne Header liefert HTTP 401. Eine unbekannte Person und eine Person ohne passende Rolle erhalten HTTP 403. Eine Person mit `erp_owner` kann eine Korrektur fürs ERP freigeben.
2. `tests/test_migrations.py`: Eine leere Datenbank hat nach `make init` die höchste Nummer in `schema_version`. Ein zweiter Lauf ändert nichts.
3. Die CI ist auf dem Hauptzweig grün, und mindestens die Tests mit `demo_bikes` laufen dort.
4. `make eval PACK=demo_bikes` endet mit Code 0. `make eval PACK=soony_gh6` endet auf dem Laptop mit Code 0 für die fünf Dokumente.
5. Jede Zeile der Tabelle in §6 hat ihren Test.

Bei Zeitnot entfallen in dieser Reihenfolge: W5 bis auf `/healthz`, `pack check`, das Golden Set für Soony über den Lieferschein hinaus, das Frontend in der CI. W1 und W2 bleiben.
