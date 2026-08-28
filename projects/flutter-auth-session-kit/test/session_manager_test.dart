import 'dart:async';

import 'package:flutter_auth_session_kit/flutter_auth_session_kit.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final now = DateTime.utc(2026, 8, 28, 3);
  AuthSession session(String token, {Duration lifetime = const Duration(hours: 1)}) =>
      AuthSession(
        accessToken: token,
        refreshToken: 'refresh-$token',
        expiresAt: now.add(lifetime),
        userId: 'user-1',
      );

  test('session encoding round-trips without changing UTC expiry', () {
    final original = session('access');
    final decoded = AuthSession.decode(original.encode());
    expect(decoded.accessToken, original.accessToken);
    expect(decoded.expiresAt, original.expiresAt);
  });

  test('restore exposes an unexpired stored session', () async {
    final store = FakeStore(session('stored'));
    final manager = SessionManager(api: FakeApi(), store: store, clock: () => now);
    await manager.restore();
    expect(manager.state.status, SessionStatus.authenticated);
    expect(manager.state.session?.accessToken, 'stored');
  });

  test('restore refreshes a session inside the expiry skew', () async {
    final store = FakeStore(session('old', lifetime: const Duration(seconds: 10)));
    final api = FakeApi(refreshResult: session('new'));
    final manager = SessionManager(api: api, store: store, clock: () => now);
    await manager.restore();
    expect(api.refreshCalls, 1);
    expect(manager.state.session?.accessToken, 'new');
  });

  test('concurrent token requests share one refresh', () async {
    final refresh = Completer<AuthSession>();
    final api = FakeApi(refreshFuture: refresh.future);
    final manager = SessionManager(
      api: api,
      store: FakeStore(session('old')),
      clock: () => now,
    );
    await manager.restore();
    final first = manager.forceRefresh();
    final second = manager.forceRefresh();
    refresh.complete(session('new'));
    expect(await Future.wait(<Future<String>>[first, second]), <String>['new', 'new']);
    expect(api.refreshCalls, 1);
  });

  test('logout prevents an in-flight refresh from restoring a session', () async {
    final refresh = Completer<AuthSession>();
    final store = FakeStore(session('old'));
    final manager = SessionManager(
      api: FakeApi(refreshFuture: refresh.future),
      store: store,
      clock: () => now,
    );
    await manager.restore();
    final pending = manager.forceRefresh();
    await manager.logout();
    refresh.complete(session('late'));
    await expectLater(pending, throwsA(isA<UnauthorizedException>()));
    expect(manager.state.status, SessionStatus.unauthenticated);
    expect(store.value, isNull);
  });

  test('permanent refresh failure clears saved credentials', () async {
    final store = FakeStore(session('old', lifetime: Duration.zero));
    final api = FakeApi(refreshError: const AuthApiException(
      kind: AuthFailureKind.expiredSession,
      safeMessage: 'Please sign in again.',
    ));
    final manager = SessionManager(api: api, store: store, clock: () => now);
    await manager.restore();
    expect(manager.state.status, SessionStatus.failure);
    expect(manager.state.session, isNull);
    expect(store.value, isNull);
  });

  test('retryable refresh failure retains the session for retry', () async {
    final stored = session('old', lifetime: Duration.zero);
    final store = FakeStore(stored);
    final api = FakeApi(refreshError: const AuthApiException(
      kind: AuthFailureKind.network,
      safeMessage: 'Connection unavailable.',
      retryable: true,
    ));
    final manager = SessionManager(api: api, store: store, clock: () => now);
    await manager.restore();
    expect(manager.state.status, SessionStatus.failure);
    expect(manager.state.failure?.retryable, isTrue);
    expect(manager.state.session, same(stored));
    expect(store.value, same(stored));
  });

  test('sign in persists the returned session', () async {
    final created = session('signed-in');
    final store = FakeStore();
    final manager = SessionManager(
      api: FakeApi(signInResult: created),
      store: store,
      clock: () => now,
    );
    await manager.signIn(email: 'user@example.com', password: 'not-logged');
    expect(store.value, same(created));
    expect(manager.state.status, SessionStatus.authenticated);
  });

  test('authorized executor retries once with a refreshed token', () async {
    final api = FakeApi(refreshResult: session('fresh'));
    final manager = SessionManager(
      api: api,
      store: FakeStore(session('current')),
      clock: () => now,
    );
    await manager.restore();
    var calls = 0;
    final result = await AuthorizedExecutor(manager).run<String>((token) async {
      calls++;
      if (calls == 1) throw const UnauthorizedException();
      return token;
    });
    expect(result, 'fresh');
    expect(calls, 2);
    expect(api.refreshCalls, 1);
  });

  test('logout succeeds locally even when revocation fails', () async {
    final store = FakeStore(session('current'));
    final manager = SessionManager(
      api: FakeApi(revokeError: StateError('offline')),
      store: store,
      clock: () => now,
    );
    await manager.restore();
    await manager.logout();
    expect(store.value, isNull);
    expect(manager.state.status, SessionStatus.unauthenticated);
  });
}

final class FakeStore implements TokenStore {
  FakeStore([this.value]);
  AuthSession? value;

  @override
  Future<void> delete() async => value = null;

  @override
  Future<AuthSession?> read() async => value;

  @override
  Future<void> write(AuthSession session) async => value = session;
}

final class FakeApi implements AuthApi {
  FakeApi({
    this.signInResult,
    this.refreshResult,
    this.refreshFuture,
    this.refreshError,
    this.revokeError,
  });

  final AuthSession? signInResult;
  final AuthSession? refreshResult;
  final Future<AuthSession>? refreshFuture;
  final Object? refreshError;
  final Object? revokeError;
  int refreshCalls = 0;

  @override
  Future<AuthSession> refresh(String refreshToken) async {
    refreshCalls++;
    if (refreshError case final error?) throw error;
    if (refreshFuture case final future?) return future;
    return refreshResult!;
  }

  @override
  Future<void> revoke(String refreshToken) async {
    if (revokeError case final error?) throw error;
  }

  @override
  Future<AuthSession> signIn({required String email, required String password}) async =>
      signInResult!;
}
