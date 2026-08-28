import 'auth_session.dart';

/// Backend boundary. Implement this with Dio, http, Firebase, Supabase, or an SDK.
abstract interface class AuthApi {
  Future<AuthSession> signIn({required String email, required String password});

  Future<AuthSession> refresh(String refreshToken);

  Future<void> revoke(String refreshToken);
}
