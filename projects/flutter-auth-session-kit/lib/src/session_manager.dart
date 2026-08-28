import 'dart:async';

import 'package:flutter/foundation.dart';

import 'auth_api.dart';
import 'auth_failure.dart';
import 'auth_session.dart';
import 'token_store.dart';

typedef Clock = DateTime Function();

enum SessionStatus {
  uninitialized,
  authenticating,
  authenticated,
  refreshing,
  unauthenticated,
  failure,
}

final class SessionState {
  const SessionState._(this.status, {this.session, this.failure});

  const SessionState.uninitialized()
      : this._(SessionStatus.uninitialized);
  const SessionState.authenticating()
      : this._(SessionStatus.authenticating);
  const SessionState.authenticated(AuthSession session)
      : this._(SessionStatus.authenticated, session: session);
  const SessionState.refreshing(AuthSession session)
      : this._(SessionStatus.refreshing, session: session);
  const SessionState.unauthenticated()
      : this._(SessionStatus.unauthenticated);
  const SessionState.failure(AuthFailure failure, {AuthSession? session})
      : this._(SessionStatus.failure, failure: failure, session: session);

  final SessionStatus status;
  final AuthSession? session;
  final AuthFailure? failure;

  bool get isAuthenticated => session != null &&
      (status == SessionStatus.authenticated ||
          status == SessionStatus.refreshing ||
          status == SessionStatus.failure);
}

/// Coordinates restore, login, refresh and logout without owning HTTP/storage SDKs.
final class SessionManager extends ChangeNotifier {
  SessionManager({
    required AuthApi api,
    required TokenStore store,
    Duration refreshSkew = const Duration(seconds: 30),
    Clock? clock,
  })  : _api = api,
        _store = store,
        _refreshSkew = refreshSkew,
        _clock = clock ?? DateTime.now;

  final AuthApi _api;
  final TokenStore _store;
  final Duration _refreshSkew;
  final Clock _clock;

  SessionState _state = const SessionState.uninitialized();
  Future<String>? _refreshInFlight;
  int _generation = 0;

  SessionState get state => _state;

  Future<void> restore() async {
    final generation = ++_generation;
    try {
      final stored = await _store.read();
      if (generation != _generation) return;
      if (stored == null) {
        _emit(const SessionState.unauthenticated());
        return;
      }
      _emit(SessionState.authenticated(stored));
      if (stored.expiresWithin(_clock(), _refreshSkew)) {
        try {
          await _refresh(force: true);
        } catch (_) {
          // _refresh has already translated the error into the correct state.
        }
      }
    } on FormatException {
      await _store.delete();
      if (generation == _generation) {
        _emit(const SessionState.failure(AuthFailure(
          AuthFailureKind.malformedSession,
          'The saved session could not be restored.',
        )));
      }
    } catch (_) {
      if (generation == _generation) {
        _emit(const SessionState.failure(AuthFailure(
          AuthFailureKind.unknown,
          'The saved session could not be restored.',
          retryable: true,
        )));
      }
    }
  }

  Future<void> signIn({required String email, required String password}) async {
    final generation = ++_generation;
    _emit(const SessionState.authenticating());
    try {
      final session = await _api.signIn(email: email, password: password);
      if (generation != _generation) return;
      await _store.write(session);
      if (generation == _generation) _emit(SessionState.authenticated(session));
    } on AuthApiException catch (error) {
      if (generation == _generation) _emit(SessionState.failure(error.toFailure()));
    } catch (_) {
      if (generation == _generation) {
        _emit(const SessionState.failure(AuthFailure(
          AuthFailureKind.unknown,
          'Sign-in failed. Please try again.',
          retryable: true,
        )));
      }
    }
  }

  Future<String> authorizedToken() {
    final session = _state.session;
    if (session == null) {
      return Future<String>.error(const UnauthorizedException());
    }
    if (!session.expiresWithin(_clock(), _refreshSkew)) {
      return Future<String>.value(session.accessToken);
    }
    return _refresh();
  }

  Future<String> forceRefresh() => _refresh(force: true);

  Future<String> _refresh({bool force = false}) {
    final existing = _refreshInFlight;
    if (existing != null) return existing;
    final session = _state.session;
    if (session == null) {
      return Future<String>.error(const UnauthorizedException());
    }
    if (!force && !session.expiresWithin(_clock(), _refreshSkew)) {
      return Future<String>.value(session.accessToken);
    }

    final completer = Completer<String>();
    _refreshInFlight = completer.future;
    final generation = _generation;
    _emit(SessionState.refreshing(session));

    unawaited(() async {
      try {
        final refreshed = await _api.refresh(session.refreshToken);
        if (generation != _generation) throw const UnauthorizedException();
        await _store.write(refreshed);
        if (generation != _generation) throw const UnauthorizedException();
        _emit(SessionState.authenticated(refreshed));
        completer.complete(refreshed.accessToken);
      } on AuthApiException catch (error) {
        if (generation == _generation) {
          if (error.retryable) {
            _emit(SessionState.failure(error.toFailure(), session: session));
          } else {
            await _store.delete();
            _emit(SessionState.failure(error.toFailure()));
          }
        }
        completer.completeError(error);
      } catch (error, stackTrace) {
        if (generation == _generation) {
          _emit(SessionState.failure(
            const AuthFailure(
              AuthFailureKind.unknown,
              'Session refresh failed. Please try again.',
              retryable: true,
            ),
            session: session,
          ));
        }
        completer.completeError(error, stackTrace);
      } finally {
        if (identical(_refreshInFlight, completer.future)) {
          _refreshInFlight = null;
        }
      }
    }());
    return completer.future;
  }

  Future<void> logout() async {
    final session = _state.session;
    _generation++;
    _refreshInFlight = null;
    await _store.delete();
    _emit(const SessionState.unauthenticated());
    if (session != null) {
      try {
        await _api.revoke(session.refreshToken);
      } catch (_) {
        // Local logout must succeed even when best-effort server revocation fails.
      }
    }
  }

  void _emit(SessionState next) {
    _state = next;
    notifyListeners();
  }
}
