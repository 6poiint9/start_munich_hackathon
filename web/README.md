# Lineguard web

This folder holds the web page of Lineguard. It is one page that shows what can stop a line today, and the decisions, ERP corrections and supplier mails that wait for an approval. The page is written with Next.js 16 (App Router), React 19, Tailwind 4 and TypeScript. The text of the page is English.

## Start

You need Node.js 20.19 or newer. Run all commands in the folder `web/`.

1. Install the packages:

   ```bash
   npm install
   ```

2. Start the Lineguard backend. The page expects it on `http://localhost:8000`.
3. Start the page:

   ```bash
   npm run dev
   ```

4. Open `http://localhost:3000` in a browser.

The backend accepts browser calls only from port 3000 and port 3100. If you use a different port, the browser blocks the calls.

If the backend does not answer, the page reports that it cannot connect. It retries every 5 seconds. The page does not switch to demo data.

## Mock mode

Mock mode shows an invented bicycle factory. It needs no backend. Each approval changes the demo data in the memory of the browser. A reload of the page sets the demo data back.

```bash
NEXT_PUBLIC_MOCK=1 npm run dev -- --port 3100
```

## Environment variables

| Variable | Default | Effect |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | Base URL of the Lineguard API |
| `NEXT_PUBLIC_MOCK` | not set | `1` starts the page in mock mode |

Next.js reads the two variables when it builds the page. Set them before `npm run dev` or `npm run build`.

## Commands

| Command | Effect |
|---|---|
| `npm run dev` | Starts the development server |
| `npm run build` | Builds the page for production |
| `npm run start` | Serves the production build |
| `npm run lint` | Runs ESLint |
| `npm run typecheck` | Runs the TypeScript compiler without output |

## Files

| Path | Content |
|---|---|
| `app/page.tsx` | The page |
| `app/globals.css` | Design tokens (colors, type scale, fill patterns) and the styles of the page |
| `app/fonts/` | The font files with their licenses. The build needs no network |
| `components/case-detail/panel.css` | The styles of the case detail |
| `components/` | The parts of the page: top bar, coverage, approvals, case list, case detail |
| `lib/api.ts` | All calls to the API, and the switch to mock mode |
| `lib/normalize.ts` | Turns raw JSON into the types of `lib/types.ts`. A missing field becomes `null` |
| `lib/words.ts` | English words for the codes of the API |
| `lib/format.ts` | English formats for numbers, money and times |
| `lib/mock.ts` | The mock backend with the role rules of the API |
| `mock/demo.ts` | The demo data. `mock/state.json` and `mock/case.json` are its base |
| `public/mock-files/` | The invented documents that the evidence list opens in mock mode |

The API contract is in `docs/api.md` in the repository root. The page takes the words for deadline, product, line and units from `state.labels`. Do not write a customer word into the code.

## Behavior

- The page loads `/state`, the selected case and the event log every 5 seconds.
- "Acting as" stores the selected person in the browser. Each write call sends the `person_id` of this person in the header `X-Lineguard-User`.
- Any selected person can approve. Rejection, discarding and count requests still require the matching role.
- Person selection is not authentication. Restrict write access before a public deployment.

ERP corrections show the proposed data before approval. In `proposal_file` mode, approval saves local JSON and CSV files. It does not update the ERP. A later ERP export must confirm the new quantity. Browser mock mode does not save these files.

## Design

The sidebar links to Overview, Cases, Approvals and Activity. On narrow screens, it becomes an icon rail. Each view has a link in the URL.

The workspace uses light surfaces and a dark blue approval summary. Text and labels state the meaning of status colors. The case detail keeps the source documents and calculations close to the actions. Data that the page loads every 5 seconds does not move.
