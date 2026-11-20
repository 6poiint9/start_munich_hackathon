---
name: secure-coding
description: Writes and reviews code to resist attack, covering untrusted input, injection, secrets, authentication, cryptography, storage, transport, and dependencies, with rules for JavaScript/TypeScript, Swift/iOS, Kotlin/Android, and Dart/Flutter. Use when code handles user or network input, credentials, files, persistence, permissions, or crypto, and for security reviews or hardening.
---

# Secure Coding

## Workflow

1. Map the **trust boundaries** the change touches: where untrusted data
   enters (user input, network replies, files, deep links, intents, IPC,
   environment, other apps) and where it lands (queries, shells, HTML, file
   paths, logs, storage, other services).
2. Read the language reference before writing code, and apply every rule in it
   that touches those boundaries:

   | Code | Reference |
   |---|---|
   | JavaScript, TypeScript, Node.js | [references/javascript.md](references/javascript.md) |
   | Swift, iOS, macOS | [references/swift.md](references/swift.md) |
   | Kotlin, Android, JVM | [references/kotlin.md](references/kotlin.md) |
   | Dart, Flutter | [references/dart.md](references/dart.md) |

   Other languages: apply the rules below plus the language's OWASP cheat sheet.
3. Write the change so each boundary is guarded by the rules below.
4. For dependency changes, check them before installing: npm with the
   `checking-npm-packages` skill; Swift, Gradle, and pub lockfiles
   (`Package.resolved`, `gradle.lockfile`, `pubspec.lock`) with
   `osv-scanner scan source -r .` when OSV-Scanner is installed.
5. Review the final diff boundary by boundary. Done when every boundary from
   step 1 is either guarded or listed in the report as a residual risk with
   its reason.

## Rules for every language

**Input**
- Validate untrusted input at the boundary against an allowlist: type,
  length, range, format, and character set. Reject what fails; do not repair
  it.
- Parse into typed structures (schemas, `Codable`, data classes) and work with
  the parsed value, never the raw string.

**Injection**
- Build queries with parameter binding, commands as argument arrays without a
  shell, and HTML through context-aware escaping or the framework's safe
  rendering. Never assemble them by string concatenation of untrusted data.
- Resolve file paths against a fixed base folder and verify the canonical
  result is still inside it.
- Fetch user-supplied URLs only after checking scheme and host against an
  allowlist (SSRF), and refuse redirects to other hosts.
- Deserialize untrusted data only with data-only formats (JSON) into explicit
  types.

**Secrets**
- Keep secrets out of source, client bundles, mobile apps, logs, URLs, and
  error messages. Load them from the environment or a secret manager on a
  server; a value shipped in an app is public.
- Add new secret files to `.gitignore` before creating them, and provide an
  `.env.example` with placeholders.

**Authentication and authorization**
- Enforce authorization on the server for every request and object (check the
  caller owns the record), never only in the client UI.
- Use the platform or framework's vetted auth (OAuth 2.0 with PKCE for apps,
  established session libraries). Store tokens in the platform's secure
  storage. Expire and rotate them.
- Compare secrets and tokens in constant time.

**Cryptography**
- Use the platform's high-level crypto APIs with modern defaults: AES-GCM or
  ChaCha20-Poly1305, SHA-256 or better, Argon2id/scrypt/bcrypt for passwords,
  and a CSPRNG for every token, nonce, and ID that must be unguessable.
- Never write your own crypto, reuse a nonce, or use MD5, SHA-1, DES, ECB, or
  non-cryptographic random generators for security.

**Transport**
- Use HTTPS/TLS everywhere with full certificate validation. Never ship code
  that disables certificate or hostname checks, including "for debug" flags.

**Errors and logging**
- Fail closed: on an error in a security check, deny.
- Show users generic errors; log details on the server side. Log security
  events (login, permission changes, failures) without passwords, tokens,
  session IDs, or personal data.

**Dependencies**
- Add only maintained, widely used packages at exact, checked versions; commit
  lockfiles; prefer the standard library when it suffices.

## Output expectations

Deliver code that guards every trust boundary it touches, and report residual
risks and any security trade-off the user must decide (for example certificate
pinning versus rotation effort). Flag pre-existing vulnerabilities seen in
touched code without silently fixing unrelated ones.
