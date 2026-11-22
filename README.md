# Lineguard

Lineguard helps a team find material shortages and prepare actions before a production deadline. It reads customer files, calculates coverage, flags possible booking errors, and prepares supplier mails and ERP correction proposals.

Team TRIPLET built Lineguard at START Hack Munich 2026 for the Lio case "Keep the Line Running". The first deployment is the "Launch Control Room" for the games publisher Soony.

## Live deployment

Lineguard runs at [https://lineguard.dlsystem.de](https://lineguard.dlsystem.de). The server reads the Soony files from the challenge portal every 60 seconds, computes the coverage, and sends and reads supplier mail through the team mailbox. The page and the API run in Docker behind an nginx reverse proxy with HTTPS. The API is at `https://lineguard.dlsystem.de/api/`, for example `/api/healthz` and `/api/state`. `docs/deploy.md` describes the setup.

## Start in three commands

You need Python 3.12 or later, Node 20.19 or later, and `pdftotext` and `pdftoppm` from poppler.

```bash
make install                                   # creates .venv and installs the backend
LINEGUARD_PACK=tests/fixtures/packs/demo_bikes .venv/bin/python -m lineguard import --no-llm
LINEGUARD_PACK=tests/fixtures/packs/demo_bikes .venv/bin/python -m lineguard run
```

The API then runs at `http://localhost:8000`. `demo_bikes` is an invented customer in this repository. It needs no key and no network.

Start the page in a second terminal:

```bash
cd web && npm ci && npm run dev
```

Open `http://localhost:3000`.

Every command also runs without `make`. `python -m lineguard --help` lists the commands: `init`, `import`, `run`, `recompute`, `reread`, `send-logged`, `demo-save`, `demo-reset`.

## Configuration

Copy `.env.example` to `.env`. The file lists each variable. The important ones:

| Variable | Purpose |
|---|---|
| `LINEGUARD_PACK` | Folder of the customer pack that the core loads |
| `XAI_API_KEY` | Key for the LLM that reads documents and writes mail drafts. Without it, the document reader does not extract facts |
| `MAIL_MODE` | `DRY_RUN` writes mails only to the log (default). `LIVE` sends them. `REPLAY` reads recorded replies |
| `LINEGUARD_NOW` | Fixes the clock for a demo replay or a test |
| `LINEGUARD_SOURCE_PATH` | Reads the customer files from a local folder and not from the portal |

The customer pack `packs/soony_gh6/` is in this repository. It holds the configuration for Soony. The customer files in the data folder `data/` and the frozen test snapshot are not in this repository. They stay on the machines of the team.

The configured LLM receives document text and images. Do not send customer data to an external provider without permission.

## Current limits

- The Soony ERP exports are read as files. Approved ERP corrections are saved as local JSON and CSV proposals. They do not update SAP.
- `DRY_RUN` does not send mail. Routine mail can run automatically only when the customer pack allows it. Orders and other binding mail need approval.
- Each known person can approve. Rejections, discards and count requests use role rules. Person selection is not a login.
- The app does not enforce the joint approvals required by parts of Soony's policy.
- The live page has no login. Each visitor can act as any known person.
- If mail delivery fails, the decision stays approved. Check the mailbox before sending again to avoid a duplicate order.
- The frozen Soony files were opened locally. Their full contents and the complete document-to-action flow were not verified.
- The reader splits long text into parts and sends PDF pages with little text to a vision model. Text split across parts and images on text-heavy pages can be missed. Review important evidence.
- Multi-product state totals and the remaining watcher and shortage rules need further end-to-end verification.

## How it is built

1. The core in `lineguard/` holds no customer value. Each customer is a pack: deadline, routes for the files, thresholds and approval rules as data. A test with the invented pack proves that the same core serves a second customer.
2. Five agents work on one shared state in SQLite. An event table is the queue. The Watcher finds new and replaced files. The Reader turns each file into facts with evidence. Stock Truth computes coverage, gaps and the moment a line stops. The Decision agent builds a plan for each gap. The Action agent writes and sends supplier mails and reads the replies.
3. Calculations use code. The LLM reads documents and writes drafts. Cases link to their available facts and source files.
4. Content from outside is data. An instruction in a document is flagged and counts in no calculation.
5. The pack defines approval roles and suggested owners. The API records the selected person but does not authenticate that person.

## The five agents

Each agent is a set of plain Python functions. An agent takes one event from the shared queue, does its work on the shared state, and writes new events for the next agent. `lineguard/pipeline.py` maps each event type to its agent.

| Agent | Code | Input | What it does | Output |
|---|---|---|---|---|
| Watcher | `lineguard/agents/watcher.py` | The file list of the portal, every 60 seconds | Compares the SHA-256 checksum of each file with the stored one. Finds new, changed and removed files. When a file is removed or replaced, it marks the old facts as no longer current | `file.added`, `file.changed`, `file.removed` |
| Reader | `lineguard/agents/reader/` | One file | Picks a parser from `routes.yaml` of the pack. Code reads tables, CSV, Excel and JSON. The LLM reads PDFs, Word files, scans and handwriting. Each value becomes a fact with its source file and its place in the file | Facts, `facts.updated` |
| Stock Truth | `lineguard/agents/stock_truth.py`, `lineguard/coverage/` | The current facts | Computes the coverage of each part: usable stock plus secured inbound minus demand. Checks each goods receipt against the delivery note, the order, the weight, the packages and the history. Ranks the sources when they disagree. Finds the time when each line stops | Gaps, booking findings, `gap.changed` |
| Decision | `lineguard/coverage/closing.py`, `lineguard/coverage/options/` | Each gap that blocks a demand date | Builds options from the facts: accept an offer, release held goods, ask for an earlier arrival, source from another supplier, sort a failed lot, confirm a supplier condition. Checks each option for arrival time, cost and certainty, and recommends one. The approval rules of the pack name the role that must approve. An open decision moves to the next role 30 minutes before it is due | Decisions, `action.requested` |
| Action | `lineguard/agents/action.py` | An option that needs a supplier | Writes the mail in the language of the supplier, with an English copy. Sends routine questions at once and holds binding mail until a person approves. Reads the replies over IMAP and attaches them to the case. Sends a reminder when a supplier does not answer | Mails, `email.received` |

An approved ERP correction goes to a separate writer (`lineguard/connectors/erp_writer.py`). Today it writes a JSON and CSV proposal file. It does not change SAP.

## Technical depth

### Agents that do the work

The agents act on their own, without a person who starts each step:

- They decide. The Decision agent picks an option for each gap and names the person who must approve it. When no option arrives in time, it raises an alert for the chief procurement officer.
- They write. The Action agent writes supplier mails in the language of the supplier. On the live server, it sent two mails to suppliers in Chinese and English, and it read both replies. The booking check of Stock Truth proposes ERP corrections.
- They escalate. An open decision moves to the next role in the escalation chain 30 minutes before its deadline. A supplier without a contact becomes an escalation, and the action runs again when the contact arrives.

A person approves each step that commits money or changes the ERP. A simple question to a supplier goes out without a click when the pack allows it.

### Real data, nothing hardcoded

Lineguard reads the files as the portal delivers them. The Soony data has CSV and Excel exports from SAP, a legacy export with semicolons and decimal commas, supplier PDFs, scanned delivery notes with handwriting, Word memos, price lists and mails in several languages.

The core in `lineguard/` contains no value of a customer. Part numbers, suppliers, deadlines, file routes, column names, thresholds and approval rules are in the pack `packs/soony_gh6/`. A test (`tests/test_no_customer_values.py`) fails when a Soony value appears in the core. A second, invented customer (`tests/fixtures/packs/demo_bikes/`) runs on the same core without a change.

### Architecture

- State: one SQLite database per workspace holds files, facts, cases, gaps, options, decisions, actions and mails. The schema has numbered migrations.
- Queue: an event table is the queue and the audit log. A worker claims an event with one atomic update. A lease returns a stuck event to the queue. Dedupe keys make each step run once.
- Isolation: the orchestrator runs eight reader workers and one worker for each other agent. An error fails only its own event.
- Code computes, the LLM reads: every number on the page comes from code. The LLM has two narrow tasks with their own prompts: extract facts from a document as JSON (`prompts/reader_extract.md`), and write a mail draft (`prompts/email_draft.md`). It does not decide and does not calculate.
- Tools around the LLM: `pdftotext` extracts the text of a PDF. `pdftoppm` turns a scan into images for the vision model. The router picks the parser. The LLM calls have retries, a limit on parallel calls and a cache.
- Evidence: each fact keeps its source file, its place in the file and its source rank. A delivery note outranks an ERP booking. Each number on the page links to its document.
- Untrusted content: text from outside is data. A document that contains an instruction is flagged, and its facts count in no calculation.

### When a new drop arrives

A new drop needs no restart and no code change:

1. Within 60 seconds, the Watcher finds the new and changed files.
2. The Reader reads only these files. A file without a route goes to the document reader.
3. A newer fact replaces an older one. The date in the file decides (`as_of`), not the order of reading. The old fact stays in the history.
4. Stock Truth computes the coverage again, the Decision agent updates the plans, and the page shows the new state within seconds.

When the server was offline, it reads everything that changed in the portal after its restart. On the first start on Sunday, it read all 335 portal files of the weekend, with no failed file.

`architecture.md` is the overview. `docs/umsetzung.md` lists the build steps. `docs/api.md` describes the API for the page. `docs/deploy.md` describes how to run Lineguard on a server with Docker.

## Tests

```bash
make test        # or: .venv/bin/python -m pytest -q
make lint
```

Tests that need the customer snapshot skip themselves when the snapshot is absent. The CI runs the tests with the invented pack on each push.
