# Flutter Auth Session Kit

A small, production-minded session orchestration package for Flutter. It solves
the concurrency and lifecycle problems around access-token expiry while leaving
HTTP, identity-provider, and secure-storage choices at the application boundary.

## Implemented behavior

- Restore a saved session at startup.
- Refresh proactively within a configurable expiry skew.
- Coalesce simultaneous refresh requests into one backend call.
- Prevent a late refresh response from signing a user back in after logout.
- Separate retryable network failures from permanent/expired-session failures.
- Delete credentials after a permanent refresh failure.
- Complete local logout even when best-effort server revocation is unavailable.
- Retry an authenticated application call exactly once after a 401/403 signal.
- Expose immutable session state through `ChangeNotifier` without a state-management
  package dependency.
- Keep raw backend errors and tokens out of UI-facing failure objects.

This package does not implement OAuth, biometrics, certificate pinning, HTTP calls,
or secure storage. Those concerns vary by backend and threat model, so they are
represented by narrow `AuthApi` and `TokenStore` interfaces.

## Architecture

```text
Flutter UI / state-management adapter
              |
       SessionManager ---- AuthorizedExecutor
          /       \
     AuthApi     TokenStore
       |             |
your backend    Keychain / Keystore adapter
```

`SessionManager` owns state transitions and refresh concurrency. `AuthApi` maps
your backend SDK or HTTP client to sign-in, refresh, and revoke operations.
`TokenStore` should be implemented with platform-protected storage in production.

## Quick start

Copy the package into a workspace or reference it with a path dependency:

```yaml
dependencies:
  flutter_auth_session_kit:
    path: ../flutter-auth-session-kit
```

Implement the two boundaries:

```dart
final sessions = SessionManager(
  api: MyAuthApi(httpClient),
  store: MySecureTokenStore(),
  refreshSkew: const Duration(seconds: 30),
);

await sessions.restore();
```

Use `sessions.state` to drive navigation. A signed-in state contains an
`AuthSession`; a failure contains a safe `AuthFailure` suitable for display.

For protected calls:

```dart
final executor = AuthorizedExecutor(sessions);
final profile = await executor.run(
  (token) => profileApi.fetch(bearerToken: token),
);
```

Your API adapter should throw `UnauthorizedException` only for an authenticated
request rejected as unauthorized. The executor forces one refresh and retries
once, avoiding infinite retry loops.

## Secure storage adapter

`MemoryTokenStore` exists only for tests and the example. A production adapter
should serialize `AuthSession.encode()` into Keychain/Keystore-backed storage and
convert corrupt persisted data into `FormatException`. Do not store tokens in
SharedPreferences, plain files, analytics events, crash breadcrumbs, or logs.

## Validation

```bash
flutter pub get
flutter analyze
flutter test

cd example
flutter pub get
flutter build web
```

The tests cover serialization, restore, proactive refresh, concurrent single-flight
refresh, stale responses after logout, permanent and transient failures, sign-in
persistence, one-time unauthorized retry, and offline revocation.

## Production checklist

- Use short-lived access tokens and rotating, server-revocable refresh tokens.
- Back `TokenStore` with Keychain/Keystore using an approved package or native code.
- Redact authorization headers from network and crash logging.
- Apply certificate/network controls appropriate to the application's risk level.
- Revoke all server-side sessions after password or account-security changes.
- Test app resume, clock skew, offline mode, account deletion, and multi-device logout.
- Keep provider client secrets on a server, never in the Flutter bundle.

## Honest limitations

- Refresh retry/backoff is intentionally left to the `AuthApi` implementation; the
  manager coalesces calls but does not hide transport policy.
- The package keeps the last session in memory after a retryable refresh error so the
  user can retry. Callers must not treat that expired access token as authorized.
- Server revocation is best effort during logout. Production backends should also
  enforce refresh-token rotation and expiration.
- No real identity provider or secure-storage plugin is connected in the example.
