# Google Shell Style Checklist

Use this checklist when writing or reviewing Bash. Existing project style is a
tie-breaker, not a reason to preserve unsafe behavior.

## Naming

- Name functions and mutable variables with lowercase letters and underscores:
  `load_config`, `config_file`.
- For namespaced library functions, use `package::function_name`.
- Name a loop collection with a plural noun and its element with the matching
  singular noun:

  ```bash
  local zone
  for zone in "${zones[@]}"; do
    deploy_to "${zone}"
  done
  ```

- Capitalize constants, readonly values, and exported environment variables,
  separating words with underscores. Declare them near the top of the file:

  ```bash
  readonly CONFIG_DIR='/etc/example'
  export CONFIG_DIR
  ```

- Mark a value computed at runtime as readonly immediately after validating it:

  ```bash
  RELEASE_VERSION="$(read_release_version)"
  [[ -n "${RELEASE_VERSION}" ]] || return 1
  readonly RELEASE_VERSION
  ```

- Use `local` for function variables. Do not combine `local` with command
  substitution because `local` masks the substitution's exit status:

  ```bash
  local response
  response="$(fetch_response)" || return
  ```

## File and program structure

- Use Bash for small utilities and wrappers, not complex applications.
- Start new executable scripts with `#!/bin/bash` and set shell options in the
  body. Preserve a repository's established shebang when modifying a file.
- Give each file a short header describing its purpose.
- Use `.sh` for libraries and make libraries non-executable. Executables may
  use `.sh` or no extension.
- Place constants first, then all functions, then execution code.
- Use a bottom-most `main` function when a script has other functions. End with
  `main "$@"`.
- Keep executable code out of the space between function definitions.

## Formatting and comments

- Indent with 2 spaces and no tabs, except where a `<<-` heredoc requires tabs.
- Target 80-character lines. Split long pipelines with one stage per line.
- Put `; then` and `; do` on the opening control-flow line. Align `fi`, `done`,
  and `esac` with their opening statements.
- Document every library function and every non-obvious function. Describe its
  purpose, globals, arguments, outputs, and meaningful return statuses.
- Comment intent and non-obvious behavior, not syntax.
- Write ownership-qualified TODOs, such as
  `# TODO(owner): Explain the temporary limitation.`

## Expansions, arguments, and data

- Quote variable and command expansions unless deliberate Bash semantics
  require otherwise. Prefer `"${name}"` over `"$name"`.
- Use `"$@"` to forward arguments. Do not use unquoted `$@` or `$*`.
- Use arrays for lists and command arguments:

  ```bash
  local -a args=(--format json)
  args+=(--output "${output_file}")
  generate_report "${args[@]}"
  ```

- Use `$(command)` rather than backticks.
- Use process substitution or `readarray` instead of piping into `while` when
  loop state must remain available afterward.
- Prefix wildcard paths, such as `./*`, so filenames beginning with `-` are not
  interpreted as options.
- Avoid `eval`. Do not store multiple command arguments in one string.

## Tests and arithmetic

- Prefer `[[ ... ]]` over `[ ... ]` or `test`.
- Use `-z` and `-n` for empty and non-empty strings.
- Use `==` for string equality. Leave the right side unquoted only when pattern
  or regular-expression matching is intentional.
- Use `(( ... ))` for numeric tests and `$(( ... ))` for arithmetic expansion.
  Avoid `expr`, `let`, and `$[ ... ]`.
- Be careful with standalone arithmetic under `set -e`; an expression
  evaluating to zero returns a non-zero status.

## Errors and command execution

- Write diagnostics to stderr and return a non-zero status for failure:

  ```bash
  error() {
    printf 'Error: %s\n' "$*" >&2
  }
  ```

- Check command results directly with `if` or `!` when adding context or
  recovery. Preserve `PIPESTATUS` immediately when individual pipeline results
  matter.
- Prefer shell builtins and parameter expansion over external processes when
  the result is equally clear.
- Prefer functions over aliases.
- Never use SUID or SGID shell scripts.

## Validation

1. Run `bash -n` for syntax.
2. Run ShellCheck for every script, regardless of size.
3. Exercise success, invalid-input, empty-value, whitespace-in-path, and
   command-failure cases relevant to the change.
4. Fix findings and repeat until all checks pass.

## Sources

- [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html)
- [Variable names](https://google.github.io/styleguide/shellguide.html#s7.2-variable-names)
