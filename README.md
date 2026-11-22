# Lineguard

Lineguard keeps a production or packing line with a fixed deadline running. It reads the files of a customer, computes the real coverage of each part, finds booking errors in goods receipts, and prepares decisions, ERP corrections and supplier mails. A person approves each of them with one click.

Team TRIPLET built Lineguard at START Hack Munich 2026 for the Lio case "Keep the Line Running". The first deployment is the "Launch Control Room" for the games publisher Soony.

## Start in three commands

You need Python 3.12 or later, Node 20 or later, and `pdftotext` and `pdftoppm` from poppler.

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
| `XAI_API_KEY` | Key for the LLM that reads documents and writes mail drafts. Without it, only tables are read |
| `MAIL_MODE` | `DRY_RUN` writes mails only to the log (default). `LIVE` sends them. `REPLAY` reads recorded replies |
| `LINEGUARD_NOW` | Fixes the clock for a demo replay or a test |
| `LINEGUARD_SOURCE_PATH` | Reads the customer files from a local folder and not from the portal |

Customer data is not in this repository. The customer pack `packs/soony_gh6/`, the data folder `data/` and the frozen test snapshot stay on the machines of the team.

## How it is built

1. The core in `lineguard/` holds no customer value. Each customer is a pack: deadline, routes for the files, thresholds and approval rules as data. A test with the invented pack proves that the same core serves a second customer.
2. Five agents work on one shared state in SQLite. An event table is the queue. The Watcher finds new and replaced files. The Reader turns each file into facts with evidence. Stock Truth computes coverage, gaps and the moment a line stops. The Decision agent builds a plan for each gap. The Action agent writes and sends supplier mails and reads the replies.
3. Every number is plain code. The LLM only reads documents and writes drafts. Each number on the page leads to its fact, its file and the place in the file.
4. Content from outside is data. An instruction in a document is flagged and counts in no calculation.
5. A person approves each decision, each ERP correction and each mail that commits money. The API checks the role of that person against the approval rules of the pack.

`architecture.md` is the overview. `docs/umsetzung.md` lists the build steps. `docs/api.md` describes the API for the page. `docs/deploy.md` describes how to run Lineguard on a server with Docker.

## Tests

```bash
make test        # or: .venv/bin/python -m pytest -q
make lint
```

Tests that need the customer snapshot skip themselves when the snapshot is absent. The CI runs the tests with the invented pack on each push.
