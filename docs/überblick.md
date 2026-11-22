Ausgangspunkt:
- Daten verändern sich ständig

Problem:

- Fehler fallen zu spät auf, system zeigt nicht die wirklichkeit (kann tage bis monate dauern bis fehler gefunden wird) (Falsch eingetragene Daten führen dazu, dass Lieferkette sich aufängt)
-> je später der Fehler entdeckt wird umso schlimmer die kosten bzw gravierendere Auswirkungen (irgendwie proportianal oder sowas darstellen dann? Irgendwie so ja der Punkt am anfang der ist hier noch klein und dann so ein punkt am ende und man hätte es vermeiden könenn, und das sind so steigende kosten kurve, x achse zeit und y achse kosten (wo falsch eingetragen wurde bis zum release kosten die die fehlen))
- Mitarbeiter müssen viel Zeit aufwenden um fehler zu finden und zu beheben (kostet auch Geld dann entsprechend) (vor dem tool nach dem tool mit zeit irgendwas, aufwand ist geringer, kosten sind geringer, fehlerquote ist geringer)
- Wenn man auf die Fehler agieren will muss man andere Leute kontaktieren (bottlenecks wenn man nicht weiß wer zuständig ist) mit schneller geschwindigkeit (und sprachlichen barrieren) und schnell erreicht von denen man bestimtme Informationen braucht um vollständigkeit von Supply Chain zu gewährleisten
-> Diese Dinge müssen automatisiert werden
- Informationen (PDF, Bild, Excel, unstrukturierte Daten) ODER (Informationen über zusammenhänge der Daten -> CD braucht eine Box oder sowas in der sie ist) liegen verstreut -> keiner kennt das Gesamtbild -> hoher Aufwand zusammenzutragen

Lösung:
- Agent der periodisch Daten vergleicht und unterschiede/unregelmäßigkeiten/inkonsistenzen auffällt -> Fehler Anomalien werden direkt erkannt statt erst wenn es zu spät ist und direkt mit Quelle angegeben. Agent rechnet die Auswirkungen der Abweichung aus. (zb 80k vs 8k dann fehlen 5,9k Collectors Edition und Linie steht am Sonntag)
- Agent der Fehler behebt autonom, Mensch muss nicht mehr ständig suchen. 
- Agent der alle notwendigen Schritte autonom ausführt, wie senden der Emails in unterschiedlichen Sprachen an die Supplier, arbeitet schnell und weiß wen er ansprechen muss. Der Agent bleibt dran, d.h. er wartet auf die Zusage des Suppliers, hakt nach oder gibt an weitere zuständige Person weiter. 
- Agent kann Zusammenhänge der Daten besser verstehen. Lineguard kennt die Stückliste, also welche Teile in welche Box gehören. Daraus rechnet es aus, was ein Fehler bedeutet.

Selling Point USP/Outcome:
- Fehler werden am Tag der Buchung gefunden, nicht an der LInie. Kosten/Folgen reduziert drastisch (lösung kostet dorot nur noch 16.8k statt 5.900 fehlende Kopien)
- Wenn etwas fehlt, wisst ihr es, solange ihr noch etwas tun könnt.
- Mitarbeiter spart sich Zeit und kosten um Fehler zu beheben. Mitarbeiter hat nicht den Overhead die zuständige Person zu suchen. Klickt nur noch
- Kein Fehler wird mehr zur teuren Überraschung (no more surprises)
- FÜR PITCH: Kostenkurve. Fehler kostet wenig, wenn manihn am Tag der Buchung findet und sehr viel wenn man ihn an der Linie findet (ganz rechts). Linegard schiebt den Zeitpunkt der Entdeckung auf der Kurve ganz nach links. (Artbook fall) (evtl noch so hinzufügen ganz rechts sonntag an der linie, es geht nichts mehr lkw braucht 13h, 5.9k zB, dann 1 tag vor relase nur noch express möglich, teurer und riskant, ganz links am tag der buchung (mit lineguard), normla nachbestellen möglich, folge 16.8k)

Ablauf in der App:
- wird gefunden, dann wird vorschlag gemacht, der muss akzeptiert werden
- dann wird von agent die schleife ausgelöst mit supplier etc.
- Befunde werden mit Belegen belegt (wenn er eine Entscheidung trifft, Bild, Excel datei oder sowas als Anhang)
- dann kann man in der app sehen welche schritte ausgeführt werden und auch die mails sehen die geschrieben wurden und sowas dunno (man sollte ein anschauliches Beispiel haben)

Technisch:
- Entscheidungslogik wann etwas angeschaut wird/ behebt wird. Schwelle an Quellen oder wie werden Anomalien bewertet?
- Agent weiß immer die richtige Ansprechperson


Who else has this problem:
Any company that brings parts from several suppliers together at one site for a fixed date, and whose ERP is filled by hand. Examples:
• Product launches in consumer electronics
• Seasonal goods in retail
• Start of series production in machine building
• Trade fair and promotion goods


What do our agents do:
Do agents take real actions (decide, write, escalate)? Yes.
- Decide: the Decision agent builds a plan for each gap, with price, deadline and the person who must approve.
- Write: the Action agent (lineguard/agents/action.py) drafts supplier mails, sends them, matches the replies to the thread and follows up when no answer comes.
- Escalate: the policy engine (lineguard/policy/engine.py) routes each decision by value and type, and passes it to the next role when needed.
- Correct: it prepares the ERP correction (connectors/erp_writer.py).
- Limits to say openly: a person approves anything that commits money. Mail runs in DRY_RUN by default. The ERP write-back is a correction file today, not a direct SAP connection.
Solid architecture, not one big prompt? Yes.
Five agents: Watcher, Reader, Stock Truth, Decision and Action work on one shared state in SQLite. An event table is the queue between them.
- Code computes: every number comes from plain code. The LLM only reads documents and writes drafts, through one entry point with cache, retries and a call log (lineguard/llm.py).
- Rules are data: approval rules are evaluated by code. No prompt decides who may approve.
- Evidence: each number on the page links to its fact, its file and the place in the file.
Messy data, nothing hardcoded? Yes.
- Formats: the Reader handles tables, PDFs and scans, including handwriting.
- Contradictions: a source ranking decides which source wins. For the art book, the handwritten note beats the ERP booking.
- No customer values in the core: all of Soony's values sit in a pack folder. tests/test_no_customer_values.py fails if a customer value appears in the core, and a second invented customer (demo_bikes) runs on the same core.
- Untrusted content: an instruction inside a document is flagged and counts in no calculation (tests/test_untrusted.py).
Does it cope when a new drop arrives? Yes. The Watcher (lineguard/agents/watcher.py) compares checksums and finds new, replaced and removed files. Only the changed file is read again, then coverage and plans are recomputed. In the demo, the scan arrives as a new file and the header turns red without a restart.

Pricing for Sooney:
My proposal is a subscription per site of about €5,000 per month, so about €60,000 per year for the Hamburg site. That is less than a third of the goods value of the art book case alone.
This number is an assumption. Nobody at Soony gave us a budget, the retail price of a copy, or the exact hours Nils spends. If the jury asks, say that it is our proposal and name the two figures behind it (€204,000 at risk against €16,800 for the early fix).
