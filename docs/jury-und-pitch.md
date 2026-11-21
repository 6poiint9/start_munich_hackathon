# Jury-Kriterien und Pitch-Bausteine

Lies diese Datei, wenn du Deck, Demo-Skript, Video oder README schreibst, oder wenn du entscheiden musst, welches Teil bei Zeitnot wichtiger ist.

Quellen: `Lio_Challenge.pdf` und `Lio_Judging.pdf` (beide liegen nicht im Repo), Gespräch mit Nils Berger am Sa 21.11., 18:30 (Notizen von Ben, O-Ton sinngemäß).

Stand Sa 21.11., 22:45: Der Bau hat Vorrang. Preismodell und Geschichte der Firma sind noch offen (`architecture.md` §11, Frage 23). Diese Datei legt fest, was im Pitch steht. Die Formulierung kommt am Sonntag (`docs/umsetzung.md`, Stufe D).

## 0. Die Haltung

Wir sind ein Startup mit einem Produkt. Soony ist unser erster Kunde.

- Richtig: „Wir haben Lineguard gebaut, eine Lösung für Firmen, deren Bestand im ERP nicht stimmt. Bei Soony hat sie den Launch gesichert.“
- Falsch: „Wir haben Soonys Problem gelöst.“

Die Jury sagt dasselbe: „Soony is your first customer, not your only one. Show us a company, not a one-off project.“

## 1. Eintrittskarte und Abgabe

Die Jury bewertet nur Teams, bei denen beides stimmt:

1. Das System läuft live vor der Jury.
2. Bis **So 12:00** ist alles abgegeben.

| Abgabe | Was genau | Wo im Plan |
|---|---|---|
| Prototyp | Läuft. Deployed, wenn möglich. Sonst lokal und das Video als Beleg | `docs/umsetzung.md`, Stufe C (Deployment) und D1 |
| Pitch-Deck | 4 Folien plus 2 bis 3 Folien als Anhang (§6) | Stufe D3 |
| Demo-Video | Höchstens 3 Minuten | Stufe D3 |
| Code | Repo, z. B. GitHub, mit kurzer README | Stufe D2 |

Demo am So ab 14:00: 3 Minuten Pitch, dann 2 Minuten Fragen der Jury.

Tipps der Jury: „Show, don't tell. Start the demo early. Slides are support, not the show.“ · „If the Wi-Fi dies, your demo video saves you. Still, the live run is what counts.“ · „Go deep, not wide.“

## 2. Kriterien und Beleg

