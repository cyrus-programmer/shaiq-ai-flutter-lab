import 'auth_failure.dart';
import 'session_manager.dart';

typedef ProtectedCall<T> = Future<T> Function(String accessToken);

/// Supplies a valid token and retries exactly once after an unauthorized response.
final class AuthorizedExecutor {
  const AuthorizedExecutor(this._sessions);

  final SessionManager _sessions;

  Future<T> run<T>(ProtectedCall<T> call) async {
    var token = await _sessions.authorizedToken();
    try {
      return await call(token);
    } on UnauthorizedException {
      token = await _sessions.forceRefresh();
      return call(token);
    }
  }
}
