# Google TypeScript Style Checklist

Use this checklist when writing or reviewing TypeScript. It paraphrases the
[Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html),
which builds on the JavaScript guide. Existing project style is a
tie-breaker, not a reason to keep unsafe or incorrect code.

## Source files and modules

- Use ES modules. Do not use `namespace` or `/// <reference>` for code
  organization; the file is the namespace.
- Use named exports. Do not use default exports.
- Do not export mutable bindings (`export let`). Export a getter function or
  a `const` object instead.
- Export only what other modules use; keep everything else module-private.
- Do not create container classes with only static members; export
  functions and constants directly.
- Use relative imports (`./foo`) within a project. Prefer namespace imports
  (`import * as foo`) for large APIs and named imports for a few symbols.
- Use `import type {Foo}` when a symbol is only used as a type, and
  `export type` when re-exporting types.
- Do not use `require` or `import x = require(...)`.

## Type system

- Rely on inference for trivially typed locals (`const n = 5;`). Annotate
  function return types and exported APIs when the type is not obvious.
- Use `unknown` instead of `any`. Narrow `unknown` with `typeof`,
  `instanceof`, or user-defined type guards.
- When `any` is unavoidable, scope it narrowly and add a comment explaining
  why.
- Do not use `{}` as a type; use `unknown`, `object`, or
  `Record<string, T>`.
- Use `interface` to declare object types and `type` for unions,
  intersections, tuples, and mapped or conditional types.
- Write arrays of simple types as `T[]` or `readonly T[]`. Use `Array<T>` for
  complex element types such as unions or object literals.
- Prefer optional fields and parameters (`?`) over `| undefined`. Do not
  include `| null` or `| undefined` in type aliases; add them at use sites.
- Use the lowercase primitive types (`string`, `number`, `boolean`), never
  wrapper types (`String`, `Number`, `Boolean`).
- Do not use `const enum`; use a plain `enum` or a union of string literals.
- Use index signatures or `Map`/`Set` for dynamic keys; never access declared
  properties with string indexing to bypass visibility.
- Use mapped and conditional types sparingly; prefer a plain interface when it
  reads more clearly.

## Assertions and suppressions

- Avoid type assertions (`x as Foo`) and non-null assertions (`x!`). Prefer
  runtime checks that let the compiler narrow the type. When an assertion is
  justified, add a comment explaining why it is safe.
- Use `as` syntax, never angle-bracket assertions (`<Foo>x`).
- When converting between unrelated types, go through `unknown`:
  `x as unknown as Foo`, and comment why.
- Type object literals with an annotation (`const foo: Foo = {...}`), not an
  assertion (`{...} as Foo`), so the compiler checks for missing fields.
- Do not use `@ts-ignore`, `@ts-nocheck`, or `@ts-expect-error`. Tests may use
  `@ts-expect-error` to check that invalid usage fails to compile, with a
  comment.

## Classes

- Do not use `#private` fields; use the `private` or `protected` modifier.
- Do not write `public` except on non-readonly public parameter properties.
- Mark properties that are never reassigned outside the constructor
  `readonly`.
- Use parameter properties (`constructor(private readonly service: Service)`)
  instead of assigning constructor parameters to fields by hand.
- Initialize fields where they are declared when possible.
- Do not use getters and setters that only pass through to a private field;
  make the field public instead.
- Do not use `Object.defineProperty` for accessors.

## Values and control flow

- Use `const` and `let`; never `var`.
- Use `===` and `!==`; `== null` is allowed to match null and undefined.
- Do not use `for...in` on arrays. Use `for...of`, or `Object.keys`/
  `Object.entries` for objects.
- Throw only `Error` objects. Type `catch` variables as `unknown` and narrow
  them before use.
- Await or return every promise; do not leave floating promises.
- Do not use `debugger`, `with`, `eval`, or `Function(string)`.
- Do not modify built-in prototypes.

## Naming

- Use `UpperCamelCase` for classes, interfaces, types, enums, decorators, and
  type parameters.
- Use `lowerCamelCase` for variables, parameters, functions, methods,
  properties, and module aliases.
- Use `CONSTANT_CASE` for global constants and enum values.
- Treat acronyms as words: `loadHttpUrl`, not `loadHTTPURL`.
- Do not use `_` as a prefix or suffix, including for private members or
  unused parameters.
- Do not prefix interfaces with `I` or suffix observables with `$` unless the
  project already does.
- Do not encode type information in names (Hungarian notation).
- Use descriptive names; abbreviate only when widely understood.

## Comments and documentation

- Use `/** JSDoc */` for documentation that users of the API read, and `//`
  for implementation notes.
- Document exported symbols and non-obvious members.
- Do not repeat types in JSDoc (`@param {string}`); TypeScript already has
  them. Add `@param` and `@return` only when they explain something.
- Put JSDoc before decorators, not between a decorator and its target.

## Formatting

- Follow the JavaScript guide: 2-space indent, 80 columns, semicolons, single
  quotes, braces for all control blocks.
- Let the project formatter decide details. Google's own tooling is `gts`
  (ESLint and Prettier preset); any configured formatter wins.

## Review checklist

- No `any`, `@ts-ignore`, `namespace`, default exports, or `const enum`.
- Assertions and non-null assertions are absent or justified in a comment.
- No `_`-prefixed identifiers and no `#private` fields.
- `import type` is used for type-only imports.
- `tsc --noEmit`, lint, formatter, and tests pass, or skipped tools are
  reported.
