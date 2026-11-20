# Google Swift Style Checklist

Use this checklist when writing or reviewing Swift. It paraphrases the
[Google Swift Style Guide](https://google.github.io/swift/), which builds on
Apple's API Design Guidelines. Existing project style is a tie-breaker, not a
reason to keep unsafe or incorrect code.

## Source files

- Name a file after its primary type (`Point.swift`). Name a file that adds a
  protocol conformance with a plus sign (`Point+Equatable.swift`); name other
  extension files by purpose (`String+Escaping.swift`).
- Use UTF-8 and only spaces for whitespace; never tabs.
- Write special characters with escape sequences (`\t`, `\n`, `\u{...}`)
  when the raw character would be invisible or ambiguous.
- Start the file with any license comment, then imports, then declarations.

## Imports

- Import whole modules, not individual declarations, unless importing the
  whole module would pull in unwanted symbols.
- Do not wrap import statements.
- Group imports, separated by one blank line, sorted lexicographically within
  each group: module imports, individual declaration imports, then
  `@testable` imports (tests only).
- Import only what the file uses; do not rely on transitive imports.

## Declarations and organization

- Put one primary type per file where practical; group related helpers next
  to it.
- Keep overloads of the same name together with no unrelated code between
  them.
- Use extensions to organize protocol conformances and related functionality,
  marked with `// MARK: -` comments when the file is long.
- Prefer `struct` and `enum` over `class`. Use classes for identity, reference
  semantics, or Objective-C interop, and mark them `final` unless designed for
  subclassing.
- Use a caseless `enum` as a namespace for static members.
- Declare the narrowest access level that works. Omitting the access level
  (`internal`) is fine; specify it explicitly on declarations that need it.
  Do not put an access modifier on an extension itself; put it on each member.

## Naming

- Follow Apple's API Design Guidelines: clarity at the point of use, names
  that read as English phrases, and argument labels that describe roles.
- Use `UpperCamelCase` for types and protocols; `lowerCamelCase` for
  functions, methods, properties, enum cases, and constants.
- Name global and static constants in `lowerCamelCase`. Do not use `k`
  prefixes, Hungarian notation, or `SCREAMING_SNAKE_CASE`.
- Do not use leading underscores to signal privacy; use access control.
- Name delegate methods with the delegate source as the first unlabeled
  argument (`func scrollViewDidScroll(_ scrollView: UIScrollView)`).
- Name static properties that return a shared instance `shared` or `default`,
  without the type name (`URLSession.shared`).

## Optionals and errors

- Do not force unwrap (`!`) or force cast (`as!`) in production code. They are
  acceptable only when failure is a programmer error that cannot be handled;
  add a comment explaining the invariant.
- Avoid implicitly unwrapped optionals (`T!`) except for properties that are
  guaranteed to be set before use, such as `@IBOutlet` or test fixtures set in
  `setUp`.
- Use `if let`, `guard let`, `??`, and optional chaining to handle `nil`.
- Use `throws` for recoverable errors. Define error types as `enum`s
  conforming to `Error` when callers need to distinguish cases.
- Do not use `try!` outside tests except for an invariant explained in a
  comment (for example, a literal regular expression). Tests may use `try` and
  let the framework report the failure.
- Do not use `Optional` to represent errors that carry information; throw.

## Control flow

- Use `guard` for early exits. The `else` body must exit the scope.
- Use `for ... where` instead of an `if` that wraps the entire loop body.
- Do not use `fallthrough` in `switch` when cases can share a pattern list
  (`case .a, .b:`).
- Put `let` and `var` on each bound name in patterns when it helps
  readability (`case .point(let x, let y)`).
- Write `switch` statements exhaustively without a `default` for enums the
  module owns, so new cases are caught by the compiler.

## Expressions and literals

- Use type shorthand: `[Element]`, `[Key: Value]`, `Wrapped?`.
- Omit redundant type annotations and redundant `self.`.
- Prefer trailing closure syntax only when a function has a single closure
  argument at the end.
- Use trailing commas in multi-line array and dictionary literals.
- Group digits in long numeric literals with underscores (`1_000_000`).
- Use the overflow operators (`&+`) only when wraparound is intended; default
  arithmetic traps on overflow.
- Do not define new operators unless the meaning is well established. When
  overloading existing operators, keep their usual meaning.

## Formatting

- Keep lines at most 100 columns, except for long URLs or literals that cannot
  be split.
- Indent with 2 spaces; continuation lines indent +2 from the start of the
  statement.
- Use K&R braces: opening brace on the same line, `else` and `catch` on the
  same line as the closing brace.
- Do not use semicolons.
- Put one statement per line.
- When a declaration or call does not fit, break after the opening
  parenthesis and put each argument on its own line, or follow the project
  formatter's choice.
- Put attributes such as `@available` or `@MainActor` on their own line
  before the declaration when they have arguments.
- Use `swift format` (bundled with Swift 6 toolchains) to apply formatting;
  its default configuration matches this guide.

## Documentation comments

- Use `///` for documentation. Do not use `/** */` blocks.
- Start with a single-sentence summary that is a sentence fragment ending in a
  period.
- Document parameters with `- Parameter name:` or a `- Parameters:` list, plus
  `- Returns:` and `- Throws:` where they apply.
- Document every `public` and `open` declaration, and any `internal` one that
  is not self-explanatory.
- Use `//` for implementation comments, explaining why rather than what.

## Review checklist

- No force unwraps, force casts, or `try!` in production code without an
  invariant comment.
- Classes are `final` unless designed for inheritance; value types preferred.
- Constants are `lowerCamelCase` with no prefixes.
- Imports are grouped, sorted, and whole-module.
- `swiftc -parse`, `swift format lint`, build, and tests pass, or skipped
  tools are reported.
