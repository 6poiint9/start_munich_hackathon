# Google JavaScript Style Checklist

Use this checklist when writing or reviewing JavaScript. It paraphrases the
[Google JavaScript Style Guide](https://google.github.io/styleguide/jsguide.html).
Existing project style is a tie-breaker, not a reason to keep unsafe or
incorrect code.

## Source files

- Name files in lowercase, using `_` or `-` as the project does, with a `.js`
  (or `.mjs`/`.cjs`) extension.
- Encode files as UTF-8. Use escape sequences such as `\u00a0` for
  non-printing characters, not the raw character.
- Order a file as: license or `@fileoverview` comment, imports, then the
  implementation, with one blank line between sections.

## Modules, imports, and exports

- Use ES modules (`import`/`export`) in new code.
- Use named exports. Do not use default exports; they give no canonical name
  and make renames and searches harder.
- Do not export mutable bindings. Export functions or getters instead.
- Include the file extension in relative import paths (`./util.js`).
- Do not import the same file twice, and avoid circular imports.
- Keep import statements on one line, even when long.
- Name namespace imports in `lowerCamelCase` derived from the file name:
  `import * as fileUtils from './file_utils.js';`.

## Declarations

- Use `const` by default and `let` only when the binding is reassigned. Never
  use `var`.
- Declare one variable per statement, close to its first use.
- Use trailing commas in multi-line array and object literals.
- Do not use the `Array` or `Object` constructors; use literals.
- Do not mix quoted and unquoted keys in one object literal.
- Use shorthand properties and methods (`{foo, bar() {}}`) where they read
  well.
- Use destructuring for multiple values from one object or array. Give
  destructured parameters a default of `{}` when the whole object is optional.

## Functions and classes

- Prefer arrow functions for nested functions and callbacks; they keep `this`.
- Use default parameters instead of reassigning parameters. Put optional
  parameters last.
- Use rest parameters (`...args`) instead of `arguments`, and spread instead of
  `Function.prototype.apply`.
- Use `class` syntax. Do not manipulate prototypes directly.
- Do not add or remove properties after construction; define every field in
  the constructor or as a class field.
- Use getters and setters sparingly and without observable side effects.
- Override `toString` only without side effects.
- Do not extend or modify built-in prototypes.

## Strings and numbers

- Use single quotes for ordinary strings.
- Use template literals for interpolation and multi-line strings instead of
  concatenation.
- Do not use line continuations (`\` at the end of a line) in strings.
- Write numbers in decimal, `0x`, `0o`, or `0b` with lowercase prefixes. Never
  use legacy octal literals with a leading zero.

## Control flow

- Always use braces for `if`, `else`, `for`, `do`, and `while` bodies, except
  a single-line `if` with no `else` that fits entirely on one line.
- Use `for...of` for arrays and iterables. Use `for...in` only on dict-style
  objects, and guard with `Object.hasOwn`.
- Give every `switch` a `default` case, last. Do not fall through from a
  non-empty case without a `// fall through` comment.
- Use `===` and `!==`. The only exception is `x == null` to match null and
  undefined together.

## Errors and asynchronous code

- Throw `Error` or a subclass, never strings or plain objects.
- Do not leave a `catch` block empty without a comment explaining why the error
  is safe to ignore.
- Prefer `async`/`await`. Await or return every promise; do not leave floating
  promises.
- Reject promises with `Error` objects.

## Disallowed features

- `with`, `eval`, `new Function(string)`, and string arguments to
  `setTimeout` or `setInterval`.
- Relying on automatic semicolon insertion; end every statement with `;`.
- Wrapper objects for primitives (`new String`, `new Boolean`, `new Number`).
- Non-standard or proposal-stage features unless the toolchain targets them.
- `debugger` statements in committed code.

## Naming

- Use only ASCII letters, digits, and, in constants or test names, `_`.
- Use `UpperCamelCase` for classes, enums, typedefs, and interfaces.
- Use `lowerCamelCase` for functions, methods, parameters, local variables,
  and non-constant fields. Name methods with verbs (`sendMessage`).
- Use `CONSTANT_CASE` for module-level or static values that are deeply
  immutable. Local variables are never `CONSTANT_CASE`.
- Name enum values in `CONSTANT_CASE`.
- Treat acronyms as words: `loadHttpUrl`, not `loadHTTPURL`.
- Prefer descriptive names over abbreviations; avoid names that encode types.
- Mark non-public fields and methods with JSDoc `@private`, `@protected`, or
  `@package`. Names of `@private` members may end with a trailing underscore.
  The guide does not cover native `#private` members; use them only where the
  project already does.

## Formatting

- Indent with 2 spaces; never tabs. Continuation lines indent at least
  4 spaces.
- Keep lines at most 80 columns, except for imports, URLs, and long string
  literals that cannot be split.
- Use K&R braces: opening brace on the same line, closing brace on its own
  line, except before `else`, `catch`, or `while` of a `do`.
- Put one statement per line and end each with a semicolon.
- Put a single space after keywords (`if (`, `for (`) and around binary
  operators; no space inside parentheses or brackets.
- Do not align tokens horizontally with extra spaces.
- Let the project formatter decide details. When none is configured, Prettier
  with `singleQuote: true` and `printWidth: 80` matches this guide closely.

## JSDoc and comments

- Document every exported function, class, and non-trivial method with
  `/** ... */`.
- Start with a summary sentence. Describe behavior and constraints, not the
  implementation.
- Use `@param {Type} name Description.` and `@return {Type} Description.` in
  untyped code. Use `@throws` for documented exceptions.
- Use `@const`, `@private`, `@protected`, and `@override` where they add
  meaning or tooling uses them.
- Use `//` comments for implementation notes. Explain why, not what.
- Write `TODO` comments with an owner or issue reference:
  `// TODO(issue-123): Remove after migration.`.

## Review checklist

- New code uses ES modules and named exports.
- No `var`, `eval`, `with`, or string-based timers.
- Every promise is awaited, returned, or explicitly handled.
- Errors are `Error` instances; no empty catches without explanation.
- Exported APIs have JSDoc.
- Validator, lint, formatter, and tests pass, or skipped tools are reported.
