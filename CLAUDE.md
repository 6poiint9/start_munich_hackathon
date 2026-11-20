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
