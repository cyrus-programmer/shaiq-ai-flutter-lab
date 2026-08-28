enum AuthFailureKind {
  invalidCredentials,
  expiredSession,
  network,
  server,
  malformedSession,
  unknown,
}

/// Safe, UI-facing failure. It intentionally contains no tokens or raw payloads.
final class AuthFailure {
  const AuthFailure(this.kind, this.message, {this.retryable = false});

  final AuthFailureKind kind;
  final String message;
  final bool retryable;
}

/// Typed error expected from an [AuthApi] implementation.
final class AuthApiException implements Exception {
  const AuthApiException({
    required this.kind,
    required this.safeMessage,
    this.retryable = false,
  });

  final AuthFailureKind kind;
  final String safeMessage;
  final bool retryable;

  AuthFailure toFailure() =>
      AuthFailure(kind, safeMessage, retryable: retryable);
}

/// Signals a 401/403 from an authenticated application request.
final class UnauthorizedException implements Exception {
  const UnauthorizedException();
}
