---
name: writing-javascript-code
description: Writes, refactors, and reviews JavaScript using the Google JavaScript Style Guide, including modules, declarations, naming, formatting, JSDoc, error handling, and validation with Node.js, ESLint, and Prettier. Use when creating or changing .js, .mjs, .cjs, or .jsx files, Node.js scripts, or browser code. Don't use for TypeScript files (use writing-typescript-code) or for merely running an existing npm script without changing code.
---

# Writing JavaScript Code

Apply this procedure when creating, modifying, or reviewing JavaScript.

## Workflow

1. Inspect the target file, `package.json`, ESLint and Prettier configuration,
   and nearby code. Follow established project conventions, module system
   (ES modules or CommonJS), and supported runtimes unless they conflict with
   correctness or safety.
2. Read
   [references/google-javascript-style.md](references/google-javascript-style.md)
   before writing code. Apply its module, declaration, naming, formatting, and
   documentation rules.
3. Reuse the project's linter, formatter, bundler, and test runner. Do not add
   or replace tooling solely to enforce this skill. Before adding a dependency,
   apply the `checking-npm-packages` skill.
4. Make the smallest complete change. Keep functions focused, state local,
   errors explicit, and modules free of import-time side effects.
5. Validate every changed file from the project root with
   `scripts/validate-javascript.sh` in this skill's folder:

   ```bash
   bash <skill-folder>/scripts/validate-javascript.sh src/app.js src/util.mjs
   ```

   Pass all changed files in one invocation. The script checks syntax with
   `node --check`, then runs the project's ESLint and Prettier if installed; it
   never downloads tools. Then run the smallest existing test command that
   covers the change.
6. Fix every syntax, lint, formatting, or test finding caused by the change.
   Rerun validation until it succeeds. Keep `eslint-disable` comments scoped to
   one line and rule, with a reason.

## Required decisions

- Use ES modules with named exports in new code; avoid default exports. Keep
  CommonJS only where the project or runtime requires it.
- Declare with `const` by default and `let` when reassigned; never `var`.
  Declare one variable per statement.
- Use `lowerCamelCase` for functions, methods, variables, and parameters;
  `UpperCamelCase` for classes; `CONSTANT_CASE` for deeply immutable
  module-level constants.
- Use `===` and `!==`, except `== null` to test for both null and undefined.
- Throw `Error` objects (or subclasses), never strings. Handle or propagate
  every rejected promise; prefer `async`/`await` over raw `.then()` chains.
- Never use `eval`, `new Function(string)`, or `with`.
- Use arrow functions for nested callbacks and `for...of` for iteration.
- Add JSDoc to exported and non-obvious functions and classes, including
  `@param` and `@return` types when the project does not use TypeScript.

## Output expectations

Deliver JavaScript that matches the repository, follows the reference, and
passes available project checks. Report checks the validator skipped because a
tool was not installed. Preserve public behavior unless the request explicitly
changes it.
