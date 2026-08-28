import 'auth_session.dart';

/// Persistence boundary. Mobile apps should back this with Keychain/Keystore.
abstract interface class TokenStore {
  Future<AuthSession?> read();

  Future<void> write(AuthSession session);

  Future<void> delete();
}

/// Test/demo store. Do not use this as durable production storage.
final class MemoryTokenStore implements TokenStore {
  AuthSession? _session;

  @override
  Future<void> delete() async => _session = null;

  @override
  Future<AuthSession?> read() async => _session;

  @override
  Future<void> write(AuthSession session) async => _session = session;
}
