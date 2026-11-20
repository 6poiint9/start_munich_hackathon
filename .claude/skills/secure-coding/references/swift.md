# Secure Coding: Swift, iOS, macOS

Rules that add to the general ones in `SKILL.md`. Based on OWASP MASVS/MASTG
and Apple's platform security guidance.

## Storage

- Store tokens, passwords, and keys in the Keychain with the narrowest
  accessibility that works, normally
  `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` (or
  `AfterFirstUnlockThisDeviceOnly` for background use). Never in
  `UserDefaults`, plist files, Core Data, or `@AppStorage`.
- Protect sensitive files with `.completeFileProtection` (or
  `.completeUnlessOpen`) when writing, and exclude them from backups
  (`isExcludedFromBackup`) when they must not leave the device.
- Keep private keys in the Secure Enclave (`SecureEnclave.P256`) where the
  feature allows, and gate high-value actions with `LAContext` plus a Keychain
  item bound to biometry (`.biometryCurrentSet`), not with an
  `evaluatePolicy` boolean alone.

## Network

- Keep App Transport Security on. Do not add `NSAllowsArbitraryLoads`; scope
  any exception to one domain with a reason.
- Never implement `urlSession(_:didReceive:completionHandler:)` to accept
  every certificate. For pinning, compare the server's public key (SPKI hash)
  with a pinned set that includes a backup key, or use
  `NSPinnedDomains` in Info.plist.
- Keep tokens out of URLs; send them in the `Authorization` header.

## Input from outside the app

- Treat URL schemes, universal links, `onOpenURL`, push payloads, pasteboard,
  shared files, and App Intents as untrusted. Parse with `URLComponents`,
  allowlist the host, path, and parameters, and require user confirmation
  before state-changing actions.
- Prefer universal links (verified domain) over custom URL schemes for
  anything carrying tokens; custom schemes can be claimed by other apps.
- Decode with `Codable` into types with validated ranges; avoid
  `NSKeyedUnarchiver` with untrusted data, or use
  `unarchivedObject(ofClass:from:)` with `requiresSecureCoding`.

## WebViews

- Use `WKWebView`, never `UIWebView`. Keep JavaScript off when not needed
  (`allowsContentJavaScript = false` on `WKWebpagePreferences`).
- Restrict navigation in `decidePolicyFor` to an allowlist of hosts, and
  validate every message in `WKScriptMessageHandler` as untrusted input.
- Do not load untrusted HTML with `loadHTMLString` and a privileged
  `baseURL`, or `loadFileURL` with broad read access.

## Cryptography and randomness

- Use CryptoKit: `AES.GCM` or `ChaChaPoly` for encryption, `SHA256`+ for
  hashing, `HMAC` for integrity, `SymmetricKey(size: .bits256)` for keys.
- Generate secrets with `SecRandomCopyBytes` or CryptoKit; never with
  `arc4random` for keys or `Int.random` for tokens.

## Code and logging

- Use `Logger` with privacy annotations; mark user data
  `privacy: .private` (the default for dynamic strings) and never log
  tokens. Remove `print` of sensitive values.
- Avoid force unwraps (`!`, `try!`) on data from outside the app; a crash on
  crafted input is a denial of service.
- Hide sensitive screens in the app switcher snapshot (overlay on
  `scenePhase` becoming `.inactive`) and set `isSecureTextEntry` on secret
  fields.
- Validate any `Process`/`NSTask` arguments on macOS as an argument array;
  never build a shell string.
