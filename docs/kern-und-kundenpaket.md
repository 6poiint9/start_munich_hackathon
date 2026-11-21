# Kern und Kundenpaket

Lies diese Datei, bevor du eine Datei unter `lineguard/` oder `packs/` anlegst, und immer dann, wenn du einen Kundenwert in den Code schreiben willst.

Entschieden am Sa 21.11., 19:55: Das Produkt heißt **Lineguard**. „Launch Control Room“ ist der Einsatz von Lineguard bei Soony.

## 1. Die Regel

Lineguard besteht aus zwei Teilen:

- **Kern** (`lineguard/`): Code, der für jede Firma mit Stückliste, Lieferanten und fester Frist gilt.
- **Kundenpaket** (`packs/<kunde>/`): alle Werte, die nur für einen Kunden gelten. Der Kern lädt genau ein Paket beim Start (`LINEGUARD_PACK=packs/soony_gh6`).

Ein **Kundenwert** ist eine Teilenummer, eine Lieferantennummer, ein Personenname, eine Menge, ein Datum, ein Dateipfad, ein Grenzwert oder eine Mail-Adresse eines Kunden.

Jeder Kundenwert steht an genau einem dieser drei Orte:

1. **Fakt:** Der Reader liest den Wert aus einer Kundendatei (Stückliste, Bestand, Organigramm, Angebot, Memo). Das ist der Normalfall.
2. **Paket:** Der Wert steht in keiner Datei, oder er sagt dem Kern, wo und wie er lesen soll.
3. **Test-Fixture:** Erwartete Zahlen für einen eingefrorenen Datenstand.

Falls es den Code schon unter `app/` gibt, bleibt der Ordnername. Die Regel betrifft Werte, nicht Ordnernamen.

`packs/soony_gh6/` steht in `.gitignore`, solange das Repo öffentlich ist: Das Paket enthält Kundendaten. Das erfundene Paket `demo_bikes` liegt im Repo.

## 2. Begriffe im Kern

Der Kern benutzt neutrale Begriffe. Die Oberfläche zeigt die Begriffe des Kunden aus `pack.yaml` (`labels`).

| Kern | Bedeutung | Bei Soony |
|---|---|---|
| `deadline` | Nächster Bedarfstermin: Zeitpunkt, an dem die Ware fertig sein muss | Launch So 22.11.2026, 20:00 |
| `demand_line` | Stück eines Produkts bis zu einem Termin (`due_at`) | 72.000 Collector's bis zum Launch |
| `case` | Ein Vorgang mit Besitzer, Termin und Zustand | Artbook-Lücke, Korrektur 5000413065 |
| `product` | Fertiges Produkt mit Stückliste | Edition: `FG-GH6-STD`, `FG-GH6-CE` |
| `component` | Teil in der Stückliste | `CMP-GAM-001` … |
| `demand` | Stückzahl je Produkt zur Frist | 640.000 Standard, 72.000 Collector's |
| `demand_class` | Gruppe der Nachfrage mit eigener Priorität | `preordered`, `open_sale` |
| `site` | Ort, an dem montiert oder gepackt wird | `DC-HAM` |
| `workspace` | Ein Kunde mit einer Frist und einem Paket | `soony_gh6` |
| `units` | Stück eines Produkts | Kopien |
| `capacity` | Stück pro Stunde je Produkt im Schichtplan | Packlinien L1–L3, CE-Zelle |
| `erp_owner` | Rolle, die als einzige ERP-Daten korrigieren darf | IT & Systems Lead (Nils Berger) |

## 3. Aufbau des Pakets

```
packs/soony_gh6/
├── pack.yaml              # Frist, Nachfrage, Quellen, Grenzwerte, Labels
├── routes.yaml            # Pfadmuster → Parser und erwartete Fakt-Typen
├── source_rank.yaml       # Dokumentklasse → Rang 1–5
├── approval_policy.yaml   # Freigaberegeln als Daten (bei Soony: PP-07 + CPO-Memo)
├── aliases.csv            # Teilenummer des Lieferanten → component_id
└── prompts/               # optional: eigene Prompt-Texte, sonst Kern-Prompts
```

