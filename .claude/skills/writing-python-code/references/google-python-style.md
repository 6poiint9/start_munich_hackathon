# Google Python Style Checklist

Use this checklist when writing or reviewing Python. Existing project style is
a tie-breaker, not a reason to preserve unsafe or incorrect behavior.

## Naming and structure

- Use descriptive names and avoid unfamiliar abbreviations.
- Use `lower_with_under` for packages, modules, functions, methods, parameters,
  and variables.
- Use `CapWords` for classes and exceptions. End exception names with `Error`.
- Use `CAPS_WITH_UNDER` for constants.
- Prefix internal names with one underscore. Avoid double-leading underscores
  for privacy; name mangling harms readability and testability.
- Avoid single-character names except for narrow counters and iterators, `e`
  for exceptions, `f` for file handles, private unconstrained type variables,
  or established mathematical notation.
- Do not encode a value's type in its name.
- Give Python files a `.py` extension and never use dashes in module or package
  names.
- Keep functions focused. When a function grows beyond roughly 40 lines,
  consider extracting coherent operations.
- Keep modules importable. Put executable behavior in `main()` and guard it:

  ```python
  if __name__ == "__main__":
      main()
  ```

## Imports and dependencies

- Import packages and modules rather than individual types, classes, or
  functions. Refer to members through the module namespace.
- `typing` and `collections.abc` symbols used for annotations are exempt and
  may be imported directly.
- Use absolute imports with full package paths. Do not manipulate `sys.path` to
  make ambiguous local imports work.
- Place imports after the module docstring and before globals. Group them in
  this order: future, standard library, third party, repository packages.
- Put imports on separate lines, except grouped imports from `typing` and
  `collections.abc`. Sort each group lexicographically.
- Do not hide required dependencies behind local imports. Use conditional
  imports only when necessary to avoid runtime-only typing dependencies.

## Errors and state

- Raise specific built-in exceptions when appropriate, such as `ValueError`
  for an invalid argument.
- Do not use `assert` for input validation or required application logic.
  Assertions are appropriate for tests and nonessential internal invariants.
- Never use bare `except:` or catch `Exception` unless immediately re-raising
  or implementing a documented isolation boundary that records the failure.
- Keep `try` blocks small so handlers cannot mask unrelated failures.
- Use `finally` or, preferably, a context manager for cleanup.
- Make error messages accurately describe the condition and clearly delimit
  interpolated values.
- Avoid mutable global state. If unavoidable, keep it internal and document the
  design reason.
- Never use mutable or runtime-computed default arguments:

  ```python
  def collect(values: Sequence[str] | None = None) -> list[str]:
      if values is None:
          values = []
      return list(values)
  ```

## Expressions and control flow

- Use comprehensions only for simple cases. Do not use multiple `for` clauses
  or multiple filter expressions in one comprehension.
- Prefer default iteration and membership operations: `for key in mapping`,
  `if item in values`, and `for line in file`.
- Use generators when streaming improves clarity or memory use. Document
  yielded values with `Yields:` and ensure expensive resources are closed.
- Keep lambdas and conditional expressions simple and on one logical line.
- Prefer explicit control flow when a compact expression becomes difficult to
  read.
- Do not mutate a container while iterating over it.

## Resources, strings, and logging

- Close files, sockets, database connections, mappings, and similar resources
  explicitly. Prefer `with`; use `contextlib.closing` when needed.
- Use f-strings, `%`, or `str.format` for formatting. Do not build formatted
  messages with chained `+`.
- Do not accumulate strings with `+=` in loops. Collect pieces and use
  `"".join(parts)` or `io.StringIO`.
- Keep quote style consistent within a file. Always use triple double quotes
  for docstrings.
- Pass logging templates and values separately:

  ```python
  logger.info("Loaded resource %s", resource_name)
  ```

  Do not use f-strings in logging calls that support lazy interpolation.

## Formatting and documentation

- Indent with 4 spaces and never use tabs.
- Target 80-character lines. Use implicit continuation inside parentheses,
  brackets, and braces instead of backslash continuation.
- Use one statement per line and no terminating semicolons.
- Use two blank lines between top-level definitions and one blank line between
  methods.
- Use trailing commas when a container or parameter list closes on a separate
  line.
- Most modules do not need a shebang. Use `#!/usr/bin/env python3` only for a
  directly executable program.
- Start non-test modules with a docstring describing their contents and usage.
- Document every public, nontrivial, or non-obvious function or method.
- Use a one-line summary followed by a blank line and additional details.
  Include `Args:`, `Returns:` or `Yields:`, and `Raises:` when they add contract
  information not evident from the signature.
- Document class instances, not the fact that the object is a class. Document
  public attributes in an `Attributes:` section.
- Comment non-obvious intent, constraints, and decisions. Do not narrate Python
  syntax.
- Format new TODOs as
  `# TODO: issue-or-bug-link - Explanation of the temporary work.`

## Type annotations

- Annotate public APIs and code where types improve safety or readability. Do
  not annotate `self` or `cls` unless needed.
- Express nullable values explicitly as `X | None` on supported Python
  versions. Do not rely on `parameter: X = None`.
- Prefer abstract input types such as `Sequence` and `Mapping` when callers do
  not need to provide a concrete collection.
- Prefer built-in generics such as `list[str]` and `tuple[int, ...]` when the
  supported Python version allows them.
- Supply type parameters for generic types instead of leaving implicit `Any`.
- Use `str` for text and `bytes` for binary data.
- Give type aliases `CapWords` names and mark internal aliases with a leading
  underscore. Follow the project's supported typing syntax.
- Avoid type-checking suppressions. When unavoidable, scope them to the exact
  line and error and explain why when it is not self-evident.

## Validation

1. Parse every changed `.py` and `.pyi` file.
2. Run the repository's configured formatter in check mode.
3. Run Pylint or the repository's configured linter.
4. Run the repository's configured type checker.
5. Run focused tests for success, invalid input, boundary values, resource
   cleanup, and relevant failure paths.
6. Fix findings and repeat until all checks pass.

## Source

- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
