---
name: interview
description: Interview the user in depth about a project or design, then write a detailed specification.
---

Follow the user's instructions and interview them in detail about the relevant
technical implementation, UI and UX, concerns, tradeoffs, and other decisions.
Use the available question tool, follow its formatting requirements, and avoid
obvious questions. Continue until the specification is complete, then write it
to a file.

**Save location:** `<cwd>/.plans/<relevant-name>.md`

- `<cwd>` = the current working directory — the project you are actually working in. Specs live with the code they describe so they are easy to find, open in an editor, and commit alongside the work.
- `<relevant-name>` = a short kebab-case slug describing the spec topic, ending in `-spec.md` (e.g. `friends-tab-redesign-spec.md`).
- Create the `.plans/` directory if it does not exist.
- Always resolve and write the absolute path, and state the path you wrote to in your reply.
- Do not save specs under `~/.claude/` — they become impossible to find there.

Use the user's request as the interview topic.
