# Secure Coding: Kotlin, Android, JVM

Rules that add to the general ones in `SKILL.md`. Based on OWASP MASVS/MASTG,
Android's app security best practices, and the OWASP Java cheat sheets.

## Android components and intents

- Set `android:exported="false"` on every activity, service, receiver, and
  provider that other apps do not need. For exported ones, require a
  signature-level permission or validate every extra as untrusted input.
- Use explicit intents for internal communication. Never forward a received
  `Intent` (intent redirection) or launch a `Uri` from extras without
  allowlisting its target.
- Create `PendingIntent`s with `FLAG_IMMUTABLE` and an explicit target
  component.
- Register runtime receivers with `RECEIVER_NOT_EXPORTED` unless they must
  receive other apps' broadcasts.
- Share files through `FileProvider` with narrow `paths` and temporary
  `FLAG_GRANT_READ_URI_PERMISSION`, never `file://` URIs or world-readable
  files.
- Verify App Links (`android:autoVerify="true"`) for links that carry tokens;
  treat deep-link parameters as untrusted.

## Storage

- Keep secrets in app-private storage encrypted with keys from the Android
  Keystore (`KeyGenParameterSpec`, `setUserAuthenticationRequired` for
  high-value keys). Use Tink or Keystore-backed AES-GCM; Jetpack Security
  `EncryptedSharedPreferences` is deprecated.
- Never store secrets on external storage, in logs, or in plain
  `SharedPreferences`/DataStore.
- Set `android:allowBackup="false"` or exclude sensitive files with
  `dataExtractionRules`/`fullBackupContent`.
- Use Room/SQLite with bound arguments (`@Query` parameters, `?`
  placeholders); never build SQL with string templates (`"... $input"`).

## Network

- Keep cleartext traffic off (`android:usesCleartextTraffic="false"`, the
  default from API 28) and configure trust in
  `network_security_config.xml`; pin with `<pin-set>` including a backup
  pin and an expiration, or OkHttp `CertificatePinner`.
- Never install a `TrustManager` or `HostnameVerifier` that accepts
  everything, not even in debug builds; use `debug-overrides` in the network
  security config instead.

## WebView

- Keep `javaScriptEnabled` off unless needed, and
  `allowFileAccess`/`allowContentAccess` off.
- Expose `@JavascriptInterface` objects only to pages from an allowlisted
  origin, and validate every call's arguments. Prefer
  `WebViewCompat.addWebMessageListener` with allowed origin rules.
- Restrict navigation in `shouldOverrideUrlLoading` to allowlisted hosts.

## Code, crypto, and logging

- Avoid `!!` on data from outside the app; parse into data classes with
  validation (kotlinx.serialization with explicit types).
- Use `SecureRandom` for tokens, `Cipher.getInstance("AES/GCM/NoPadding")`
  with a fresh 12-byte IV per message, and never `ECB`, `DES`, or a hard-coded
  key or IV.
- Strip sensitive logs from release builds (no tokens or personal data in
  `Log`/Timber), and enable R8 minification for release.
- Set `FLAG_SECURE` on windows showing secrets, and use
  `InputType.TYPE_TEXT_VARIATION_PASSWORD` for secret fields.
- Request the minimum permissions; prefer system pickers (Photo Picker,
  Storage Access Framework) over broad storage permissions.

## Server-side Kotlin (Spring, Ktor, Quarkus)

- Bind parameters in JPA/JDBC/Exposed queries; never concatenate JPQL or SQL.
- Disable polymorphic default typing in Jackson (`activateDefaultTyping`) and
  never use Java serialization (`ObjectInputStream`) on untrusted data.
- Disable external entities in XML parsers (XXE).
- Use the framework's security module for authentication, CSRF, CORS, and
  method-level authorization rather than hand-written filters.