`pack.yaml` (Schema `PackConfig` in `lineguard/pack.py`, mit Pydantic geprüft; ein fehlendes Pflichtfeld stoppt den Start mit klarer Meldung):

```yaml
workspace: soony_gh6               # Kunden-Schlüssel in jeder Tabelle (docs/skalierung.md N3)
customer: Soony
labels: {deadline: "Launch", product: "Edition", line: "Packlinie"}
timezone: Europe/Berlin
deadline: 2026-11-22T20:00:00+01:00
site: DC-HAM

sources:
  - connector: portal_api          # oder local_folder
    base_url_env: PORTAL_BASE
    token_env: PORTAL_TOKEN
    poll_seconds: 60

demand: []                          # Bei Soony leer: Die Nachfrage steht in den Daten (geprüft am Stand von Sa 22:45).
                                    # products.csv, day_one_qty: 640.000 und 72.000. launch_plan_GH6.xlsx, Spalte
                                    # "of which pre-orders": 415.000 Standard, 72.000 Collector's. Der Rest ist open_sale.
                                    # Ein Kunde ohne solche Datei trägt hier Zeilen ein:
                                    #   - {product: <id>, class: preordered, units: 1000, due_at: <Zeitpunkt>}
                                    # Nennen Daten und Paket beide eine Menge, gewinnt der Fakt aus den Daten.
priority_order: [preordered, compliance, open_sale]
# Stand der gepackten Stück, Bestand und Schichtplan kommen über Routen (kind build_status, stock, shifts).
# Je Art gewinnt der neueste as_of (docs/import-und-routen.md §3, Regel 12).

booking_check:                      # siehe docs/buchungspruefung.md
  over_tolerance: 0.05
  weight_ratio_range: [0.5, 2.0]
  min_agreeing_sources: 2
coverage:                           # siehe docs/lueckenschluss.md
  confirm_threshold: 0.8
  thin_margin: 0.05
  stale_count_days: 14
  default_handling_hours: 2         # Annahme. Der Branch rechnet mit 4. Klären mit Felix Brunner (architecture.md §11, Frage 25)
  horizon_days: 30
watch:                              # siehe docs/dauerbetrieb.md §5
  default_notice_days: 14
  confirm_days: 5
  silent_after_hours: {sea: 24, air: 12, road: 8}   # Annahme, klären mit Felix Brunner
  feed_stale_hours: 12                              # Annahme, klären mit Nils Berger

mail: {subject_tag: "[GH6]", sender_env: GMAIL_ADDRESS, follow_up_hours: 2}
erp_writer: {mode: proposal_file}   # oder middleware
auto_approve:                       # läuft ohne Klick (docs/skalierung.md N6)
  action_kinds: [status_request, follow_up, count_request]
  max_cost_eur: 0
roles: {erp_owner: "IT & Systems Lead", site_lead: "Site Lead DC-HAM"}
```

`approval_policy.yaml` enthält nur Regeln und Rollen. Die Personen zu den Rollen kommen als Fakten aus dem neuesten Organigramm. Das Schema von `routes.yaml` und `source_rank.yaml` steht in `docs/import-und-routen.md` §2. Die Freigaberegeln von Soony:

```yaml
rules:
  - {id: po_value, applies_to: purchase_order, tiers: [
      {lt_eur: 50000, role: buyer}, {lt_eur: 500000, role: category_lead},
      {lt_eur: 2000000, role: head_of_procurement}, {lt_eur: 5000000, role: cpo},
      {role: [cpo, cfo]}]}
  - {id: air_freight, applies_to: air_freight, limit_eur_per_month_per_category: 200000,
     below: category_lead, above: cpo}
  - {id: dock_slot, applies_to: inbound_delivery, add_role: site_lead}
  - {id: supplier_release, applies_to: supplier_release, role: [category_lead, supplier_quality_lead]}
  - {id: unreleased_part, applies_to: unreleased_part, add_role: quality_compliance}
  - {id: erp_write, applies_to: erp_correction, role: erp_owner}
  - {id: vacant_role, fallback_role: head_of_procurement}
escalation: [buyer, category_lead, head_of_procurement, cpo]
source: "approval_policy_PP-07.pdf, memo_launch_priorities.docx"
```

## 4. Was der Kern bereitstellt

