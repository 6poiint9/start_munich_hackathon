---
name: writing-dart-code
description: Writes, refactors, and reviews Dart and Flutter code using Effective Dart (Google's Dart style guide), including naming, imports, formatting, null safety, types, async code, documentation, and validation with dart format and dart analyze. Use when creating or changing .dart files, Flutter widgets, or Dart packages. Don't use for platform code inside ios/ or android/ folders, pubspec-only edits, or merely running an existing Flutter command without changing code.
---

# Writing Dart Code

Apply this procedure when creating, modifying, or reviewing Dart or Flutter
code.

## Workflow

1. Inspect the target file, `pubspec.yaml`, `analysis_options.yaml`, and
   nearby code. Follow established project conventions, the Dart SDK
   constraint, and the configured lint set (for example `flutter_lints` or
   `lints`) unless they conflict with correctness or safety.
2. Read [references/effective-dart.md](references/effective-dart.md) before
   writing code. Apply its naming, import, typing, async, and documentation
   rules. For Flutter architecture or widgets, also use the `flutter-expert`
   skill when available.
3. Reuse the project's analyzer configuration, formatter, and test runner. Do
   not add or replace tooling or lints solely to enforce this skill.
4. Make the smallest complete change. Keep widgets small and `const` where
   possible, state explicit, and nullability precise.
5. Validate every changed file from the package root with
   `scripts/validate-dart.sh` in this skill's folder:

   ```bash
   bash <skill-folder>/scripts/validate-dart.sh lib/main.dart lib/src/game.dart
   ```

   Pass all changed files in one invocation. The script checks
   `dart format` and runs `dart analyze --fatal-infos`. Then run the smallest
   existing test command (`flutter test test/game_test.dart` or `dart test`)
   that covers the change.
6. Fix every formatting, analyzer, or test finding caused by the change.
   Rerun validation until it succeeds. Scope `// ignore:` comments to one line
   and one lint, with a reason.

## Required decisions

- Use `UpperCamelCase` for types and extensions, `lowercase_with_underscores`
  for files, packages, directories, and import prefixes, and `lowerCamelCase`
  for everything else, including constants.
- Order imports as `dart:`, then `package:`, then relative, each section
  sorted alphabetically, with exports in a separate section after imports.
- Prefer `final` locals and fields, and `const` constructors and literals
  wherever the values are compile-time constants.
- Annotate public API types and function return types; avoid `dynamic`
  unless disabling static checking is the intent.
- Prefer `async`/`await` over raw `Future` chains. Catch with `on Type`
  clauses, use `rethrow`, and never catch `Error` subtypes.
- Do not use `new`, and do not initialize variables to `null` explicitly.
- Document public APIs with `///` comments that start with a single-sentence
  summary.

## Output expectations

Deliver Dart that matches the repository, follows the reference, and passes
`dart format` and the analyzer. Report checks the validator skipped because the
SDK was not installed. Preserve public behavior unless the request explicitly
changes it.
