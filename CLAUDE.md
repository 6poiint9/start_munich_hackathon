# Repository agent instructions

Whenever you are not completely sure about a requirement, behavior, decision,
fact, or answer, use the `grill-me` skill before relying on an assumption. If
skill invocation is unavailable, read and follow
`.claude/skills/grill-me/SKILL.md`. Investigate facts first, then ask the user
about any uncertainty that remains.

Use the `simple-english` skill for every reply and whenever you write or edit
human-readable text, including README files, documentation, and messages.
Load it at the start of each task. If skill invocation is unavailable, read
`.claude/skills/simple-english/SKILL.md` and its relevant references instead.
Apply its guidance without changing facts, uncertainty, requirements, quoted
text, code, identifiers, commands, or other content that must remain exact.

## Implementation

Before you write or change product code, read `docs/umsetzung.md` for the order
of the steps and `architecture.md` for the design. The first table in
`architecture.md` names the file in `docs/` that you must read for each part. Keep customer values
out of the core package (`docs/kern-und-kundenpaket.md`).
