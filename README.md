# start_munich_hackathon

Launch control tower for the Lio challenge at START Hack Munich 2026. The customer is Soony (fictional). Soony must pack the last copies of Grand Heist 6 before Sunday 22 November, 20:00.

The tower answers one question: will Soony make the launch, and what breaks first? It reads the messy customer data from the Soony portal, computes a forecast, and turns the forecast into a short list of risks. Each risk has an owner and an action.

## How it works

The tower runs a loop with these steps:

1. The sync step asks the portal for the file list. Each file has a SHA-256 checksum (a fingerprint of the content). New and replaced files are downloaded. Each version is kept under `data/versions`, and each change is logged in `data/changes.jsonl`.
2. The model step reads all files into one picture of the launch. It does not trust column names, delimiters, encodings or date formats. It finds columns through an alias list in `soony_tower/tables.py` and finds the tables in the Excel reports through a header search.
3. The forecast step computes two scenarios. The plan scenario repeats what the Soony launch plan believes. The realistic scenario removes the parts used since the stock snapshot, blocks parts with a revision that must not be packed, adds the last leg from the port or airport to Hamburg, and does not count silent shipments.
4. The document agent (`soony_tower/documents.py`) sends PDFs, scans, Word files and supplier notices to the Radeon cloud endpoint. Radeon returns the facts in a fixed JSON schema, in English, also for documents in Korean, Chinese or Polish. Each file version is read once, and the result is stored in `data/extractions`. `RADEON_MODEL` selects a model. The default is `Qwen3.8-27B`.
5. The risk step turns the forecast and the document facts into risks. Each risk has a stable id. The next run compares its risks with the previous run and reports which risks are new, worse or resolved.

The gap between the two scenarios is the answer to the customer quote "The system says we are fine. My gut says we are not."

## Setup

You need Python 3.12 and a team token from the portal (Settings page).

1. Create the virtual environment: `python -m venv .venv`
2. Install the packages: `.venv/Scripts/python -m pip install -r requirements.txt`
3. Copy `.env.example` to `.env`. Put your team token into `LIO_TOKEN` and your Radeon API key into `RADEON_API_KEY`.

Do not commit `.env` or the `data/` folder. The data must not leave the team. Both are in `.gitignore`.

## Commands

Run each command from the project root.

| Command | What it does |
| --- | --- |
| `.venv/Scripts/python -m soony_tower sync` | Downloads new and replaced files from the portal. |
| `.venv/Scripts/python -m soony_tower report` | Prints the forecast and the risks. |
| `.venv/Scripts/python -m soony_tower report --at 2026-11-21T17:00` | Replays the forecast at a given moment. |
| `.venv/Scripts/python -m soony_tower read --limit 5` | Lets Radeon read up to 5 documents that it has not read yet. |
| `.venv/Scripts/python -m soony_tower models` | Lists the models available from Radeon. |
| `.venv/Scripts/python -m soony_tower ping` | Sends a test request to the Radeon endpoint. |
| `.venv/Scripts/python -m soony_tower watch --every 300` | Syncs every 300 seconds, reads new documents and prints the changes. |
| `.venv/Scripts/python -m soony_tower serve` | Starts the cockpit and the HTTP API on port 8000. |

## Cockpit

The cockpit is a web page for the procurement team. To open it, run the `serve` command and go to `http://localhost:8000`. The page has these parts:

- The verdict tells how many copies the launch will miss. It puts the number from the launch plan next to the number from the tower.
- "What breaks first" lists the risks. Each risk has the copies at risk, the action, the owner and the evidence files.
- "Inbound runway" shows when each shipment for a launch part arrives in Hamburg, compared to the time when packing closes.
- "Parts for the launch" compares the need of each part with the parts that will really be in Hamburg.
- The replay bar at the bottom moves the clock. The forecast is computed again for that moment. Use it in the demo to show how the picture changed.
- The "Sync portal" button downloads new files from the portal and shows which risks are new, worse or resolved.

The page is `soony_tower/cockpit/index.html`. It uses no build step.

## Mail agent

The mail agent (`soony_tower/mail.py`) asks suppliers about open risks and reads their answers. It never sends a mail on its own. It works in three steps:

1. Radeon reads the open risks and writes a draft for each risk that a supplier can answer, for example "confirm the pickup and the tracking number for PO 4500318735". The address comes from the supplier profile in the portal data, never from the model. The draft must not order or accept prices. If it must, the draft is marked "commits money".
2. A person reads the draft in the cockpit, can change it, and clicks "Approve and send". The mail goes out by SMTP from `MAIL_ADDRESS`.
3. The agent fetches the replies by IMAP. It matches each reply to its question by the mail headers, or else by the sender. Radeon reads the reply and its attachments. A clear answer, for example a confirmed pickup with a tracking number, changes the risk to "Answered". A suspicious reply, for example a new bank account, becomes a high risk.

To set it up:

1. Create a Gmail account for the team and turn on 2-step verification.
2. Create an app password for the account in the Google account security settings.
3. Register the address in the portal under Settings, Mail senders. Suppliers do not answer other addresses.
4. Put `MAIL_ADDRESS` and `MAIL_APP_PASSWORD` into `.env`, or into the environment on Render.

On the server, the agent checks the inbox after each sync and writes drafts for new risks. Set `MAIL_AUTODRAFT=0` to stop the automatic drafts. On the command line, `python -m soony_tower drafts` writes drafts and `python -m soony_tower inbox` reads the replies.

## Deployment on Render

The repository has a `Dockerfile` and a `render.yaml` blueprint. The portal data is not in the image. When the server starts, it downloads the data from the portal with the team token. Then it syncs again every 300 seconds and lets Radeon read 3 more documents after each sync, the most important first.

1. Push the repository to GitHub. Make sure that `.env` and `data/` are not in the commit.
2. On render.com, select New, then Blueprint, and select this repository.
3. Enter `LIO_TOKEN` and `RADEON_API_KEY` when Render asks for them.
4. After the deploy, open the Environment tab of the service and copy `COCKPIT_PASSWORD`. Render generated it.
5. Open the service URL. The user name is `soony`, the password is the value from step 4.

These environment variables control the server:

| Variable | Default | What it does |
| --- | --- | --- |
| `COCKPIT_PASSWORD` | not set | Turns on the browser login. Without it, the page is open. |
| `COCKPIT_USER` | `soony` | The user name for the login. |
| `SYNC_EVERY` | `300` in Docker, `0` local | Seconds between two portal syncs. `0` turns the background sync off. |
| `DOC_READS_PER_SYNC` | `3` | Documents that Radeon reads after each sync. |
| `RADEON_MODEL` | `Qwen3.8-27B` | Model used for Radeon requests. |

The free Render plan stops the service after 15 minutes without visitors, and it deletes the downloaded data. The next visit starts the service again, and the first sync takes about one minute. Open the page some minutes before a demo.

## HTTP API

| Endpoint | What it returns |
| --- | --- |
| `GET /api/status?at=...` | Forecast, components, inbound shipments and risks, from the files on disk. |
| `POST /api/sync` | Syncs with the portal, then returns the same data as `/api/status`. |
| `GET /api/changes` | Every file change detected so far. |

## Assumptions

`soony_tower/settings.py` holds every assumption that the data does not give, for example the hours without an update before a shipment counts as silent. Each value names the Soony person who can confirm it. Replace the values with the answers from the office hours.