| Modul | Aufgabe | Kundenwerte kommen aus |
|---|---|---|
| `lineguard/pack.py` | Paket laden und prüfen | `pack.yaml` |
| `lineguard/connectors/` | Ports `SourceConnector` (`list`, `download`), `Mailer` (`send`, `poll`), `ErpWriter` (`apply`, `status`) | `pack.yaml`, `.env` |
| `lineguard/agents/` | Watcher, Reader, Stock Truth, Action, Decision | Fakten |
| `lineguard/policy/engine.py` | `route(decision_type, value_eur, category, flags) -> [role]` und `resolve_person(role, category, at)` mit Vertretung und vakanter Rolle | `approval_policy.yaml`, Organigramm-Fakten |
| `lineguard/coverage/` | Rechenkern, Buchungsprüfung, Lückenschluss | Fakten, Grenzwerte aus dem Paket |

`lineguard/policy/engine.py` ersetzt die frühere Datei `app/policy/pp07.py`. Die Regeln bleiben Code-ausgewertet. Kein Prompt entscheidet über eine Freigabe.

## 5. Zweites Paket als Beweis

`tests/fixtures/packs/demo_bikes/` ist ein kleines erfundenes Paket: ein Produkt, drei Teile, zwei Bedarfstermine. Alle Spalten haben deutsche Namen, die `routes.yaml` über `columns` zuordnet. Die Tests mit diesem Paket brauchen deshalb kein LLM und laufen in der CI.

| Datei unter `files/` | `kind` | Inhalt, den ein Test braucht |
|---|---|---|
| `produkte.csv`, `teile.csv`, `stueckliste.csv` | `products`, `components`, `bom` | Ein Teil hat eine freigegebene Revision |
| `bedarf.csv` | `demand` | Zwei Zeilen mit verschiedenem `due_at` (`tests/test_demand_lines.py`) |
| `bestand.csv` | `stock` | Ein Teil mit dünner Deckung und alter Zählung |
| `bestellungen.csv` | `purchase_orders` | Eine offene Position mit nicht freigegebener Revision (`tests/test_watch.py`) |
| `wareneingang.csv` | `goods_receipts` | Eine Buchung mit Faktor 10, eine Teillieferung |
| `lieferscheine.csv` | `delivery_notes` | Menge, Gewicht und Packstücke je Lieferschein. Sie stützen die richtige Menge der Faktor-10-Buchung |
| `angebote.csv` | `offers` | Ein Angebot, das die Lücke schließt (`tests/test_closing.py`) |
| `vertraege.csv` | `validity` | Ein Vertrag mit `valid_until` 10 Tage nach der Test-Uhrzeit |
| `personen.csv` | `person_roles` | Vier Personen mit Rolle, darunter `erp_owner` (`tests/test_auth.py`) |
| `hinweis_lieferant.txt` | `document` | Das eine Dokument im Golden Set von `demo_bikes` |

Alle Termine im Paket beziehen sich auf eine feste Test-Uhrzeit, die die Tests über `LINEGUARD_NOW` setzen.

Zweck: Der Test zeigt, dass der Kern ohne Änderung für einen zweiten Kunden läuft. Im Pitch ist das der Satz „Der nächste Kunde ist ein Ordner, kein Projekt“.

## 6. Fertig, wenn

1. `pytest tests/test_no_customer_values.py` ist grün. Der Test liest alle Bezeichner aus `packs/*/` und aus den Stammdaten (Teile, Lieferanten, Personen, Bestellnummern) und findet keinen davon in `lineguard/`.
2. Der Kern startet mit `LINEGUARD_PACK=packs/soony_gh6` und mit `LINEGUARD_PACK=tests/fixtures/packs/demo_bikes`, ohne dass eine Datei im Kern anders ist.
3. `pytest tests/test_second_pack.py` ist grün: Der Kern findet im Paket `demo_bikes` den Faktor-10-Fehler und die Lücke und erstellt eine Entscheidung.
4. Eine Änderung an einem Grenzwert in `pack.yaml` ändert das Ergebnis nach einem Neustart, ohne Code-Änderung.

Bei Zeitnot entfallen Punkt 2 (zweites Paket) und Punkt 3. Punkt 1 und Punkt 4 bleiben.