| Kriterium | Was die Jury fragt | Unser Beleg |
|---|---|---|
| **1. Pitch, der hängen bleibt** | Ist das Problem in 30 Sekunden klar? | Folie 1 in 20 Sekunden: 80.000 gebucht, 8.000 geliefert, 5.900 Collector's ohne Artbook |
| | Führt eine klare Linie vom Schmerz bei Soony zum Produkt? | Nils: Fehler fällt erst beim Packen auf → Lineguard prüft beim Wareneingang. Nils muss alles selbst prüfen → die Karte zeigt alle Belege nebeneinander (`docs/buchungspruefung.md` §1, §6) |
| | Nutzt das Team, was es von Soonys Leuten gelernt hat, nicht nur die Daten? | Satz für die Bühne (§3). Die Regel „super wichtig → Mensch, sonst automatisch“ kommt direkt von Nils (`docs/buchungspruefung.md` §6a) |
| **2. Echter Business Case** | Warum dieses Problem, warum jetzt, was ist es wert? | Nils: „fast die komplette Woche“ geht in Fehlerkorrektur. Ein Launch mit fester Frist macht jeden späten Fund teuer (§4) |
| | Warum zahlt Soony, und ungefähr wie viel? | Nils: Automatisch wurde es noch nie versucht, es fehlt die Zeit. Deshalb würden sie kaufen. Preis: offen (§5) |
| | Wer hat das Problem noch? Läuft es über einen Launch hinaus? | Kern und Kundenpaket, zweites Paket `demo_bikes` (`docs/kern-und-kundenpaket.md`). Nils: Andere Kunden haben ähnliche Daten. Dauerbetrieb nach der Frist (`docs/dauerbetrieb.md`) |
| **3. Technische Tiefe** | Handeln die Agenten wirklich (entscheiden, schreiben, eskalieren)? | Mail an Lieferanten, Sperre einer Charge, Korrektur ans ERP (Mensch oder automatisch nach Regel), Eskalation an die nächste Rolle (`architecture.md` §2.4, §2.5; `docs/lueckenschluss.md` §5, §8) |
| | Tool-Use, Logik und Zustand statt eines großen Prompts? | 5 Agenten mit eigenen Tools, gemeinsamer Zustand, Event-Tabelle (`architecture.md` §1–§3). Zahlen rechnet Code, das LLM liest und schreibt |
| | Unordentliche und widersprüchliche Daten? Etwas fest eingebaut? | Quellen-Rangfolge, Tabelle `contradictions` (`architecture.md` §2.3), Schema-Erkennung (§6.1), `tests/test_no_customer_values.py`, Grenzen im Paket |
| | Neuer Drop ohne Umbau? | Watcher mit Prüfsummen, ersetzte Dateien, Fakten-Diff (`architecture.md` §2.1, §6.4) |
| | Was passiert, wenn das System falsch liegt? | `architecture.md` §6.6. Dazu: Kritische Korrekturen gibt ein Mensch frei. Jede automatische Korrektur lässt sich mit einem Klick zurücknehmen. Eine Korrektur gilt erst als erledigt, wenn der nächste ERP-Export sie zeigt (`docs/buchungspruefung.md` §6a, §7) |
| **4. Taste** | Fühlt es sich wie ein echtes Produkt an, aus einem Guss? | Eine Seite. Kopfzeile „System sagt“ neben „gesichert“. Karten mit einem Satz, Belegen, Preis und Knopf (`docs/lueckenschluss.md` §2, `docs/buchungspruefung.md` §6) |
| | Würden die Leute, die wir befragt haben, es an einem stressigen Sonntag benutzen? | Nils entscheidet auf der Karte, ohne Telefon und Gang ins Lager |
| | Stimmen die Details: Wortwahl, Standardwerte, der Moment, in dem ein Mensch entscheidet? | Standard ist `DRY_RUN` und `auto_enabled: false`. Der Knopf nennt die Folge („Deckung Collector's sinkt auf −5.900“) |

Schwach laut Jury: eine Tour durch alle Funktionen, zehn Folien Architektur, bevor klar ist, warum es zählt, „der Markt ist riesig“, alle Zahlen auf einem Bildschirm, Werte aus den Daten im Code.

## 3. Was Nils Berger gesagt hat

Die Anforderungen daraus stehen in `docs/buchungspruefung.md` §1. Für die Bühne:

**Satz für den Einstieg** (Muster der Jury: „On Saturday, Felix told us… so we built…“):
„Am Samstag hat uns Nils, IT-Lead bei Soony, gesagt: Eine Null zu viel ist der Klassiker. Das merkt man erst beim Packen, und dann muss er alles selbst nachprüfen. Deshalb prüft Lineguard jede Buchung, sobald die Ware ankommt, und legt ihm die Belege nebeneinander hin.“

Drei Sätze zum Problem:

1. **Spät:** Ein Tippfehler beim Wareneingang fällt erst auf, wenn das Teil gebraucht wird. Nach Tagen oder nach Monaten.
2. **Menschlich und häufig:** Fast alle Fehler macht ein Mensch, beim Fahrer, beim Lieferanten oder beim Buchen. Kein Einzelfall.
3. **Eine Person:** Nur Nils darf ins SAP. Er telefoniert, mailt, lässt im Lager nachschauen. Korrigiert wird sofort oder erst 2 Wochen später.

Zitate sind sinngemäß aus den Notizen. Auf der Folie steht „laut Nils Berger, IT & Systems Lead“.

## 4. Business Case

Was wir sagen dürfen, weil Nils es gesagt hat:

- „Fast die komplette Woche“ geht bei ihm in Fehlerkorrektur. Er würde lieber Software bauen und Daten genauer anschauen.
- Eine automatische Fehlererkennung wurde noch nie versucht. Es fehlt die Zeit. Deshalb würden sie eine Lösung kaufen.
- Am meisten stört ihn die Prüfung: Er muss selbst klären, ob ein Fehler wirklich einer ist.

Was das System misst (`docs/buchungspruefung.md` §8): Zeit vom Buchen bis zum Fund, Prüfzeit je Karte, Zeit bis zur Korrektur, Anteil der automatischen Korrekturen, Anzahl der Befunde im Rückblick.

Was der Fall bei Soony wert ist: 5.900 Collector's ohne Artbook. Laut CPO-Memo wird eine fehlende vorbestellte Kopie erstattet und kostet den Kunden.

Keine erfundenen Zahlen. Stundenzahl, Preis je Kopie und Preis von Lineguard stehen erst im Deck, wenn jemand bei Soony sie genannt hat (§5).

## 5. Zahlen, die noch fehlen

| Zahl | Wen fragen | Wofür | Bis dahin im Deck |
|---|---|---|---|
| Stunden pro Woche und Korrekturen pro Monat | Nils Berger | Gesparte Zeit gegen Preis | „fast die komplette Woche, laut Nils“ |
| Kosten einer fehlenden vorbestellten Kopie und einer Standard-Kopie | Dr. Maren Vogt | Wert der geretteten Kopien | „wird erstattet und kostet den Kunden“ (CPO-Memo) |
| Kosten einer Stunde Linienstopp | Felix Brunner | Wert der früheren Warnung | ohne Zahl |
| Grenzen für die Stufe `auto` | Nils Berger | `booking_check.tiers` im Soony-Paket | `auto_enabled: false` |
| Preis von Lineguard | Team | Folie 4 | ohne Zahl oder als Modell (z. B. je Standort) |

## 6. Pitch: 3 Minuten, 4 Folien

| Nr. | Folie | Zeit | Inhalt |
|---|---|---|---|
| 1 | Problem | 20 s | ERP: 80.000 Artbooks. Lieferschein: 8.000, von Hand korrigiert. Ohne Lineguard fehlt 5.900 Käufern ihre nummerierte Collector's Edition. Dazu der Satz von Nils (§3) |
| 2 | Live-Demo | ca. 1:45 | Keine Folie, das Produkt. Eine neue Datei kommt rein. Die Buchungsprüfung findet die Null zu viel. Die Karte zeigt die Belege nebeneinander. Die Kopfzeile zeigt sofort „System sagt“ neben „gesichert“. Nils gibt die Korrektur frei. Der Lückenschluss schlägt die Nachbestellung vor, die Mail an den Lieferanten geht nach Klick raus |
| 3 | Wie es funktioniert | 25 s | Eine Folie: 5 Agenten, ein gemeinsamer Zustand, der Code rechnet, Grok liest. Kern plus Kundenpaket. „Super wichtig → Mensch, sonst automatisch“ |
| 4 | Wirkung und Ausblick | 20 s | Weniger Prüfarbeit für Nils, im System gemessen (§4). Der nächste Kunde ist ein Ordner, kein Projekt. Teamname TRIPLET |

Die Demo startet früh, spätestens nach 20 Sekunden.

**Anhang (2 bis 3 Folien, nur auf Nachfrage):**

1. Architektur im Detail (`architecture.md` §1)
2. Was passiert, wenn das System falsch liegt (§2, Kriterium 3)
3. Zweiter Kunde: `demo_bikes` läuft mit demselben Kern, Ablauf „Neuer Kunde“ (`docs/betrieb-und-wartung.md` §7)

**Video:** Bildschirmaufnahme der Demo mit Sprechertext nach festem Skript, höchstens 3 Minuten. Zwei Aufnahmen, die bessere zählt. Es ist der Rückfall, wenn das WLAN ausfällt.

## 7. Über Soony hinaus

Das Muster gilt für jede Firma, die Teile von mehreren Lieferanten an einem Ort zu einem festen Termin zusammenführt und deren ERP von Hand gefüllt wird: Produktstart in der Unterhaltungselektronik, Saisonware im Handel, Serienanlauf im Maschinenbau, Messe- und Aktionsware. Laut Nils gibt es weitere Kunden mit ähnlichen Daten.

Was ein neuer Kunde braucht, steht in `docs/kern-und-kundenpaket.md` und `docs/betrieb-und-wartung.md` §7: ein neues Paket mit Frist, Nachfrage, Quellen, Grenzen und Freigaberegeln. Der Kern bleibt gleich.
