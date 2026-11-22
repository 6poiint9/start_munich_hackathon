# Lineguard

Lineguard helps a team find material shortages and prepare actions before a production deadline. It reads customer files, calculates coverage, flags possible booking errors, and prepares supplier mails and ERP correction proposals.

Team TRIPLET built Lineguard at START Hack Munich 2026 for the Lio case "Keep the Line Running". The first deployment is the "Launch Control Room" for the games publisher Soony.

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

Customer data is not in this repository. The customer pack `packs/soony_gh6/`, the data folder `data/` and the frozen test snapshot stay on the machines of the team.

The configured LLM receives document text and images. Do not send customer data to an external provider without permission.

## Current limits

- The Soony ERP exports are read as files. Approved ERP corrections are saved as local JSON and CSV proposals. They do not update SAP.
- `DRY_RUN` does not send mail. Routine mail can run automatically only when the customer pack allows it. Orders and other binding mail need approval.
- Person selection applies role rules but is not a login. Do not expose the app publicly without access control.
- The frozen Soony files were opened locally. Their full contents and the complete document-to-action flow were not verified.
- Document extraction limits text to 14,000 characters and scan PDFs to three pages. Review longer documents separately.
- Multi-product state totals and the remaining watcher and shortage rules need further end-to-end verification.

## How it is built

1. The core in `lineguard/` holds no customer value. Each customer is a pack: deadline, routes for the files, thresholds and approval rules as data. A test with the invented pack proves that the same core serves a second customer.
2. Five agents work on one shared state in SQLite. An event table is the queue. The Watcher finds new and replaced files. The Reader turns each file into facts with evidence. Stock Truth computes coverage, gaps and the moment a line stops. The Decision agent builds a plan for each gap. The Action agent writes and sends supplier mails and reads the replies.
3. Calculations use code. The LLM reads documents and writes drafts. Cases link to their available facts and source files.
4. Content from outside is data. An instruction in a document is flagged and counts in no calculation.
5. The pack defines approval rules. The API checks the selected person's role, but does not authenticate that person.

`architecture.md` is the overview. `docs/umsetzung.md` lists the build steps. `docs/api.md` describes the API for the page. `docs/deploy.md` describes how to run Lineguard on a server with Docker.

## Tests

```bash
make test        # or: .venv/bin/python -m pytest -q
make lint
```

Tests that need the customer snapshot skip themselves when the snapshot is absent. The CI runs the tests with the invented pack on each push.
