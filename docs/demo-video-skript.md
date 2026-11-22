
# Lineguard Demo Video Skript (Sprache: Englisch)

Zwei Versionen für ein voice-over Skript: ein full cut (ca. 2:50 min) und ein short cut (ca. 90 Sekunden). Die visuelle Spalte ist eine Empfehlung, die den App-Bildschirmen und den Folien entspricht.

---

## Version 1: Full Cut (approx. 2:50 min)

Speaking pace is about 140 words per minute, and the text is around 400 words. The limit for the video is 3 minutes.

### 0:00 – 0:15 | Hook

*Visual: Cost curve (slide 3), small dot on the far left, large one on the far right*

> "We are Lineguard. We find wrong stock bookings on the day they happen. One wrong number in the ERP, and nobody notices for days. On Sunday, the line stops. Lineguard moves the discovery to the day of the booking."

### 0:15 – 0:30 | What the customer told us

*Visual: Quote from Nils Berger (slide 3, left side)*

> "Soony is our first customer. On Saturday, Nils Berger, IT lead at Soony, told us: a zero too many is the classic error. You only see it at packing, and then he must check everything himself. That takes almost his whole week. So we built Lineguard."

### 0:30 – 0:45 | New file

*Visual: App dashboard, then the scan is uploaded, header turns red*

> "At the Hamburg site, the art book for the Collector's Edition is booked at 80,000 units. Now a scan arrives: a handwritten note from the supplier. The Watcher sees the new file at once, with no restart. The Reader reads it, handwriting included."

### 0:45 – 1:10 | Finding and impact

*Visual: Finding view with evidence, file and location highlighted*

> "The note says 8,000. The ERP says 80,000. A source ranking decides: the handwritten note beats the booking. Lineguard knows the bill of materials, so it calculates the impact: 5,900 Collector's Editions are missing, and the line stops on Sunday. The header shows 'System says' beside 'secured'. Every number links to its evidence."

### 1:10 – 1:30 | Proposal and approval

*Visual: Proposal card with price, deadline, approver; click on "Approve"*

> "The Decision agent builds a plan: a reorder with price, deadline, and the person who must approve it. The policy engine routes it to the right role. Nils approves the ERP correction. Paul Winter approves the reorder. Anything that commits money stays with a human."

### 1:30 – 1:55 | The agent stays on it

*Visual: Timeline view, emails in two languages, supplier reply, follow-up*

> "Then the Action agent takes over. It writes the mail in the supplier's language and knows whom to contact. It matches the reply, follows up, or passes the case to the next person. In this demo, mail runs in dry-run mode, and the ERP correction is a file, not a direct SAP write."

### 1:55 – 2:10 | How it works

*Visual: Architecture slide, or the five agents in the app*

> "Under the hood: five agents on one shared state. Every number comes from code. The LLM only reads documents and drafts messages. All of Soony's values sit in one customer package, and a second customer already runs on the same core."

### 2:10 – 2:35 | Result and business case

*Visual: Slide 5, bar graph €700k against €60k*

> "The result: the error was found on the day of the booking. The reorder from Nowak costs €16,800. Found on Sunday, the same error costs about €700,000: 5,900 Collector's Editions at €120 each. Lineguard costs €5,000 per site per month. One saved launch pays for about eleven years."

### 2:35 – 2:50 | Closing

*Visual: Slide 5, market card, then logo and tagline*

> "In Germany alone, about 23,000 manufacturing sites work this way. Soony is site one. Lineguard: if something is missing, you know while you can still do something about it."

### Notes

- Make sure that the numbers match your screens. Say them exactly as the app shows them.
- The €120 per missing Collector's Edition comes from Dr. Maren Vogt at Soony. €700,000 is 5,900 × €120, rounded down from €708,000.
- €5,000 per site per month is our proposal, not a price that Soony agreed to. If the jury asks, say so.
- €16,800 is the Nowak offer in the demo, not a general result.
- The 23,000 sites are a rough count from public statistics (Destatis). Check the number before you record, or say "about twenty thousand".
- The quote from Nils is from our notes, not word for word. On screen, write "according to Nils Berger, IT & Systems Lead".
- "Prepares the ERP correction" is deliberate. Today Lineguard writes a correction file. It is not a direct SAP connection.
- Do not say that the Action agent sent live mail unless the demo runs in live mode. The default is DRY_RUN.
- Do not say that an ERP correction is complete until the next ERP export shows it.
- If you run over, shorten "How it works" first. Keep the quote, the result, and the closing.
- Spoken numbers: "eighty thousand", "eight thousand", "fifty-nine hundred", "sixteen thousand eight hundred euros", "seven hundred thousand euros", "a hundred and twenty euros", "five thousand euros", "twenty-three thousand".

---

## Version 2: Short Cut (90 seconds)

About 220 words at roughly 140 words per minute, so about 95 seconds. Speak a little faster than in Version 1.

### 0:00 – 0:10 | Hook

*Visual: Cost curve, dot on the far left against the far right*

> "We are Lineguard. We find wrong stock bookings on the day they happen. The later an error is found, the more it costs."

### 0:10 – 0:30 | Detection

*Visual: Dashboard, scan uploaded, header turns red*

> "Soony is our first customer. Nils, their IT lead, told us: a zero too many is the classic error, and nobody sees it until packing. In Hamburg, the art book is booked at 80,000 units. Then a handwritten supplier note arrives. The Watcher sees it at once. The Reader reads the handwriting: 8,000."

### 0:30 – 0:42 | Impact

*Visual: Finding view with evidence highlighted*

> "The note beats the booking. Lineguard knows the bill of materials: 5,900 Collector's Editions are missing, and the line stops on Sunday. Every number links to its evidence."

### 0:42 – 1:00 | Approval and action

*Visual: Proposal card, click on "Approve", then the timeline with emails*

> "The Decision agent proposes a reorder with price, deadline, and approver. Nils and Paul Winter approve. Anything that commits money stays with a human. Then the Action agent mails the supplier in their language and follows up. In the demo, mail runs in dry-run mode."

### 1:00 – 1:15 | Result

*Visual: Slide 5, bar graph €700k against €60k*

> "Found on the day of the booking, the Nowak reorder costs €16,800. Found on Sunday, the error costs about €700,000. Lineguard costs €5,000 per site per month, so one saved launch pays for about eleven years."

### 1:15 – 1:30 | Close

*Visual: Market card, then logo*

> "Five agents, every number from code, one package per customer. In Germany alone, about 23,000 sites work this way. Lineguard: if something is missing, you know while you can still do something about it."

### Notes

- Cut from the longer version: the source ranking details, the ERP correction file, and most of the architecture. Keep those for the live pitch.
- Keep the quote from Nils, the human approval, the dry-run statement, and the €700,000 against €16,800.
- The same rules for numbers apply as in Version 1: €120 per copy comes from Soony, €5,000 per month is our proposal, and 23,000 sites is a rough count.
- If you run over, shorten "Approval and action" first, because the timeline visual carries it well.
- Read it aloud once with a timer. If you finish under 80 seconds, slow down for the numbers.
