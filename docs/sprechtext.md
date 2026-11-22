# Sprechtext für den Pitch

Deck: `pitch_deck_line_5slides.pptx`. Dauer: etwa 3 Minuten, rund 430 Wörter. Text in eckigen Klammern wird nicht gesprochen.

## Slide 1: Lineguard (ca. 10 s)

"Hi, we're Lineguard. We find booking errors the day they happen, not when the packing line runs out. Soony is our first customer. Let me show you why they need us."

## Slide 2: 80,000 ≠ 8,000 (ca. 30 s)

"On Sunday at 8 pm, Grand Heist 6 goes on sale. Fans have waited thirteen years.

[Pause]

SAP says Soony has 80,000 art books for the Collector's Edition. The delivery note says 8,000. Someone typed one zero too many.

[Auf den Pfeil zeigen]

Without the art book, no Collector's Edition can be packed. That's 5,900 fans who pre-ordered and get nothing on launch day."

## Slide 3: The later you find it, the more it costs. (ca. 25 s)

"When we talked to Nils, who runs IT at Soony, he told us: a wrong stock number only shows up when the part is needed again. Days, sometimes months later.

[Auf den roten Punkt zeigen]

For Soony, that's Sunday at the packing line. Too late for any truck. About 200,000 euros of Collector's Editions, gone.

[Auf den grünen Punkt zeigen]

Found on Wednesday, it's a normal reorder for 16,800 euros. Lineguard moves the discovery from here to here."

## Slide 4: Live demo (ca. 80 s, Wechsel in die App)

"Here's Lineguard running on Soony's real data.

[Neuen Lieferschein einspielen]

A new delivery note arrives from Nowak, a supplier in Poland. Nobody typed anything. Lineguard picked it up by itself.

[Fund öffnen]

It reads the scan, including the handwritten correction, and compares it with the order and with SAP. Order: 8,000. Delivery note: 8,000. SAP: 80,000. Two sources agree, so SAP is wrong.

It doesn't stop at the mismatch. It knows the bill of materials, so it tells us what it means: 5,900 Collector's Editions short.

[Vorschlag zeigen]

Lineguard already found a fix. Nowak has 8,000 art books in stock, 16,800 euros, in Hamburg in 13 hours. By Soony's own approval rules, Paul from procurement may approve this. One click.

[Freigeben klicken]

Now the agents work. The order goes to Nowak, in Polish, because nobody at Soony speaks Polish.

[Mail kurz zeigen]

The correction for SAP goes to Nils. Nothing changes in SAP without him. And Lineguard waits for Nowak's confirmation and follows up if it doesn't come.

From delivery note to confirmed reorder, with one human click."

## Slide 5: Soony is customer one. (ca. 30 s)

"So why does Soony pay? One caught error saved them about 200,000 euros. Lineguard costs 30,000 euros per site per year.

[Auf die Balken zeigen]

And Soony is not special. Every company that books goods by hand has this error. We start where it hurts most, companies with a hard deadline like launches and seasonal retail, and then every warehouse. A new customer is a new configuration, not a new project. At 100 sites, that's 3 million euros a year.

No line should stop for a reason you could have seen coming. We'd love one pilot on a real launch. Thank you."

## Hinweise für die Probe

- Die Demo wird am ehesten zu lang. Über 3 Minuten? Dann streicht zuerst "It doesn't stop at the mismatch …" und den Satz über das Nachhaken.
- Der Satz von Nils stammt aus der Mitschrift des Gesprächs und ist kein wörtliches Zitat. Sagt "he told us", nicht "he said, quote".
- 200,000 € = 5,900 × 34.50 € Herstellkosten pro Collector's Edition (`soony/master/products.csv`).
- 30,000 € pro Standort und Jahr ist eure Annahme (2,500 € pro Monat). Fragt die Jury, sagt das offen: "That's our planned price: 2,500 euros per site per month."
- Hängt die Live-Demo, spielt an dieser Stelle das Demo-Video ab und sprecht denselben Text darüber.

## Fragen der Jury (2 Minuten)

- "What if Lineguard is wrong?": "Two independent sources must agree. If they don't, Lineguard asks the warehouse to count. Nothing goes into SAP without a human."
- "What happens with new data?": "New files are picked up and read automatically. No rebuild."
- "Is this one big prompt?": "No. Code does the math, AI reads the documents, humans approve."
- "Why can't SAP do this?": "SAP only knows what was typed in. The truth is on the paper."
