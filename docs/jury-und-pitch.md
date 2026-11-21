# Jury-Kriterien und Pitch-Bausteine

Lies diese Datei, wenn du Deck, Demo-Skript oder README schreibst, oder wenn du entscheiden musst, welches Teil bei Zeitnot wichtiger ist.

Quellen: `Lio_-_Challenge_Keep_the_Line_Running.pdf`, `Lio_-_Judging_criteria.pdf` (beide liegen nicht im Repo), Gespräch mit Nils Berger am Sa 21.11.

Stand Sa 21.11., 20:55: Der Pitch ist zurückgestellt, bis der Bau steht. Lio erwartet einen Pitch über das Startup und den echten Wert (`architecture.md` §0c). Preismodell, Zielkunde und die Geschichte der Firma fehlen in dieser Datei noch (`architecture.md` §11, Frage 23).

## 1. Eintrittskarte

Die Jury bewertet nur Teams, bei denen beides stimmt:

1. Das System läuft live vor der Jury.
2. Bis So 12:00 ist alles abgegeben: Prototyp (wenn möglich deployed), Pitch-Deck, Demo-Video mit höchstens 3 Minuten, Code mit kurzer README.

Demo: 3 Minuten Pitch, 2 Minuten Fragen. Die Demo früh starten. Das Video ist nur der Rückfall.

## 2. Kriterien und wo die Architektur sie erfüllt

| Kriterium | Was die Jury fragt | Antwort in der Architektur |
|---|---|---|
| Pitch | Ist das Problem in 30 Sekunden klar? Führt eine Linie vom Schmerz bei Soony zum Produkt? Nutzt das Team, was es von Soonys Leuten gelernt hat? | Leitfall Artbook: eine Null zu viel, SAP sagt 80.000, der Lieferschein sagt 8.000. Satz für die Bühne: „Am Samstag sagte uns Nils, dass so ein Fehler erst an der Linie auffällt und dass nur er ihn korrigieren darf. Deshalb prüft Lineguard jede Buchung sofort und legt ihm die fertige Korrektur hin.“ (`architecture.md` §0b) |
| Business Case | Warum zahlt Soony, und wie viel? Wer hat das Problem noch? Läuft es über einen Launch hinaus? | Kern und Kundenpaket: Der nächste Kunde ist ein Ordner (`docs/kern-und-kundenpaket.md`). Kennzahlen aus dem System: Zeit bis zum Fund, Zeit bis zur Korrektur, gerettete Kopien (`docs/buchungspruefung.md` §8). Antworten auf Fragen zu Wachstum und Kosten je Kunde: `docs/skalierung.md` §4. Offene Zahlen: §4 |
| Technische Tiefe | Handeln die Agenten wirklich? | Mails an Lieferanten, Sperrung einer Charge, Korrektur ans ERP, Eskalation an die nächste Rolle (`architecture.md` §2.4, §2.5; `docs/lueckenschluss.md` §5) |
| | Tool-Use, Logik und Zustand statt eines großen Prompts? | 5 Agenten mit eigenen Tools, gemeinsamer Zustand, Event-Tabelle (`architecture.md` §1–§3). Zahlen rechnet Code, das LLM liest und schreibt |
| | Unordentliche und widersprüchliche Daten? Etwas fest eingebaut? | Quellen-Rangfolge und Tabelle `contradictions` (`architecture.md` §2.3), Schema-Erkennung (§6.1), Test `test_no_customer_values.py`, zweites Paket |
| | Neuer Drop ohne Umbau? | Watcher mit Prüfsummen, ersetzte Dateien, Fakten-Diff (`architecture.md` §2.1, §6.4) |
| | Was passiert, wenn das System falsch liegt? | `architecture.md` §6.6 |
| Taste | Ein Produkt, eine klare Empfehlung, ein Klick, ein guter Moment für die Entscheidung des Menschen | Eine Seite. Kopfzeile mit Deckung in Prozent. Karten mit einem Satz, Beleg, Preis und Knopf (`docs/buchungspruefung.md` §6) |

Schwach laut Jury: eine Tour durch alle Funktionen, zehn Folien Architektur, „der Markt ist riesig“, alle Zahlen auf einem Bildschirm.

## 3. Was Nils Berger gesagt hat und was daraus wurde

Die Tabelle mit den Aussagen steht in `architecture.md` §0b. Für den Pitch reichen drei Sätze:

1. Problem: Ein Tippfehler beim Wareneingang bleibt unbemerkt, bis das Teil an der Linie fehlt. Das dauert Tage bis Monate.
2. Engpass: Eine einzige Person darf korrigieren. Laut Nils kostet ihn das fast seine ganze Arbeitszeit.
3. Lösung: Lineguard findet den Fehler bei der Buchung, rechnet sofort mit der richtigen Menge und gibt Nils die Korrektur zum Freigeben.

## 4. Zahlen, die noch fehlen

Diese Zahlen kommen nur aus den Office Hours. Bis dahin zeigt das Deck die Größe ohne Zahl oder mit der Angabe „laut Nils“.

| Zahl | Wen fragen | Wofür |
|---|---|---|
| Stunden pro Woche für Korrekturen und Anzahl Korrekturen pro Monat | Nils Berger (er sagte „fast alles“, ohne Stundenzahl) | Preis pro Jahr gegen gesparte Zeit |
| Kosten einer fehlenden vorbestellten Kopie und einer fehlenden Standard-Kopie | Dr. Maren Vogt | Wert der geretteten Kopien |
| Kosten einer Stunde Linienstopp | Felix Brunner | Wert der früheren Warnung |
| Gab es schon einen Versuch, Fehler automatisch zu finden? | Nils Berger (im Gespräch ohne klare Antwort) | Abgrenzung im Pitch |

## 5. Über Soony hinaus

Das Muster gilt für jede Firma, die Teile von mehreren Lieferanten an einem Ort zu einem festen Termin zusammenführt und deren ERP von Hand gefüllt wird: Produktstart in der Unterhaltungselektronik, Saisonware im Handel, Serienanlauf im Maschinenbau, Messe- und Aktionsware.

Was dafür nötig ist, steht in `docs/kern-und-kundenpaket.md`: ein neues Paket mit Frist, Nachfrage, Quellen und Freigaberegeln. Der Kern bleibt gleich.

Im Pitch nennt das Team Lineguard als Produkt und Soony als ersten Kunden: „Lineguard hat bei Soony den Launch gesichert“, nicht „wir haben Soonys Problem gelöst“.
