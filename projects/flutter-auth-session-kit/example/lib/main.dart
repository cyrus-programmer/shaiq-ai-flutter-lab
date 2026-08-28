import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_auth_session_kit/flutter_auth_session_kit.dart';

void main() => runApp(const SessionDemo());

final class SessionDemo extends StatefulWidget {
  const SessionDemo({super.key});

  @override
  State<SessionDemo> createState() => _SessionDemoState();
}

final class _SessionDemoState extends State<SessionDemo> {
  late final SessionManager sessions;

  @override
  void initState() {
    super.initState();
    sessions = SessionManager(api: DemoAuthApi(), store: MemoryTokenStore())
      ..addListener(_refresh);
    unawaited(sessions.restore());
  }

  @override
  void dispose() {
    sessions
      ..removeListener(_refresh)
      ..dispose();
    super.dispose();
  }

  void _refresh() => setState(() {});

  @override
  Widget build(BuildContext context) {
    final state = sessions.state;
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: const Color(0xff2f6fed), useMaterial3: true),
      home: Scaffold(
        appBar: AppBar(title: const Text('Session Kit Demo')),
        body: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  Icon(
                    state.isAuthenticated ? Icons.verified_user : Icons.lock_outline,
                    size: 64,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    state.status.name,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  if (state.session case final session?) ...<Widget>[
                    const SizedBox(height: 8),
                    Text('User: ${session.userId}', textAlign: TextAlign.center),
                  ],
                  if (state.failure case final failure?) ...<Widget>[
                    const SizedBox(height: 8),
                    Text(failure.message, textAlign: TextAlign.center),
                  ],
                  const SizedBox(height: 28),
                  FilledButton(
                    onPressed: state.isAuthenticated
                        ? null
                        : () => sessions.signIn(
                              email: 'demo@example.com',
                              password: 'demo-only',
                            ),
                    child: const Text('Sign in with demo backend'),
                  ),
                  OutlinedButton(
                    onPressed: state.isAuthenticated ? sessions.forceRefresh : null,
                    child: const Text('Force token refresh'),
                  ),
                  TextButton(
                    onPressed: state.isAuthenticated ? sessions.logout : null,
                    child: const Text('Log out'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

final class DemoAuthApi implements AuthApi {
  var version = 0;

  @override
  Future<AuthSession> refresh(String refreshToken) async => _session();

  @override
  Future<void> revoke(String refreshToken) async {}

  @override
  Future<AuthSession> signIn({required String email, required String password}) async =>
      _session();

  AuthSession _session() {
    version++;
    return AuthSession(
      accessToken: 'demo-access-$version',
      refreshToken: 'demo-refresh-$version',
      expiresAt: DateTime.now().toUtc().add(const Duration(minutes: 5)),
      userId: 'demo-user',
    );
  }
}
