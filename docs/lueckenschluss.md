# Lückenschluss: Ziel 100 % Deckung

Lies diese Datei, wenn du `lineguard/coverage/closing.py`, die Optionen im Decision Agent oder die Kopfzeile der Oberfläche baust.

## 1. Ziel

Entschieden am Sa 21.11., 19:55: Das Ziel ist **100 % Deckung der gesamten Nachfrage zur Frist**. Bei Soony sind das alle 712.000 Kopien (640.000 Standard, 72.000 Collector's), auch die Standard-Kopien für Spontankäufe.

Software stellt keine Ware her. Lineguard sichert deshalb vier Dinge zu, und jedes ist messbar:

1. **Wahrheit:** Die Deckung rechnet mit belegten Mengen, nicht mit gebuchten (`docs/buchungspruefung.md`, Release Gate, Zählung bei dünner Deckung).
2. **Plan:** Jede offene Lücke hat zu jeder Zeit einen Plan mit Besitzer, Frist und Preis, oder sie ist offen als `unclosable` gemeldet.
3. **Zeit:** Jede Option zählt nur, wenn die Ware noch rechtzeitig gepackt werden kann.
4. **Nachhaken:** Eine Option zählt erst als sicher, wenn ein Beleg sie bestätigt. Bis dahin läuft eine Absicherung mit.

**Zusage für jede Kopie:** Zu jedem Zeitpunkt ist jede Kopie der Nachfrage in genau einem Zustand: `packed`, `secured`, `planned`, `open` oder `unclosable`. Eine sechste Möglichkeit gibt es nicht. Keine Kopie fehlt still. Der Test in §10, Punkt 8 prüft das.

**Rangfolge bei Mangel:** Bei Soony gilt das Memo des CPO (`memo_launch_priorities.docx`, 21.11.): „Collector's Edition first. All 72,000 copies are pre-ordered and numbered. Where a part is short, it goes to the Collector's cell before the Standard lines. This includes game cards.“ Grund laut Memo: Eine vorbestellte Kopie, die am ersten Tag fehlt, wird erstattet und kostet den Kunden. Eine Standard-Kopie am Dienstag wird noch verkauft. Im Paket steht das als `priority_order: [preordered, compliance, open_sale]`. Die Rangfolge bestimmt, was zuerst gedeckt wird. Das Ziel bleibt 100 % für alle Stufen.

**Keine Deckung mit gesperrter Ware:** Laut Memo verlässt keine Kopie Hamburg mit einem nicht freigegebenen Teil. Kein Generator zählt deshalb Ware ohne Freigabe, auch nicht, um eine Lücke zu schließen. `rework_sort` zählt nur die erwartete gute Menge nach der Sortierung.

Die Schleife ist allgemein. Sie kennt Fakt-Typen und Stammdaten, aber kein Teil, keinen Lieferanten und keinen Fall von Soony.

„Frist“ und `deadline` meinen in dieser Datei den Bedarfstermin der Lücke (`gaps.due_at`). Bei mehreren Terminen gilt die Zuteilung aus `docs/dauerbetrieb.md` §4. Fälle aus der Liste „Danach“ kommen in die Schleife, sobald ihr `act_by` im Horizont liegt.

## 2. Deckung als Kennzahl

Die Kopfzeile der Oberfläche zeigt je Produkt eine Zahl und vier Zustände:

```
demand(product)   = Summe der Bedarfszeilen des Produkts (docs/dauerbetrieb.md §3)
packed            = aus der neuesten Status-Datei
still_to_pack     = demand − packed
buildable(level)  = min über alle Teile der Stückliste von
                    floor((usable_stock + inbound(level)) / Menge je Produkt),
                    nach Verteilung geteilter Teile in priority_order,
                    begrenzt durch capacity × verbleibende Schichtstunden
coverage(level)   = (packed + min(still_to_pack, buildable(level))) / demand
```

| Zustand | `inbound(level)` enthält | Anzeige |
|---|---|---|
| `system` | Bestand wie gebucht, ohne Buchungsprüfung, Release Gate und Verbrauch seit dem Snapshot. Jeder Zulauf aus der Planung des Kunden mit Termin vor der Frist | „System sagt“ |
| `secured` | Nutzbarer Bestand plus Zulauf mit Beleg vom Rang 1 oder 2 und Ankunft vor `latest_useful_arrival` | „gesichert“ |
| `planned` | zusätzlich freigegebene Optionen in Ausführung | „in Arbeit“ |
| `open` | Lücke mit Plan, der auf Freigabe wartet | „wartet auf Entscheidung“ |
| `unclosable` | Lücke ohne ausreichende Optionen | „nicht schließbar: N Kopien“ |

`system` ist kein Zustand einer Lücke, sondern die Vergleichszahl: was die Planung des Kunden glaubt. Die Kopfzeile stellt sie neben `secured`, zum Beispiel „System sagt 100 % · gesichert 91 %“. Der Abstand ist der Wert von Lineguard in einer Zeile und beantwortet den Satz des Kunden „The system says we are fine. My gut says we are not.“ Dieselbe Funktion rechnet beide Zahlen, nur der Filter über die Fakten ist anders.

Das Ziel ist erreicht, wenn `coverage(secured) = 100 %` für jedes Produkt gilt.

## 3. Zeitgrenzen

```
breaks_at             = Zeitpunkt, an dem das Teil bei aktueller Rate leer ist   (architecture.md §2.3)
latest_useful_arrival = deadline − (fehlende Stück / capacity des Produkts) − handling_hours
```

`latest_useful_arrival` ist die harte Grenze: Später angekommene Ware schafft es nicht mehr durch die Linie. `breaks_at` ist das weiche Ziel: Eine Ankunft danach kostet Stillstand, rettet aber noch Kopien. `handling_hours` kommt aus dem Paket (`coverage.default_handling_hours`) oder als Fakt aus einer Kundendatei.

## 4. Optionen

Eine **Option** ist ein Weg, Stück zu gewinnen. Jeder Generator ist eine Funktion mit derselben Signatur und liest nur Fakten:

```python
class OptionGenerator(Protocol):
    kind: str
    def generate(self, gap: Gap, facts: FactView, pack: PackConfig) -> list[Option]: ...
```

| `kind` | Liest | Erzeugt | Kostet Geld |
|---|---|---|---|
| `release_held` | Sendung mit Status „angekommen“ oder „abholbereit“ ohne Wareneingang | Abholung und Dock-Slot anfragen | nein oder gering |
| `accept_offer` | Fakt `offer` mit `valid_until` in der Zukunft | Bestellung zum Angebot | ja |
| `expedite_inbound` | Fakt `inbound_qty` mit Ankunft nach `latest_useful_arrival` oder ohne Bestätigung | Anfrage an Lieferant oder Spediteur: frühere Ankunft, Teilmenge per Luft | Anfrage nein, Zusage ja |
| `rework_sort` | Gesperrte Charge mit `inspection_result` | Sortierung: erwartete gute Menge = Charge × (1 − Fehlerquote) | gering |
| `reallocate` | Teil, das mehrere Produkte brauchen | Verteilung nach `priority_order` | nein |
| `count_request` | Befund `needs_count` oder Regel `thin_and_stale` (§7) | Zählung im Lager | nein |
| `alt_source` | Anderer Lieferant mit demselben Teil in Bestellungen oder Stammdaten | Preisanfrage mit Menge und spätester Ankunft | Anfrage nein |
| `add_capacity` | `actual_rate < required_rate` | Zusatzschicht oder zweite Linie anfragen | ja |
| `deliver_after_deadline` | Rest ohne Option | Plan für die Lieferung nach der Frist mit frühestem Datum | nein |

Jede Option hat: `qty_gain`, `arrives_at`, `cost_eur`, `confidence` (0–1), `feasible`, `valid_until`, `needs_roles` (aus `policy.route`), `evidence_fact_ids`, `status`.

`confidence` folgt dem Rang des Belegs: Rang 1 oder 2 mit Datum = 0,9. Aussage des Lieferanten ohne Dokument = 0,6. Noch keine Antwort = 0,3.

Für Sonntag 12:00 reichen `release_held`, `accept_offer`, `expedite_inbound`, `rework_sort`, `reallocate`, `count_request` und `deliver_after_deadline`. `alt_source` und `add_capacity` kommen danach.

## 5. Die Schleife

`close_gaps()` läuft bei `gap.changed`, `email.received`, `decision.approved`, `decision.rejected` und bei jedem `tick`:

```
für jede aktuelle Lücke mit gap_qty < 0 und impact = deadline_blocker, in Rangfolge:
    need       = −gap_qty
    options    = alle Generatoren aufrufen, alte Optionen mit neuen Fakten abgleichen
    feasible   = Optionen mit arrives_at ≤ latest_useful_arrival und valid_until > jetzt
    sortiert   = feasible nach (confidence ≥ confirm_threshold zuerst, cost_eur / qty_gain, arrives_at)

    plan, firm, soft = [], 0, 0
    für o in sortiert:
        wenn firm ≥ need: stop
        plan.append(o)
        wenn o.confidence ≥ confirm_threshold: firm += o.qty_gain   sonst: soft += o.qty_gain

    wenn firm + soft < need:  Zustand unclosable, residual = need − firm − soft
    sonst:                    Zustand open, Plan vorschlagen
```

Folgen aus der Schleife:

- **Absicherung:** Solange `firm < need`, nimmt die Schleife weitere Optionen dazu. Ein unbestätigter Weg bekommt also einen zweiten Weg daneben.
- **Fragen sofort:** Optionen ohne Kosten (Anfrage, Zählung, Abholtermin) gehen als Routine-Aktion an den Action Agent, sobald sie entstehen. Alle Fragen laufen parallel.
- **Geld mit Freigabe:** Optionen mit `cost_eur > 0` oder mit einer Zusage werden zu einer Entscheidung. `act_by = breaks_at − Vorlauf der Option` (`architecture.md` §2.3). Liegt dieser Zeitpunkt in der Vergangenheit, gilt `act_by = latest_useful_arrival − Vorlauf der Option`. Der Decision Agent routet die Entscheidung mit `policy.route`.
- **Preis des Wartens:** Jede Entscheidung zeigt neben dem Preis der Option, was eine Stunde Stillstand kostet: `rate_per_hour` Stück des Produkts, das auf das Teil wartet.
- **Neuer Fakt, neuer Plan:** Eine Antwort eines Lieferanten ändert `confidence`, `qty_gain` oder `arrives_at`. Die Schleife rechnet neu. Wird eine bestätigte Option größer als nötig, verfallen die Absicherungen, die noch kein Geld gekostet haben.
- **Eskalation:** Ist eine Entscheidung zum Zeitpunkt `act_by − 30 min` noch offen, geht sie an die nächste Rolle aus `approval_policy.escalation`. Event `decision.escalated`.

## 6. Zustände einer Lücke

```
open → plan_proposed → approved → in_execution → confirmed → closed
                                              ↘ failed → open
unclosable (jederzeit möglich, verlässt den Zustand bei einer neuen Option)
```

| Zustand | Bedingung für den Wechsel |
|---|---|
| `plan_proposed` | Plan deckt `need`, Entscheidung erstellt |
| `approved` | Mensch hat freigegeben |
| `in_execution` | Aktion gesendet (Mail, Bestellung, Abholauftrag) |
| `confirmed` | Beleg vom Rang 1 oder 2 nennt Menge und Ankunft vor `latest_useful_arrival` |
| `closed` | Wareneingang gebucht und geprüft, `usable_stock` deckt `need` |
| `failed` | Absage, Frist verpasst oder Beleg widerspricht |

## 7. Regel `thin_and_stale`

Ein falscher Bestand fällt sonst erst an der Linie auf. Deshalb fordert Stock Truth eine Zählung an, bevor das Teil gebraucht wird:

```
margin = (usable_stock + inbound(secured) − need_remaining) / need_remaining
wenn margin < thin_margin
   und (last_count älter als stale_count_days  oder  Teil hat einen offenen Buchungsbefund):
       Aktion count_request an site_lead, Routine, eine je Teil und Tag
```

`last_count` steht im Bestandsexport. Die gezählte Menge kommt als Fakt `counted_qty` (Rang 1) zurück.

## 8. Wenn eine Lücke nicht schließbar ist

Lineguard meldet den Rest offen und versteckt ihn nicht:

1. Kopfzeile: „Standard 98,9 % · 6.800 Kopien nicht schließbar“ mit dem Grund und dem Beleg.
2. Verteilung nach `priority_order`: Vorbestellte Nachfrage wird zuerst gedeckt, und die Menge dafür wird reserviert. Erst danach bekommt die nächste Stufe Teile. Ein Rest bleibt also zuerst bei `open_sale`.
3. **Eskalation sofort:** Beim Event `gap.unclosable` geht eine Entscheidung an die oberste Rolle der Eskalationskette (bei Soony `cpo`). Sie wartet nicht auf `act_by`. Inhalt: Stückzahl, betroffene `demand_class`, Grund, Beleg und die Option `deliver_after_deadline` (frühestes Datum, Stückzahl, Kosten).
4. Trifft der Rest die erste Stufe aus `priority_order` (bei Soony `preordered`, also Collector's), steht die Entscheidung oben in der Liste „Jetzt“, rot, vor allen anderen Fällen.
5. Die Schleife sucht bei jedem neuen Fakt weiter. Der Zustand `unclosable` ist nie endgültig vor der Frist.

## 9. Daten

Neue Tabelle `options` (Ergänzung zu `architecture.md` §3). `decisions.options` enthält dann nur noch die Liste der `option_id`.

| Spalte | Inhalt |
|---|---|
| `id`, `gap_id`, `kind` | |
| `qty_gain` (Stück des Teils), `units_gained` (JSON: `product_id` → Stück), `arrives_at`, `cost_eur`, `confidence`, `valid_until` | |
| `feasible` | bool, mit `infeasible_reason` |
| `role_in_plan` | `primary`, `backup`, `none` |
| `status` | `candidate/proposed/approved/in_execution/confirmed/delivered/failed/expired` |
| `needs_roles`, `evidence_fact_ids` | JSON |
| `action_id`, `decision_id` | |
| `dedupe_key` | UNIQUE: `<gap_component>:<kind>:<Quelle der Option>` |

Der Zustand aus §6 steht in `cases.state` (`docs/dauerbetrieb.md` §6). Neue Spalten in `gaps`: `case_id`, `due_at`, `residual_qty`.
Neue Events: `option.created`, `option.changed`, `decision.escalated`, `gap.unclosable`, `gap.closed`.

## 10. Fertig, wenn

1. Die Kopfzeile zeigt je Produkt `coverage(system)` neben `coverage(secured)` und die Stückzahl in jedem der vier Zustände. Die Summe der vier Zustände ist `still_to_pack`.
2. Jede Lücke mit `impact = deadline_blocker` hat entweder einen Plan mit Entscheidung oder den Zustand `unclosable` mit `residual_qty`. Der Test prüft das für jede Lücke im eingefrorenen Datenstand.
3. Eine Option mit Ankunft nach `latest_useful_arrival` ist `feasible = false` und zählt in keinem Plan.
4. Eine eingespielte Antwort eines Lieferanten („20.000 Stück, Ankunft So 09:00“) hebt die Option auf `confirmed`, ändert die Kopfzeile und lässt die kostenlosen Absicherungen verfallen.
5. Eine offene Entscheidung wechselt 30 Minuten vor `act_by` zur nächsten Rolle.
6. Der Test mit dem Paket `demo_bikes` erzeugt mit denselben Generatoren mindestens eine Option und einen Plan.
7. Kein Generator enthält einen Kundenwert (`tests/test_no_customer_values.py`).
8. `tests/test_every_unit_accounted.py`: Für jedes Produkt ist `packed + secured + planned + open + unclosable = demand`. Keine Kopie fehlt in der Summe.
9. Bei Mangel an einem geteilten Teil deckt die Verteilung zuerst `preordered`. Ein Test mit dem Soony-Stand (`@pytest.mark.customer_data`) zeigt das an den Spielkarten (`CMP-GAM-001`).
10. Ein Event `gap.unclosable` erzeugt im selben Durchlauf eine Entscheidung an die oberste Rolle der Eskalationskette.
11. Kein Plan enthält Ware ohne Freigabe.
