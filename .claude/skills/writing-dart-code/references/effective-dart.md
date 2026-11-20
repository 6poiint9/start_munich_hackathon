# Effective Dart Checklist

Use this checklist when writing or reviewing Dart or Flutter code. It
paraphrases [Effective Dart](https://dart.dev/effective-dart), Google's style
and usage guide for Dart. Existing project style is a tie-breaker, not a
reason to keep unsafe or incorrect code.

## Naming

- Use `UpperCamelCase` for classes, enums, typedefs, type parameters, and
  extensions.
- Use `lowercase_with_underscores` for packages, directories, source files,
  and import prefixes (`import 'dart:math' as math;`).
- Use `lowerCamelCase` for variables, parameters, members, named parameters,
  and constants, including enum values. Do not use `SCREAMING_CAPS` in new
  code unless matching an existing file.
- Capitalize acronyms and abbreviations longer than two letters like words
  (`HttpRequest`, `Id`, but `IO`, `UI`).
- Use a leading `_` only for library-private identifiers, never for locals or
  parameters.
- Do not use prefix letters (`kDefaultTimeout`, `mCount`); Flutter's own `k`
  constants are a legacy exception.
- Name unused callback parameters `_` (a wildcard on Dart 3.7+; use `_`,
  `__`, and so on for several parameters on earlier versions).
- Name things consistently, put the most descriptive noun last, and make code
  read like a sentence (`list.isEmpty`, `errors.add(error)`).
- Name booleans as non-imperative verb phrases or adjectives (`isEnabled`,
  `hasElements`, `canClose`).

## Imports and exports

- Order directives: `dart:` imports, then `package:` imports, then relative
  imports, with a blank line between sections.
- Sort each section alphabetically.
- Put `export` directives in their own section after all imports.
- Do not import from another package's `src/` directory.
- Do not let import paths reach into or out of `lib/`. Within your own
  package's `lib/`, prefer relative imports or `package:` imports
  consistently, as the project does.
- Use `show` or `hide` only when it resolves a real conflict or clarifies
  usage.

## Formatting

- Format every file with `dart format`; do not hand-format.
- Keep lines at most 80 characters (the formatter default), unless the
  project configures `page_width`.
- Use curly braces for all flow control statements. A single-line `if` with
  no `else` that fits on one line may omit them.
- Use trailing commas in Flutter widget argument lists so the formatter
  places one argument per line.

## Types and null safety

- Annotate types of fields and top-level variables when the type is not
  obvious from the initializer.
- Annotate return types and parameter types on function declarations; do not
  annotate parameters of function literals passed as arguments.
- Do not redundantly annotate initialized local variables.
- Avoid `dynamic` unless you want to disable static checking. Use `Object?`
  when any value is accepted.
- Do not explicitly initialize variables to `null`.
- Avoid `late` when callers need to know whether the value is initialized; use
  a nullable type instead.
- Prefer type promotion or null-check patterns (`if (x case final x?)`) over
  `!`. Use `!` only when a comment or the surrounding code makes the
  invariant obvious.
- Use `??` and `?.` to handle null, and `?? false` to convert a nullable
  boolean.
- Use `Future<void>` as the return type of asynchronous functions that
  produce no value.
- Prefer generic function type syntax (`void Function(int)`) and avoid
  `typedef` for simple function types.

## Classes and members

- Prefer `final` for fields and top-level variables that never change.
- Use `const` constructors and `const` literals whenever possible; in
  Flutter, mark widgets and their constructor calls `const`.
- Use initializing formals (`this.name`) and `super.key` parameters.
- Do not use `new`, and do not repeat `const` inside a `const` context.
- Make declarations private unless they need to be public.
- Avoid classes with only static members; use top-level functions and
  constants.
- Use getters for property-like operations with no side effects, and methods
  for work that is expensive or has side effects.
- Override `hashCode` whenever you override `==`, and make `==` obey equality
  rules. Prefer records or code generation for value types.
- Use `class` modifiers (`final`, `base`, `interface`, `sealed`) to state how
  a class may be extended or implemented.

## Collections and functions

- Use collection literals (`[]`, `{}`), and `isEmpty`/`isNotEmpty` instead of
  `length == 0`.
- Use collection `if`, `for`, and spreads instead of building lists
  imperatively.
- Use `whereType<T>()` instead of `where` plus `cast`; avoid `cast()` when a
  typed collection can be created directly.
- Use a function declaration, not a variable holding a lambda, to bind a
  function to a name. Use tear-offs (`list.forEach(print)`) instead of
  wrapping lambdas.
- Use `=>` for members whose body is a single expression.
- Use string interpolation instead of `+`, and omit braces around simple
  identifiers (`'Hello, $name'`).

## Errors and asynchrony

- Avoid `catch` without an `on` clause. If you must catch everything, do not
  discard the error silently.
- Do not catch `Error` or its subtypes; they signal programming bugs.
- Use `rethrow` to rethrow a caught exception so the stack trace is kept.
- Throw `Error` subtypes only for programming errors and `Exception` types for
  recoverable failures.
- Prefer `async`/`await` over `then` chains. Do not mark a function `async`
  when it has no use for it.
- Avoid using `Completer` directly; wrap callback APIs only when necessary.
- Await or explicitly ignore (`unawaited(...)`) every future.
- In Flutter, check `context.mounted` after an `await` before using a
  `BuildContext`.

## Documentation

- Use `///` doc comments for members and types; do not use `/** */`.
- Start with a single-sentence summary ending in a period, followed by a blank
  line before any detail.
- Start function and method comments with third-person verbs ("Returns ...")
  and variable or property comments with noun phrases.
- Refer to identifiers in square brackets (`[Widget]`, `[build]`).
- Document public APIs; avoid redundant comments that repeat the name.
- Use `//` for implementation comments explaining why.

## Review checklist

- `dart format` makes no changes and `dart analyze` reports no issues.
- Imports are ordered `dart:`, `package:`, relative, each sorted.
- No `new`, `dynamic` without reason, or unexplained `!`.
- Widgets and literals are `const` where possible.
- Catches use `on` clauses and `rethrow`; no `Error` catching.
- Tests pass, or skipped tools are reported.
