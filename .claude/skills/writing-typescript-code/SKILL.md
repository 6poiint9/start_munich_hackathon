---
name: writing-typescript-code
description: Writes, refactors, and reviews TypeScript using the Google TypeScript Style Guide, including type safety, modules, naming, classes, error handling, and validation with tsc, ESLint, and Prettier. Use when creating or changing .ts, .tsx, .mts, or .cts files, type declarations, or tsconfig-based projects. Don't use for plain JavaScript (use writing-javascript-code) or for merely running an existing npm script without changing code.
---

# Writing TypeScript Code

Apply this procedure when creating, modifying, or reviewing TypeScript.

## Workflow

1. Inspect the target file, `tsconfig.json`, `package.json`, ESLint and
   Prettier configuration, and nearby code. Follow established project
   conventions, compiler options, and runtimes unless they conflict with
   correctness or safety.
2. Read
   [references/google-typescript-style.md](references/google-typescript-style.md)
   before writing code. Apply its type, module, naming, and class rules.
3. Reuse the project's compiler settings, linter, formatter, and test runner.
   Do not loosen `tsconfig.json` strictness or add tooling solely to enforce
   this skill. Before adding a dependency, apply the `checking-npm-packages`
   skill.
4. Make the smallest complete change. Model data with precise types, narrow
   unknown input at boundaries, and keep modules free of import-time side
   effects.
5. Validate every changed file from the project root with
   `scripts/validate-typescript.sh` in this skill's folder:

   ```bash
   bash <skill-folder>/scripts/validate-typescript.sh src/app.ts src/view.tsx
   ```

   Pass all changed files in one invocation. The script runs the project's
   `tsc --noEmit`, then ESLint and Prettier if installed; it never downloads
   tools. Then run the smallest existing test command that covers the change.
6. Fix every type, lint, formatting, or test finding caused by the change.
   Rerun validation until it succeeds.

## Required decisions

- Use named exports; never default exports or `namespace`.
- Use `unknown` instead of `any`, and narrow it with type guards. Treat `any`
  as a last resort with a comment explaining why.
- Never use `@ts-ignore`, `@ts-expect-error` (outside tests), or
  `@ts-nocheck`. Fix the type error instead.
- Avoid type assertions (`as`) and non-null assertions (`!`); prefer runtime
  checks that narrow the type.
- Use `interface` for object shapes and `type` for unions, intersections, and
  mapped types.
- Use TypeScript `private`/`protected` modifiers, not `#private` fields; mark
  never-reassigned properties `readonly`.
- Use `lowerCamelCase` for values, `UpperCamelCase` for types, and never a
  leading or trailing `_` on identifiers.
- Use `import type` for imports used only as types.

## Output expectations

Deliver TypeScript that matches the repository, follows the reference, and
compiles under the project's strictness. Report checks the validator skipped
because a tool was not installed. Preserve public behavior unless the request
explicitly changes it.
