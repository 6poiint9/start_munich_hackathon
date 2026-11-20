---
name: writing-python-code
description: Writes, refactors, and reviews Python code using the Google Python Style Guide, including naming, imports, exceptions, resource handling, docstrings, typing, formatting, and validation practices. Use when creating or changing Python modules, packages, scripts, tests, or .py files. Don't use for non-Python code or for merely running an existing Python command without changing code.
---

# Writing Python Code

Apply this procedure when creating, modifying, or reviewing Python code.

## Workflow

1. Inspect the target file, project configuration, dependency manifest, and
   nearby Python code. Follow established project conventions and supported
   Python versions unless they conflict with correctness or safety.
2. Read
   [references/google-python-style.md](references/google-python-style.md)
   before writing code. Apply its naming, import, exception, documentation, and
   typing rules.
3. Reuse the project's formatter, linter, type checker, and test runner. Do not
   add or replace tooling solely to enforce this skill.
4. Make the smallest complete change. Keep functions focused, APIs typed,
   resources explicitly managed, errors specific, and modules safe to import.
5. Validate every changed Python file:

   ```bash
   python3 "$HOME/.copilot/skills/writing-python-code/scripts/validate_python.py" \
     path/to/module.py
   ```

   Pass all changed `.py` and `.pyi` files in one invocation. Then run the
   smallest existing project lint, type-check, and test commands that cover the
   change.
6. Fix every syntax, Pylint, type-check, or test finding caused by the change.
   Rerun validation until it succeeds. Keep suppressions narrow and explain
   non-obvious suppressions.

## Required decisions

- Use descriptive PEP 8 names: `lower_with_under` for modules, functions,
  methods, parameters, and variables; `CapWords` for classes and exceptions;
  `CAPS_WITH_UNDER` for constants.
- Import packages and modules rather than individual functions or classes,
  except for supported typing symbols. Use absolute imports and group imports
  at the top of the file.
- Avoid mutable global state and mutable default arguments.
- Raise specific built-in or domain exceptions. Never use `assert` for runtime
  validation, and do not catch broad exceptions unless re-raising or forming a
  documented isolation boundary.
- Use context managers for files, sockets, database connections, and other
  closeable resources.
- Add type annotations to public APIs and code where types improve safety or
  clarity. Express nullable values explicitly.
- Add docstrings to public, nontrivial, or non-obvious APIs. Comment intent and
  constraints rather than restating code.
- Use lazy logging interpolation: `logger.info("Loaded %s", resource_name)`.
- Put executable behavior in `main()` behind
  `if __name__ == "__main__":` so modules remain importable.

## Output expectations

Deliver Python code that matches the repository, follows the reference, and
passes available project checks. Preserve public behavior unless the request
explicitly changes it.
