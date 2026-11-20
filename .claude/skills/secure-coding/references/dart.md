# Secure Coding: Dart, Flutter

Rules that add to the general ones in `SKILL.md`. Based on OWASP MASVS/MASTG
and Flutter's security guidance. Flutter apps also inherit the platform rules
in [swift.md](swift.md) (iOS runner, `Info.plist`) and
[kotlin.md](kotlin.md) (Android manifest, network security config).

## Secrets and builds

- Treat everything in the app as public: Dart constants, assets,
  `--dart-define` and `--dart-define-from-file` values, and `.env` files
  bundled as assets can all be extracted. Keep API keys with real power on a
  backend that the app calls with the user's own token.
- Build release apps with `--obfuscate --split-debug-info=<dir>` and keep the
  symbol files out of the repo; obfuscation slows reverse engineering but
  protects no secret.

## Storage

- Store tokens and keys with `flutter_secure_storage` (Keychain / Android
  Keystore), not `shared_preferences`, Hive/Isar without encryption, or plain
  files. On iOS set the accessibility to `first_unlock_this_device` or
  stricter.
- Use `path_provider`'s application support or documents folder for private
  files, never external or shared storage for sensitive data.
- Use `sqflite`/`drift` with `?` arguments or the query builder; never
  interpolate into SQL strings.

## Network

- Use `https` URIs only. Never set `HttpClient.badCertificateCallback` to
  return `true`, also not behind a debug flag that could ship.
- For pinning, use a `SecurityContext` with only the pinned certificates
  (`withTrustedRoots: false`) or a maintained pinning package, and include a
  backup pin.
- Send tokens in headers, not in query parameters.

## Input from outside the app

- Treat deep links (`go_router`, `app_links`, `uni_links`), push payloads,
  clipboard, shared files, and platform-channel messages as untrusted. Parse
  with `Uri.parse`, allowlist host, path, and parameters, and confirm
  state-changing actions with the user.
- Validate every value arriving over `MethodChannel`/`EventChannel` on both
  the Dart and the native side; the native side should not trust Dart input
  blindly and vice versa.
- Decode JSON into typed model classes (`json_serializable`, `freezed`) with
  validation; avoid passing `dynamic` maps through the app.

## WebView

- With `webview_flutter`, keep `JavaScriptMode.disabled` unless needed,
  restrict navigation in `NavigationDelegate.onNavigationRequest` to
  allowlisted hosts, and validate every `JavaScriptChannel` message.
- Open external links with `url_launcher` after checking the scheme
  (`https`, `mailto`), never `javascript:` or `file:`.

## Code and logging

- Use `Random.secure()` for tokens and IDs; `Random()` is predictable. Use
  `package:cryptography` or `pointycastle` with AES-GCM rather than custom
  schemes.
- Avoid `!` on data from outside the app; check and handle `null`.
- Do not `print` or `debugPrint` tokens or personal data; strip verbose
  logging from release builds (`kReleaseMode`).
- Hide sensitive screens from screenshots and the app switcher with a
  maintained plugin or platform code (`FLAG_SECURE` on Android, a privacy
  overlay on iOS).

## Dependencies

- Prefer packages with a verified publisher on pub.dev, high pub points, and
  recent releases; commit `pubspec.lock` for apps.
- Check `pubspec.lock` with `osv-scanner scan source -r .` (ecosystem `Pub`)
  when OSV-Scanner is installed, and review native code that plugins add.
