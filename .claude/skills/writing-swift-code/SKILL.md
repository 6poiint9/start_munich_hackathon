---
name: writing-swift-code
description: Writes, refactors, and reviews Swift using the Google Swift Style Guide, including naming, optionals, error handling, access control, formatting, documentation comments, and validation with swiftc and swift-format. Use when creating or changing .swift files for iOS, macOS, SwiftUI, UIKit, or Swift packages. Don't use for Objective-C, Xcode project settings, or merely running an existing build without changing code.
---

# Writing Swift Code

Apply this procedure when creating, modifying, or reviewing Swift.

## Workflow

1. Inspect the target file, `Package.swift` or Xcode project, any
   `.swift-format` or SwiftLint configuration, and nearby code. Follow
   established project conventions and the deployment target unless they
   conflict with correctness or safety.
2. Read [references/google-swift-style.md](references/google-swift-style.md)
   before writing code. Apply its naming, optional, error, and formatting
   rules. For SwiftUI or concurrency specifics, also use the
   `swiftui-expert-skill` or `swift-concurrency-expert` skill when available.
3. Reuse the project's formatter, linter, and test runner. Do not add or
   replace tooling solely to enforce this skill.
4. Make the smallest complete change. Prefer value types and immutable state,
   handle every failure path, and keep access levels as narrow as possible.
5. Validate every changed file with `scripts/validate-swift.sh` in this
   skill's folder:

   ```bash
   bash <skill-folder>/scripts/validate-swift.sh Sources/App/Model.swift
   ```

   Pass all changed files in one invocation. The script checks syntax with
   `swiftc -parse` and lints with `swift format lint --strict`, whose defaults
   match this guide (a project `.swift-format` file wins). Then run the
   smallest existing build or test command (`swift test`, `xcodebuild test`)
   that covers the change.
6. Fix every syntax, lint, build, or test finding caused by the change. Rerun
   validation until it succeeds.

## Required decisions

- Use `UpperCamelCase` for types and protocols and `lowerCamelCase` for
  everything else, including constants. Never use a `k` prefix or
  Hungarian notation.
- Prefer `let` over `var`, and structs and enums over classes unless identity
  or inheritance is needed. Mark classes `final` unless designed for
  subclassing.
- Never force unwrap (`!`), force cast (`as!`), or `try!` outside tests,
  unless a failure is a programmer error and a comment explains why. Unwrap
  with `if let` or `guard let`.
- Use `guard` for early exits so the main path is not nested.
- Model failures with `throws` and specific `Error` types; do not return
  sentinel values or silently swallow errors.
- Omit `self.` unless required, and omit redundant type annotations.
- Document public and non-obvious declarations with `///` comments that start
  with a single-sentence summary.

## Output expectations

Deliver Swift that matches the repository, follows the reference, and passes
available project checks. Report checks the validator skipped because a tool
was not installed. Preserve public behavior unless the request explicitly
changes it.
