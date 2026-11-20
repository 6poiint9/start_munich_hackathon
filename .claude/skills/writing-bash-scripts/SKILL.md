---
name: writing-bash-scripts
description: Writes, refactors, and reviews Bash scripts using the Google Shell Style Guide, with strict variable naming, quoting, control-flow, error-handling, and validation practices. Use when creating or changing .sh files, Bash libraries, or Bash blocks in CI workflows. Don't use for POSIX sh, zsh, fish, PowerShell, or general one-off command execution.
---

# Writing Bash Scripts

Apply this procedure when creating, modifying, or reviewing Bash code.

## Workflow

1. Inspect the target file and nearby Bash code before editing. Preserve
   established project conventions unless they conflict with correctness or
   safety.
2. Confirm Bash is appropriate. Use it for small utilities and wrappers that
   primarily invoke other programs. Prefer a structured language when the
   solution requires substantial data processing, complex control flow, or is
   likely to grow beyond roughly 100 lines.
3. Read [references/google-shell-style.md](references/google-shell-style.md)
   before writing code. Apply its naming rules to every variable and function.
4. Make the smallest complete change. Keep arguments and filenames safe across
   spaces, empty values, and leading hyphens. Surface failures with actionable
   messages on stderr and non-zero exit statuses.
5. Validate every changed script:

   ```bash
   bash scripts/validate-shell.sh \
     path/to/script.sh
   ```

   Pass all changed `.sh` files in one invocation. For inline Bash in YAML,
   run the repository's existing workflow or YAML checks and manually apply the
   same style reference.
6. Fix every syntax or ShellCheck finding caused by the change, then rerun the
   validator until it succeeds. Do not suppress ShellCheck findings unless the
   behavior is intentional and the suppression is narrowly scoped with a
   reason.

## Required decisions

- Use lower snake case for function names and mutable/local variables:
  `download_file`, `output_dir`.
- Name loop variables after one element of the collection:
  `for zone in "${zones[@]}"`.
- Use upper snake case for constants, readonly values, and exported environment
  variables: `readonly OUTPUT_DIR='/tmp/output'`.
- Declare function variables with `local`. Separate declaration from command
  substitution so the command's exit status remains observable.
- Prefer `main "$@"` for scripts containing functions; keep functions together
  above `main`.
- Quote expansions, use `"${name}"`, pass arguments with `"$@"`, and represent
  argument lists as arrays expanded with `"${args[@]}"`.
- Prefer `[[ ... ]]`, `(( ... ))`, and `$(...)`. Avoid `eval`, backticks,
  aliases, and strings that encode multiple command arguments.
- Send errors to stderr. Check command failures explicitly when recovery or a
  more useful error message is needed.

## Output expectations

Deliver executable Bash code that matches the surrounding repository, follows
the reference, and passes the available validator checks. If Bash is the wrong
tool, explain the maintainability concern and use the repository's preferred
structured language instead.
